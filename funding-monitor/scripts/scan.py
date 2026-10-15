#!/usr/bin/env python3
"""funding-monitor: scan research funding channels, score against a profile, write a digest.

Standard library only. Python 3.11+ (tomllib).

Subcommands
  init   copy the profile template to a new profile file
  plan   print the monitoring plan (what is monitored, by what means, how often)
  check  test that each machine-readable channel is reachable and parseable
  scan   fetch, dedupe, score, and write Markdown + JSON

Profile lookup order (first that exists wins):
  --profile PATH, $FUNDING_MONITOR_PROFILE, ~/.config/funding-monitor/profile.toml,
  ./profile.toml, <skill>/config/profile.toml

API keys come from environment variables named in the profile (never from the profile itself):
  SAM_API_KEY, SIMPLER_API_KEY by default. A ~/.config/funding-monitor/.env file with
  KEY=value lines is also read if present.

Examples
  python3 scan.py init --out ~/.config/funding-monitor/profile.toml
  python3 scan.py plan
  python3 scan.py check
  python3 scan.py scan --since-days 8 --details --out-dir ./out
  python3 scan.py scan --state ~/.config/funding-monitor/state.json --details --out-dir ./out
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit("Python 3.11+ is required (tomllib).")

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
TEMPLATE = SKILL_DIR / "config" / "profile.template.toml"
USER_DIR = Path.home() / ".config" / "funding-monitor"
UA = "funding-monitor/2.0 (+research funding scan; contact in profile)"
TIMEOUT = 40

GG_SEARCH = "https://api.grants.gov/v1/api/search2"
GG_FETCH = "https://api.grants.gov/v1/api/fetchOpportunity"
GG_VIEW = "https://www.grants.gov/search-results-detail/{id}"
SIMPLER_SEARCH = "https://api.simpler.grants.gov/v1/opportunities/search"
SAM_SEARCH = "https://api.sam.gov/opportunities/v2/search"
SAM_PTYPES = {"o": "Solicitation", "k": "Combined synopsis/solicitation", "p": "Presolicitation",
              "r": "Sources sought", "s": "Special notice", "a": "Award notice"}

MEANS_LABEL = {
    "api": "API query",
    "rss": "RSS feed",
    "web": "Web page check (link scraping)",
    "sitemap": "Sitemap check (new or updated pages)",
    "browser": "Web page check (headless browser rendering)",
    "email": "Email (newsletter or list)",
    "alert": "Email alert from a saved search at the provider",
    "manual": "Manual check (no automation possible)",
}


# ------------------------------------------------------------------ profile and env
def find_profile(explicit: Path | None) -> Path:
    cands = [explicit] if explicit else []
    if os.environ.get("FUNDING_MONITOR_PROFILE"):
        cands.append(Path(os.environ["FUNDING_MONITOR_PROFILE"]))
    cands += [USER_DIR / "profile.toml", Path("profile.toml"), SKILL_DIR / "config" / "profile.toml"]
    for c in cands:
        if c and c.expanduser().exists():
            return c.expanduser()
    sys.exit("No profile found. Run setup (see SKILL.md) or: scan.py init --out ~/.config/funding-monitor/profile.toml")


def load_profile(path: Path) -> dict:
    prof = tomllib.loads(path.read_text())
    prof.setdefault("channel", [])
    if prof.get("meta", {}).get("is_template"):
        print(f"WARNING: {path} is the unedited template. Run setup first.", file=sys.stderr)
    return prof


CREDENTIALS_FILE = SKILL_DIR / "config" / "credentials.toml"


def _read_dotenv() -> dict:
    f = USER_DIR / ".env"
    out = {}
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def resolve_secret(name: str) -> tuple[str | None, str]:
    """Return (value, source) for a credential, trying host-neutral delivery forms in order.
    The value is never logged or printed. See config/credentials.toml."""
    v = os.environ.get(name)
    if v:
        return v.strip(), "environment variable"
    candidates = []
    if os.environ.get(f"{name}_FILE"):
        candidates.append((Path(os.environ[f"{name}_FILE"]).expanduser(), f"file from {name}_FILE"))
    if os.environ.get("CREDENTIALS_DIRECTORY"):
        candidates.append((Path(os.environ["CREDENTIALS_DIRECTORY"]) / name, "systemd credentials directory"))
    candidates.append((Path("/run/secrets") / name.lower(), "/run/secrets mount"))
    for path, label in candidates:
        try:
            if path.is_file():
                val = path.read_text().strip()
                if val:
                    return val, label
        except OSError:
            continue
    val = _read_dotenv().get(name)
    if val:
        return val, "~/.config/funding-monitor/.env"
    return None, "not found"


def get_secret(name: str) -> str | None:
    return resolve_secret(name)[0]


def load_credential_specs() -> list[dict]:
    if CREDENTIALS_FILE.exists():
        return tomllib.loads(CREDENTIALS_FILE.read_text()).get("credential", [])
    return []


def load_dotenv() -> None:
    """Kept for compatibility: secrets are now resolved on demand by resolve_secret()."""
    return


# ------------------------------------------------------------------ http helpers
def _request(url: str, data: dict | None = None, headers: dict | None = None) -> bytes:
    hdrs = {"User-Agent": UA}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST" if body else "GET")
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 422, 429):
                raise
            last = e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def _json(url, data=None, headers=None):
    return json.loads(_request(url, data, headers))


def _clean(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s))).strip()


def _parse_date(s: str | None) -> dt.date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:  # RFC 822 dates in RSS
        return email.utils.parsedate_to_datetime(s).date()
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return dt.date.fromisoformat(m.group(1)) if m else None


def _rec(**kw) -> dict:
    base = {"source": "", "channel": "", "uid": "", "id": "", "number": "", "title": "", "agency": "",
            "agency_code": "", "status": "", "doc_type": "", "posted": "", "close": "", "url": "",
            "text": "", "evidence": ""}
    base.update(kw)
    return base


# ------------------------------------------------------------------ handlers
def h_grants_gov(ch: dict, prof: dict, ctx: dict) -> list[dict]:
    queries = ch.get("queries") or prof.get("queries", {}).get("api", [])
    hits: dict[str, dict] = {}
    for kw in queries:
        payload = {"keyword": kw, "oppStatuses": "forecasted|posted", "rows": 100,
                   "dateRange": str(ctx["since_days"])}
        try:
            d = _json(GG_SEARCH, payload)["data"]
        except Exception as e:  # noqa: BLE001
            ctx["log"].append(f"{ch['id']}: query '{kw}' failed: {e}")
            continue
        for h in d.get("oppHits", []):
            hits.setdefault(h["id"], _rec(
                source="grants.gov", channel=ch["id"], uid=f"gg:{h['id']}", id=h["id"],
                number=h.get("number", ""), title=h.get("title", ""), agency=h.get("agency", ""),
                agency_code=h.get("agencyCode", ""), status=h.get("oppStatus", ""),
                doc_type=h.get("docType", ""), posted=h.get("openDate", ""), close=h.get("closeDate", ""),
                url=GG_VIEW.format(id=h["id"]), evidence="API"))
        time.sleep(0.3)
    cutoff = dt.date.today() - dt.timedelta(days=ctx["since_days"])
    out = [r for r in hits.values() if (_parse_date(r["posted"]) or dt.date.today()) >= cutoff]
    ctx["log"].append(f"{ch['id']}: {len(out)} opportunities from {len(queries)} queries")
    return out


def enrich_grants_gov(items: list[dict], ctx: dict, limit: int) -> None:
    n = 0
    for r in items:
        if r["source"] != "grants.gov" or n >= limit:
            continue
        try:
            d = _json(GG_FETCH, {"opportunityId": int(r["id"])})["data"]
        except Exception as e:  # noqa: BLE001
            ctx["log"].append(f"grants.gov detail {r['number']} failed: {e}")
            continue
        n += 1
        s = d.get("synopsis") or d.get("forecast") or {}
        r["text"] = _clean(s.get("synopsisDesc") or s.get("forecastDesc"))[:3000]
        r["eligibility_codes"] = [a.get("id") for a in (s.get("applicantTypes") or [])]
        r["eligibility_note"] = _clean(s.get("applicantEligibilityDesc"))[:400]
        r["instrument"] = ", ".join(i.get("description", "") for i in (s.get("fundingInstruments") or []))
        r["award_ceiling"] = s.get("awardCeilingFormatted") or s.get("awardCeiling") or ""
        r["est_funding"] = s.get("estimatedFundingFormatted") or s.get("estimatedFunding") or ""
        r["response_desc"] = _clean(s.get("responseDateDesc"))[:300]
        time.sleep(0.3)
    ctx["log"].append(f"grants.gov: fetched details for {n} opportunities")


def h_simpler(ch: dict, prof: dict, ctx: dict) -> list[dict]:
    key = get_secret(ch.get("key_env", "SIMPLER_API_KEY"))
    if not key:
        ctx["log"].append(f"{ch['id']}: skipped, {ch.get('key_env', 'SIMPLER_API_KEY')} not found in any supported delivery form (run: scan.py credentials)")
        return []
    start = (dt.date.today() - dt.timedelta(days=ctx["since_days"])).isoformat()
    out: dict[str, dict] = {}
    for kw in ch.get("queries") or prof.get("queries", {}).get("api", []):
        payload = {"query": kw,
                   "filters": {"opportunity_status": {"one_of": ["posted", "forecasted"]},
                               "post_date": {"start_date": start}},
                   "pagination": {"page_offset": 1, "page_size": 100,
                                  "sort_order": [{"order_by": "post_date", "sort_direction": "descending"}]}}
        try:
            d = _json(SIMPLER_SEARCH, payload, {"X-API-Key": key})
        except Exception as e:  # noqa: BLE001
            ctx["log"].append(f"{ch['id']}: query '{kw}' failed: {e}")
            continue
        for o in d.get("data", []):
            oid = str(o.get("opportunity_id") or o.get("legacy_opportunity_id") or "")
            s = o.get("summary") or {}
            out.setdefault(oid, _rec(
                source="simpler.grants.gov", channel=ch["id"], uid=f"sg:{oid}", id=oid,
                number=o.get("opportunity_number", ""), title=o.get("opportunity_title", ""),
                agency=o.get("agency_name") or "", agency_code=o.get("agency_code") or "",
                status=o.get("opportunity_status", ""), posted=s.get("post_date") or "",
                close=s.get("close_date") or "", url=f"https://simpler.grants.gov/opportunity/{oid}",
                text=_clean(s.get("summary_description"))[:2000], evidence="API"))
        time.sleep(1.1)
    ctx["log"].append(f"{ch['id']}: {len(out)} opportunities")
    return list(out.values())


def h_sam(ch: dict, prof: dict, ctx: dict) -> list[dict]:
    """One request per entry in ch['requests'] (default: one per organization), because
    non-federal SAM.gov keys have a small daily request quota. Keyword filtering is local."""
    env = ch.get("key_env", "SAM_API_KEY")
    key = get_secret(env)
    if not key:
        ctx["log"].append(f"{ch['id']}: skipped, {env} not found in any supported delivery form (run: scan.py credentials)")
        return []
    today = dt.date.today()
    base = {"api_key": key, "postedFrom": (today - dt.timedelta(days=ctx["since_days"])).strftime("%m/%d/%Y"),
            "postedTo": today.strftime("%m/%d/%Y"), "limit": 1000, "offset": 0,
            "ptype": ch.get("ptypes", ["o", "k", "p", "r", "s"])}
    reqs = ch.get("requests") or [{"organizationName": o} for o in ch.get("organizations", [])] or [{}]
    budget = int(ch.get("max_requests_per_run", 6))
    out: dict[str, dict] = {}
    for i, extra in enumerate(reqs):
        if i >= budget:
            ctx["log"].append(f"{ch['id']}: request budget {budget} reached, {len(reqs) - budget} skipped")
            break
        q = {**base, **extra}
        try:
            d = _json(SAM_SEARCH + "?" + urllib.parse.urlencode(q, doseq=True))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = _clean(e.read().decode("utf-8", "replace"))[:160]
            except Exception:  # noqa: BLE001
                pass
            hint = {401: "key rejected", 403: "key rejected or not yet active", 404: "no data, or key invalid (SAM.gov returns 404 for both)",
                    429: "daily quota spent"}.get(e.code, "")
            ctx["log"].append(f"{ch['id']}: {extra} HTTP {e.code} ({hint})" + (f" Response: {body}" if body else ""))
            continue
        except Exception as e:  # noqa: BLE001
            ctx["log"].append(f"{ch['id']}: {extra} failed: {e}")
            continue
        for o in d.get("opportunitiesData") or []:
            nid = o.get("noticeId", "")
            out.setdefault(nid, _rec(
                source="sam.gov", channel=ch["id"], uid=f"sam:{nid}", id=nid,
                number=(o.get("solicitationNumber") or "").strip(), title=o.get("title", ""),
                agency=o.get("fullParentPathName", ""), agency_code=o.get("fullParentPathCode", ""),
                status="active" if o.get("active") == "Yes" else (o.get("active") or ""),
                doc_type=o.get("type", ""), posted=o.get("postedDate", ""),
                close=o.get("responseDeadLine") or o.get("reponseDeadLine") or "",
                url=f"https://sam.gov/opp/{nid}/view", evidence="API"))
        time.sleep(1)
    ctx["log"].append(f"{ch['id']}: {len(out)} notices from {min(len(reqs), budget)} requests")
    return list(out.values())


def _fix_xml(raw: bytes) -> bytes:
    return re.sub(rb"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", b"&amp;", raw)


def h_rss(ch: dict, prof: dict, ctx: dict) -> list[dict]:
    try:
        raw = _request(ch["url"])
    except Exception as e:  # noqa: BLE001
        ctx["log"].append(f"{ch['id']}: fetch failed: {e}")
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        try:
            root = ET.fromstring(_fix_xml(raw))
            ctx["log"].append(f"{ch['id']}: malformed XML repaired")
        except ET.ParseError as e:
            ctx["log"].append(f"{ch['id']}: unparseable feed: {e}")
            return []
    atom = "{http://www.w3.org/2005/Atom}"
    items = root.findall("./channel/item") or root.findall(f"{atom}entry")
    chan_date = root.findtext("./channel/pubDate") or root.findtext(f"{atom}updated") or ""
    cutoff = dt.date.today() - dt.timedelta(days=ctx["since_days"])
    out = []
    for it in items:
        title = (it.findtext("title") or it.findtext(f"{atom}title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not link:
            le = it.find(f"{atom}link")
            link = le.get("href", "") if le is not None else ""
        desc = _clean(it.findtext("description") or it.findtext(f"{atom}summary") or "")
        pub = it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or it.findtext(f"{atom}updated") or ""
        pd = _parse_date(pub)
        if pd and pd < cutoff:
            continue
        num = re.search(r"\b((?:NSF|PD)\s?\d{2}-\d{3,4}|(?:RFA|PAR|PA|NOT|PAS)-[A-Z]{2}-\d{2}-\d{3})\b", f"{title} {desc}")
        dls = re.findall(r"((?:Full Proposal|Letter of Intent|Preliminary Proposal|Application Due|Deadline)[^:]{0,40}):\s*([A-Z][a-z]+ \d{1,2}, \d{4})", desc)
        out.append(_rec(source=ch["id"], channel=ch["id"], uid=f"rss:{link or title}", id=link,
                        number=num.group(1) if num else "", title=title, agency=ch.get("agency", ""),
                        agency_code=ch.get("agency_code", ""), status="posted", doc_type=ch.get("doc_type", "feed item"),
                        posted=pub.strip(), close="; ".join(f"{k}: {v}" for k, v in dls), url=link,
                        text=desc[:1500], evidence="feed", feed_date=chan_date.strip()))
    ctx["log"].append(f"{ch['id']}: {len(out)} items (feed updated: {chan_date.strip() or 'not stated'})")
    return out


_DATE_RX = re.compile(r"^\s*(?:Week of\s+|Posted:?\s+|Updated:?\s+)?((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\s*$")


class _Links(HTMLParser):
    """Collect (href, anchor text, nearest preceding standalone date) for every link."""

    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str, str]] = []
        self.after: list[str] = []   # text between this link and the next one
        self._href = None
        self._txt: list[str] = []
        self.current_date = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._txt = []

    def handle_data(self, data):
        if self._href is not None:
            self._txt.append(data)
            return
        if self.after and len(self.after[-1]) < 600:
            self.after[-1] += " " + data
        m = _DATE_RX.match(data)
        if m:
            self.current_date = m.group(1).replace(".", "")

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._txt).split()), self.current_date))
            self.after.append("")
            self._href = None


def _allowed(url: str, ch: dict, prof: dict, ctx: dict) -> bool:
    """Honor robots.txt unless the user turned that off for this channel (ignore_robots = true)
    or for the whole profile ([fetching] respect_robots = false). The override is logged."""
    respect = prof.get("fetching", {}).get("respect_robots", True) and not ch.get("ignore_robots", False)
    if respect:
        return _robots_ok(url, ctx["log"], ch["id"])
    probe: list = []
    if not _robots_ok(url, probe, ch["id"]):
        ctx["log"].append(f"{ch['id']}: robots.txt disallows automated agents. Fetching anyway because the profile overrides it.")
    return True


def _robots_ok(url: str, log: list, cid: str) -> bool:
    """Minimal robots.txt check for the '*' group with wildcard support and longest-match
    precedence. urllib.robotparser is avoided because it treats a 403 on robots.txt (common
    with web application firewalls) as 'disallow everything' and ignores wildcards."""
    p = urllib.parse.urlparse(url)
    try:
        txt = _request(f"{p.scheme}://{p.netloc}/robots.txt").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return True  # no readable robots.txt
    rules, active, saw_agent, active_group_open = [], False, False, False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if saw_agent and not active_group_open:
                active = False
            active = active or v == "*" or v.lower().startswith("funding-monitor")
            saw_agent, active_group_open = True, True
        elif k in ("allow", "disallow"):
            active_group_open = False
            if active and v:
                rx = "^" + re.escape(v).replace(r"\*", ".*").replace(r"\$", "$")
                rules.append((len(v), k == "allow", re.compile(rx)))
    target = p.path or "/"
    if p.query:
        target += "?" + p.query
    match = max((r for r in rules if r[2].match(target)), default=None, key=lambda r: (r[0], r[1]))
    ok = match is None or match[1]
    if not ok:
        log.append(f"{cid}: robots.txt disallows automated fetching of this URL. Skipped. Check it manually.")
    return ok


def _deadline_text(s: str) -> str:
    """Pull 'Deadline: ...' style text that listing pages often print after each link."""
    m = re.search(r"(?:Funder\s+)?(?:Deadline|Due(?: date)?|Applications? due)s?:?\s*(.{4,80}?)(?=\s+(?:Amount|Focus|Award|Eligib|Sponsor|Funder)\b|$)", s, re.I)
    if m:
        return m.group(0).strip()
    m = re.search(r"(?:Deadline|Due date|Closing date|Proposals? due|accepted until|due no later than)s?:?\s*((?:[A-Z][a-z]{2,8}\.? \d{1,2}, \d{4})|\d{1,2}/\d{1,2}/\d{4}|Rolling)", s, re.I)
    return f"Deadline: {m.group(1)}" if m else ""


def h_web(ch: dict, prof: dict, ctx: dict) -> list[dict]:
    url = ch["url"]
    if not _allowed(url, ch, prof, ctx):
        return []
    try:
        raw = _request(url)
    except Exception as e:  # noqa: BLE001
        ctx["log"].append(f"{ch['id']}: fetch failed: {e}")
        return []
    page = raw.decode("utf-8", "replace")
    p = _Links()
    p.feed(page)
    pat = re.compile(ch.get("link_pattern", "."), re.I)
    min_len = int(ch.get("min_link_text", 12))
    seen, out = set(), []
    cutoff = dt.date.today() - dt.timedelta(days=ctx["since_days"])
    dated = undated_old = 0
    for (href, text, sect_date), trail in zip(p.links, p.after):
        full = urllib.parse.urljoin(url, href)
        trail = " ".join(trail.split())[:500]
        if len(text) < min_len or not (pat.search(full) or pat.search(text)) or full in seen:
            # Text between this non-matching link and the next item belongs to the previous item
            # (listing pages often print deadline, amount, and contact columns after the title).
            if out and ch.get("capture_context", True) and len(out[-1]["text"]) < 900:
                out[-1]["text"] = (out[-1]["text"] + " " + text + " " + trail).strip()[:900]
            continue
        d = _parse_date(sect_date) if sect_date else None
        if d:
            dated += 1
            if ch.get("use_section_dates", True) and d < cutoff:
                undated_old += 1
                continue
        seen.add(full)
        out.append(_rec(source=ch["id"], channel=ch["id"], uid=f"web:{full}", id=full, title=text,
                        agency=ch.get("agency", ""), agency_code=ch.get("agency_code", ""),
                        doc_type="page link", url=full, posted=sect_date, evidence="page",
                        text=trail if ch.get("capture_context", True) else "",
                        close=_deadline_text(trail)))
        if len(out) > 1:
            out[-2]["close"] = out[-2]["close"] or _deadline_text(out[-2]["text"])
        if len(out) >= int(ch.get("max_links", 400)):
            ctx["log"].append(f"{ch['id']}: max_links {ch.get('max_links', 400)} reached")
            break
    if out:
        out[-1]["close"] = out[-1]["close"] or _deadline_text(out[-1]["text"])
    if undated_old:
        ctx["log"].append(f"{ch['id']}: {undated_old} links under section dates older than the window were skipped")
    fp = hashlib.sha256(re.sub(r"\s+", " ", _clean(page)).encode()).hexdigest()[:16]
    ctx.setdefault("page_fingerprints", {})[ch["id"]] = fp
    if len(page) > 2000 and not out:
        ctx["log"].append(f"{ch['id']}: page fetched but no matching links. It may be rendered by JavaScript. Check manually.")
    else:
        ctx["log"].append(f"{ch['id']}: {len(out)} matching links")
    return out


def h_sitemap(ch: dict, prof: dict, ctx: dict) -> list[dict]:
    """Read a sitemap (or sitemap index), keep URLs matching loc_pattern whose lastmod falls in
    the window, then fetch each page for its title, description, and any deadline text.
    Works for many JavaScript-heavy sites, because sitemaps are plain XML."""
    url = ch["url"]
    if not _allowed(url, ch, prof, ctx):
        return []
    pat = re.compile(ch.get("loc_pattern", "."), re.I)
    cutoff = dt.date.today() - dt.timedelta(days=ctx["since_days"])
    entries: list[tuple[str, str]] = []
    todo, n_maps = [url], 0
    while todo and n_maps < int(ch.get("max_sitemaps", 10)):
        u = todo.pop(0)
        n_maps += 1
        try:
            raw = _request(u).decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            ctx["log"].append(f"{ch['id']}: sitemap {u} failed: {e}")
            continue
        if "<sitemapindex" in raw:
            sp = re.compile(ch.get("sitemap_pattern", "."), re.I)
            todo += [x for x in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", raw) if sp.search(x)]
            continue
        for block in re.findall(r"<url>(.*?)</url>", raw, re.S):
            loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block)
            mod = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", block)
            if loc and pat.search(loc.group(1)):
                entries.append((loc.group(1), mod.group(1) if mod else ""))
    recent = [(u, m) for u, m in entries if not m or (_parse_date(m) or dt.date.today()) >= cutoff]
    recent.sort(key=lambda x: x[1], reverse=True)
    out = []
    for loc, mod in recent[: int(ch.get("max_pages", 25))]:
        title, desc, body = loc.rstrip("/").rsplit("/", 1)[-1], "", ""
        try:
            page = _request(loc).decode("utf-8", "replace")
            t = re.search(r"<title>(.*?)</title>", page, re.S | re.I)
            if t:
                title = _clean(t.group(1))
                suf = ch.get("title_suffix", "")
                if suf and title.endswith(suf):
                    title = title[: -len(suf)].strip()
            d = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', page, re.I)
            desc = _clean(d.group(1)) if d else ""
            body = _clean(re.sub(r"(?is)<(script|style|nav|header|footer)\b.*?</\1>", " ", page))
        except Exception as e:  # noqa: BLE001
            ctx["log"].append(f"{ch['id']}: page {loc} failed: {e}")
        slug = loc.rstrip("/").rsplit("/", 1)[-1]
        out.append(_rec(source=ch["id"], channel=ch["id"], uid=f"web:{loc}", id=loc, title=title,
                        number=slug.upper() if ch.get("number_from_slug") else "",
                        agency=ch.get("agency", ""), agency_code=ch.get("agency_code", ""),
                        doc_type="page added or updated", posted=mod[:10], close=_deadline_text(body),
                        url=loc, text=(desc + " " + body)[:1500], evidence="page"))
        time.sleep(0.5)
    ctx["log"].append(f"{ch['id']}: {len(entries)} matching sitemap URLs, {len(recent)} modified in window, {len(out)} fetched")
    return out


def playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def h_browser(ch: dict, prof: dict, ctx: dict) -> list[dict]:
    """Render a JavaScript page with headless Chromium (optional Playwright dependency), then
    read table rows from the DOM (row_selector + columns, most robust), parse rows from the
    visible text (row_regex with named groups number, title, desc, due, posted, agency, link),
    or collect rendered links matching link_pattern.
    Without Playwright the channel is reported as a manual check."""
    url = ch["url"]
    if not playwright_available():
        ctx["log"].append(f"{ch['id']}: Playwright not installed, check manually: {url} "
                          "(pip install playwright, then python3 -m playwright install chromium)")
        return []
    if not _allowed(url, ch, prof, ctx):
        return []
    from playwright.sync_api import sync_playwright
    timeout = int(ch.get("timeout_ms", 90000))
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as e:  # noqa: BLE001
                ctx["log"].append(f"{ch['id']}: Chromium unavailable ({str(e)[:80]}). Run: python3 -m playwright install chromium")
                return []
            page = browser.new_page(user_agent=UA)
            page.goto(url, wait_until="networkidle", timeout=timeout)
            if ch.get("wait_for"):
                page.wait_for_selector(ch["wait_for"], timeout=timeout)
            if ch.get("row_selector"):
                try:  # tables often fill in after network idle
                    page.wait_for_function("sel => document.querySelectorAll(sel).length > 2",
                                           arg=ch["row_selector"], timeout=min(timeout, 30000))
                except Exception:  # noqa: BLE001
                    pass
            page.wait_for_timeout(int(ch.get("wait_ms", 2000)))
            text = page.inner_text("body")
            links = page.eval_on_selector_all("a", "els => els.map(e => [e.href, (e.innerText || '').trim()])")
            dom_rows = []
            if ch.get("row_selector"):
                dom_rows = page.eval_on_selector_all(
                    ch["row_selector"],
                    "(els, cellSel) => els.map(r => ({cells: [...r.querySelectorAll(cellSel)]"
                    ".map(c => (c.innerText || '').trim().replace(/\\s+/g, ' ')),"
                    " link: (r.querySelector('a[href]') || {}).href || ''}))",
                    ch.get("cell_selector", "td, [role=cell], [role=gridcell]"))
            browser.close()
    except Exception as e:  # noqa: BLE001
        ctx["log"].append(f"{ch['id']}: rendering failed: {str(e)[:160]}. Check manually: {url}")
        return []
    out = []
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=ctx["since_days"])
    if ch.get("row_selector") or ch.get("row_regex"):
        if ch.get("row_selector"):
            cols = ch.get("columns", ["title", "desc", "due"])
            groups = []
            for r in dom_rows:
                if not r["cells"] or not any(r["cells"]):
                    continue
                g = {name: (r["cells"][i] if i < len(r["cells"]) else "") for i, name in enumerate(cols) if name}
                g.setdefault("link", r.get("link", ""))
                groups.append(g)
        else:
            groups = [{k: (v or "").strip() for k, v in m.groupdict().items()}
                      for m in re.finditer(ch["row_regex"], text, re.M)]
        flt = ch.get("filter")  # e.g. {field = "category", regex = "Limited Submission"}
        if flt:
            frx = re.compile(flt["regex"], re.I)
            groups = [g for g in groups if frx.search(g.get(flt["field"], ""))]
        matched = len(groups)
        dropped = 0
        for g in groups:
            due = _parse_date(g.get("due"))
            if ch.get("keep") == "upcoming" and due and due < today:
                dropped += 1
                continue
            posted = _parse_date(g.get("posted"))
            if posted and posted < cutoff:
                dropped += 1
                continue
            key = g.get("number") or g.get("title", "")
            out.append(_rec(source=ch["id"], channel=ch["id"], uid=f"br:{ch['id']}:{key}", id=key,
                            number=g.get("number", ""), title=g.get("title", ""),
                            agency=g.get("agency") or ch.get("agency", ""), agency_code=ch.get("agency_code", ""),
                            doc_type=ch.get("doc_type", "rendered row"), posted=g.get("posted", ""),
                            close=f"Due: {g['due']}" if g.get("due") else "", url=g.get("link") or url,
                            text=g.get("desc", ""), evidence="page"))
        ctx["log"].append(f"{ch['id']}: rendered page, {matched} rows matched, {len(out)} kept, {dropped} dropped by date")
        if not matched:
            ctx["log"].append(f"{ch['id']}: no rows matched. The layout may have changed. Check manually: {url}")
    else:
        pat = re.compile(ch.get("link_pattern", "."), re.I)
        seen = set()
        for href, t in links:
            if len(t) >= int(ch.get("min_link_text", 12)) and (pat.search(href) or pat.search(t)) and href not in seen:
                seen.add(href)
                out.append(_rec(source=ch["id"], channel=ch["id"], uid=f"web:{href}", id=href, title=" ".join(t.split()),
                                agency=ch.get("agency", ""), agency_code=ch.get("agency_code", ""),
                                doc_type="rendered link", url=href, evidence="page"))
        ctx["log"].append(f"{ch['id']}: rendered page, {len(out)} matching links")
    return out


HANDLERS = {"grants_gov": h_grants_gov, "simpler": h_simpler, "sam": h_sam, "rss": h_rss, "web": h_web,
            "sitemap": h_sitemap, "browser": h_browser}


# ------------------------------------------------------------------ scoring
def score(rec: dict, prof: dict) -> None:
    kw = prof["keywords"]
    w = kw.get("weights", {"tier_a": 3, "tier_b": 2, "tier_c": 1})
    title = f" {rec['title']} ".lower()
    body = f" {rec.get('text', '')} ".lower()
    hits = {"a": [], "b": [], "c": []}
    total, title_hit = 0, False
    for tier in ("a", "b", "c"):
        for term in kw.get(f"tier_{tier}", []):
            t = term.lower()
            if t in title:
                hits[tier].append(term.strip())
                total += w[f"tier_{tier}"] * 2
                title_hit = True
            elif t in body:
                hits[tier].append(term.strip())
                total += w[f"tier_{tier}"]
    ag = prof.get("agencies", {})
    code = (rec.get("agency_code") or "").upper()
    if any(code.startswith(p) for p in ag.get("boost", [])):
        total += ag.get("boost_points", 1)
    elif code and not any(code.startswith(p) for p in ag.get("neutral", [])) and rec["source"] in ("grants.gov", "simpler.grants.gov"):
        total -= ag.get("other_penalty", 0)
    ex = prof.get("exclude", {})
    flags = [f"excluded term in title: '{t}'" for t in ex.get("title_terms", []) if t in title]
    codes = rec.get("eligibility_codes")
    if codes and ex.get("eligible_codes") and not set(codes) & set(ex["eligible_codes"]):
        flags.append("eligibility codes exclude your applicant type")
    if flags:
        total -= ex.get("penalty", 5)
    distinct = len(set(hits["a"]) | set(hits["b"]))
    th = prof.get("thresholds", {})
    rec.update(score=total, hits=hits, flags=flags,
               scored_on="title+text" if rec.get("text") else "title only")
    if rec["source"] != "grants.gov" and rec["evidence"] == "page" and not distinct and not hits["c"]:
        rec["bucket"] = "low"
    elif flags:
        rec["bucket"] = "filtered"
    elif total >= th.get("strong_min_score", 6) and distinct >= th.get("strong_min_distinct_terms", 2):
        rec["bucket"] = "strong"
    elif total >= th.get("possible_min_score", 3) and (distinct >= 1 or title_hit):
        rec["bucket"] = "possible"
    else:
        rec["bucket"] = "low"


# ------------------------------------------------------------------ plan / check
def channel_status(ch: dict) -> str:
    if not ch.get("enabled", True):
        return "disabled"
    if ch.get("handler") == "browser" and not playwright_available():
        return "needs Playwright (falls back to manual)"
    env = ch.get("key_env")
    if env and not get_secret(env):
        return f"needs {env}"
    if ch.get("means") in ("email", "alert") and not ch.get("senders"):
        return "sender not recorded (subscribe, then record sender)"
    return "ready"


def cmd_plan(prof: dict, args) -> int:
    sched = prof.get("schedule", {})
    print(f"# Monitoring plan for {prof.get('meta', {}).get('owner', 'this profile')}\n")
    print(f"Scan cadence: {sched.get('scan_every', 'weekly')} (window {sched.get('window_days', 8)} days). "
          f"Email sweep: {sched.get('email_sweep', 'each scan, via an email connector if available')}.")
    labels = prof.get("email_sweep", {}).get("labels", [])
    print(f"Email labels swept: {', '.join(labels) if labels else 'none recorded'}.\n")
    print("| Channel | Covers | Means | Checked | Status |")
    print("|---|---|---|---|---|")
    order = {"api": 0, "rss": 1, "sitemap": 2, "web": 3, "browser": 4, "email": 5, "alert": 6, "manual": 7}
    rows = sorted(prof["channel"], key=lambda c: (not c.get("enabled", True), order.get(c.get("means", ""), 9)))
    for ch in rows:
        means = MEANS_LABEL.get(ch.get("means", ""), ch.get("means", ""))
        if ch.get("means") in ("email", "alert") and ch.get("senders"):
            means += f" from {', '.join(ch['senders'])}"
        print(f"| {ch.get('name', ch['id'])} | {ch.get('covers', '')} | {means} | {ch.get('frequency', 'each scan')} | {channel_status(ch)} |")
    todo = [c for c in prof["channel"] if c.get("enabled", True) and c.get("means") in ("email", "alert")
            and not c.get("senders")]
    if todo:
        print("\n## Email lists and alerts still to set up\n")
        for c in todo:
            if c.get("signup"):
                how = f"subscribe at {c['signup']}"
            elif c.get("setup"):
                how = f"set it up following {c['setup']}"
            elif c.get("signup_hint"):
                how = f"no sign-up link known yet, so {c['signup_hint']}"
            else:
                how = ("no sign-up link known yet, so follow 'When no sign-up link is known' "
                       "in references/email-lists.md")
            print(f"- {c.get('name', c['id'])}: {how}, then record the sender address in channel '{c['id']}'.")
    kw = prof.get("keywords", {})
    print(f"\nKeywords: {len(kw.get('tier_a', []))} core, {len(kw.get('tier_b', []))} adjacent, "
          f"{len(kw.get('tier_c', []))} program/mechanism terms. API queries: {len(prof.get('queries', {}).get('api', []))}.")
    return 0


def cmd_credentials(prof: dict) -> int:
    """Machine-readable credential report for any agent host. Prints no secret values."""
    enabled = {c["id"] for c in prof["channel"] if c.get("enabled", True)}
    report = []
    for spec in load_credential_specs():
        val, source = resolve_secret(spec["name"])
        needed = [c for c in spec.get("used_by_channels", []) if c in enabled]
        report.append({
            "name": spec["name"], "secret": spec.get("secret", True), "required": spec.get("required", False),
            "resolved": bool(val), "source": source, "needed_by_enabled_channels": needed,
            "purpose": spec.get("purpose", ""), "sent_to_hosts": spec.get("sent_to_hosts", []),
            "obtain": spec.get("obtain", ""), "without_it": spec.get("without_it", ""),
        })
    print(json.dumps({"credentials_file": str(CREDENTIALS_FILE), "credentials": report}, indent=1))
    return 0


def cmd_check(prof: dict, args) -> int:
    ctx = {"since_days": 30, "log": []}
    for ch in prof["channel"]:
        if args.channel and ch["id"] != args.channel:
            continue
        if not ch.get("enabled", True) and not args.channel:
            continue
        h = HANDLERS.get(ch.get("handler", ""))
        if not h:
            print(f"- {ch['id']}: {MEANS_LABEL.get(ch.get('means'), ch.get('means'))}, nothing to test automatically")
            continue
        test = dict(ch)
        if ch.get("handler") in ("grants_gov", "simpler"):
            test["queries"] = ["research"]  # generic term, so the test checks reachability, not fit
        if ch.get("handler") == "sam":
            test["max_requests_per_run"] = 1
        n0 = len(ctx["log"])
        items = h(test, prof, ctx)
        msgs = "; ".join(ctx["log"][n0:])
        print(f"- {ch['id']}: {'OK' if items else 'CHECK'} ({len(items)} items) {msgs}")
    return 0


# ------------------------------------------------------------------ scan
def load_state(p: Path | None) -> dict:
    if p and p.exists():
        return json.loads(p.read_text())
    return {"seen": {}, "last_run": {}, "page_fingerprints": {}}


def due(ch: dict, state: dict) -> bool:
    every = {"each scan": 0, "daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30}.get(ch.get("frequency", "each scan"), 0)
    last = state.get("last_run", {}).get(ch["id"])
    return not last or (dt.date.today() - dt.date.fromisoformat(last)).days >= every


def render(items: list[dict], ctx: dict, prof: dict, args, manual: list[dict]) -> str:
    lines = [f"# Funding scan, {dt.date.today().isoformat()}", "",
             f"Profile: {ctx['profile']}. Window: last {args.since_days} days. "
             f"State: {args.state or 'none (window-based, may repeat items)'}.", ""]
    for key, label in [("strong", "Strong fit"), ("possible", "Possible fit"), ("low", "Low relevance"),
                       ("filtered", "Filtered out (audit these)")]:
        grp = sorted([r for r in items if r["bucket"] == key], key=lambda r: -r["score"])
        lines += [f"## {label} ({len(grp)})", ""]
        for r in grp:
            if key in ("low", "filtered"):
                fl = f" [{'; '.join(r['flags'])}]" if r["flags"] else ""
                lines.append(f"- {r['title']} ({r['agency'] or r['channel']}, {r['number'] or r['evidence']}){fl} {r['url']}")
                continue
            lines.append(f"### {r['title']}")
            lines.append(f"- Agency: {r['agency'] or 'n/a'} | Number: {r['number'] or 'n/a'} | Type: {r['doc_type']} | Evidence: {r['evidence']} ({r['channel']})")
            lines.append(f"- Posted: {r['posted'] or 'not given'} | Close/deadlines: {r['close'] or 'not given'}")
            for f, lab in (("response_desc", "Deadline note"), ("instrument", "Instrument"),
                           ("award_ceiling", "Award ceiling"), ("eligibility_note", "Eligibility (source text)")):
                if r.get(f):
                    lines.append(f"- {lab}: {r[f]}")
            lines.append(f"- Score {r['score']} ({r['scored_on']}). A: {', '.join(r['hits']['a']) or '-'} | B: {', '.join(r['hits']['b']) or '-'} | C: {', '.join(r['hits']['c']) or '-'}")
            lines.append(f"- {r['url']}")
            lines.append("")
        lines.append("")
    if manual:
        lines += ["## Channels for the email sweep or manual check", ""]
        for ch in manual:
            s = f" from {', '.join(ch['senders'])}" if ch.get("senders") else ""
            lines.append(f"- {ch.get('name', ch['id'])}: {MEANS_LABEL.get(ch['means'], ch['means'])}{s}")
        lines.append("")
    lines += ["## Run log", ""] + [f"- {m}" for m in ctx["log"]]
    return "\n".join(lines) + "\n"


_NUM_RX = re.compile(
    r"\b(DE-FOA-\d{7}|LAB-\d{2}-\d{3,5}|(?:NSF|PD)\s?\d{2}-\d{3,4}|(?:RFA|PAR|PAS|PA|NOT)-[A-Z]{2}-\d{2}-\d{3}"
    r"|HR\d{7}[A-Z]?\d{0,4}|W911NF-?\d{2}-?S-?\d{4}|N0001\d{2}-?\d{2}-?S-?[A-Z]{0,2}-?\d{3,4})\b", re.I)


def _canon_keys(r: dict) -> list[str]:
    keys = []
    m = re.search(r"grants\.gov/search-results-detail/(\d+)", r.get("url", ""))
    if m:
        keys.append(f"gg:{m.group(1)}")
    if r["source"] == "grants.gov":
        keys.append(f"gg:{r['id']}")
    m = re.search(r"sam\.gov/(?:.*/)?opp/([0-9a-f]{32})", r.get("url", ""))
    if m:
        keys.append(f"sam:{m.group(1)}")
    num = r.get("number") or ""
    if not num:
        m = _NUM_RX.search(f"{r.get('title', '')} {r.get('url', '')}")
        if m:
            num = r["number"] = m.group(1).upper()
    if num:
        keys.append("num:" + re.sub(r"[\s-]", "", num).upper())
    t = re.sub(r"[^a-z0-9]", "", (r.get("title") or "").lower())
    if len(t) >= 25:
        keys.append("title:" + t)
    return keys


def dedupe(items: list[dict]) -> list[dict]:
    """Merge records that share a Grants.gov id, SAM notice id, opportunity number, or a long
    normalized title. API records are kept in preference to feed, email, or page records."""
    rank = {"API": 0, "feed": 1, "page": 2}
    items = sorted(items, key=lambda r: rank.get(r.get("evidence", ""), 3))
    index: dict[str, dict] = {}
    out = []
    for r in items:
        keys = _canon_keys(r)
        hit = next((index[k] for k in keys if k in index), None)
        if hit:
            hit.setdefault("also_in", []).append(r["channel"])
            for f in ("close", "text", "posted", "number"):
                if not hit.get(f) and r.get(f):
                    hit[f] = r[f]
        else:
            out.append(r)
            hit = r
        for k in keys:
            index.setdefault(k, hit)
    return out


def cmd_scan(prof: dict, args) -> int:
    ctx = {"since_days": args.since_days, "log": [], "profile": str(args.profile_path)}
    state = load_state(args.state)
    items, manual = [], []
    for ch in prof["channel"]:
        if not ch.get("enabled", True):
            continue
        h = HANDLERS.get(ch.get("handler", ""))
        if not h:
            manual.append(ch)
            continue
        if args.state and not due(ch, state):
            ctx["log"].append(f"{ch['id']}: not due (frequency {ch.get('frequency')})")
            continue
        items += h(ch, prof, ctx)
        state.setdefault("last_run", {})[ch["id"]] = dt.date.today().isoformat()

    deduped = dedupe(items)
    items = deduped
    for r in items:
        score(r, prof)
    if args.details:
        enrich_grants_gov([r for r in sorted(items, key=lambda r: -r["score"]) if r["bucket"] != "filtered"],
                          ctx, args.detail_limit)
        for r in items:
            score(r, prof)

    # Channels such as limited-submission lists can ask that their items never sink to "low".
    floors = {c["id"]: c["min_bucket"] for c in prof["channel"] if c.get("min_bucket")}
    rank = {"filtered": 0, "low": 1, "possible": 2, "strong": 3}
    for r in items:
        f = floors.get(r["channel"])
        if f and rank.get(r["bucket"], 0) < rank[f] and r["bucket"] != "filtered":
            r["bucket"] = f
            r["flags"] = r.get("flags", [])

    if args.state:
        before = len(items)
        items = [r for r in items if r["uid"] not in state["seen"]] if not args.include_seen else items
        ctx["log"].append(f"state: {before - len(items)} previously seen items suppressed")
        now = dt.datetime.now().isoformat(timespec="seconds")
        for r in items:
            state["seen"].setdefault(r["uid"], now)
        for cid, fp in ctx.get("page_fingerprints", {}).items():
            old = state.setdefault("page_fingerprints", {}).get(cid)
            if old and old != fp:
                ctx["log"].append(f"{cid}: page content changed since last run")
            state["page_fingerprints"][cid] = fp
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps(state, indent=1))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    (args.out_dir / f"funding-scan-{stamp}.md").write_text(render(items, ctx, prof, args, manual))
    (args.out_dir / f"funding-scan-{stamp}.json").write_text(json.dumps(items, indent=1, default=str))
    counts = {b: sum(r["bucket"] == b for r in items) for b in ("strong", "possible", "low", "filtered")}
    print(json.dumps({"out_dir": str(args.out_dir), "counts": counts, "log": ctx["log"]}, indent=1))
    return 0


def cmd_init(args) -> int:
    out = Path(args.out).expanduser()
    if out.exists() and not args.force:
        sys.exit(f"{out} exists. Use --force to overwrite.")
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEMPLATE, out)
    print(f"Wrote {out}. Edit it (or run the setup conversation) before scanning.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init")
    pi.add_argument("--out", default=str(USER_DIR / "profile.toml"))
    pi.add_argument("--force", action="store_true")
    sub.add_parser("plan")
    sub.add_parser("credentials", help="report declared secrets and whether each resolves (never values)")
    pc = sub.add_parser("check")
    pc.add_argument("--channel", default=None, help="test one channel id, even if disabled")
    ps = sub.add_parser("scan")
    ps.add_argument("--since-days", type=int, default=None)
    ps.add_argument("--state", type=Path, default=None)
    ps.add_argument("--details", action="store_true")
    ps.add_argument("--detail-limit", type=int, default=150)
    ps.add_argument("--include-seen", action="store_true")
    ps.add_argument("--out-dir", type=Path, default=Path("."))
    args = ap.parse_args()
    if args.cmd == "init":
        return cmd_init(args)
    load_dotenv()
    args.profile_path = find_profile(args.profile)
    prof = load_profile(args.profile_path)
    if args.cmd == "credentials":
        return cmd_credentials(prof)
    if args.cmd == "plan":
        return cmd_plan(prof, args)
    if args.cmd == "check":
        return cmd_check(prof, args)
    if args.since_days is None:
        args.since_days = int(prof.get("schedule", {}).get("window_days", 8))
    return cmd_scan(prof, args)


if __name__ == "__main__":
    sys.exit(main())
