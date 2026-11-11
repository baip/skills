#!/usr/bin/env python3
"""Read-only access to the local Zotero library for the wiki agent.

Policy (AGENTS.md §2.1): the wiki never modifies Zotero, whatever the API allows. This client
sends only GET requests to the local API (http://localhost:23119/api/), plus one read-only
Better BibTeX JSON-RPC method (item.citationkey). It never touches zotero.sqlite. Full text and rendered
pages go to a temp directory outside the wiki. The only wiki writes are `stamp`, which records a
provenance fingerprint in a source page's frontmatter.

Usage:
  zot.py status
  zot.py collections [--match TEXT]
  zot.py items COLLECTION_KEY [--recursive]
  zot.py search QUERY
  zot.py item ITEM_KEY                # metadata + attachments + notes/annotation counts
  zot.py notes ITEM_KEY               # child notes as plain text
  zot.py annotations ATTACHMENT_KEY   # highlights/comments on a PDF
  zot.py pdfpath KEY                  # one line per PDF: ATTACHMENT_KEY<TAB>ABSOLUTE_PATH<TAB>OK|MISSING; read it in place
  zot.py render KEY [--pages 3-7] [--dpi 150]  # PDF pages -> PNG files in a temp dir, to view as images
  zot.py fulltext ATTACHMENT_KEY      # text index -> temp dir, for searching/quoting only
  zot.py clean                        # delete the temp dir (rendered pages, text indexes)
  zot.py coverage COLLECTION_KEY [--recursive]    # per-item state: none / metadata / read / integrated
  zot.py fingerprint KEY              # v3 content hashes: biblio, abstract, pdf, notes, annotations
  zot.py stamp PAGE|CITEKEY|KEY [...] # record fingerprint; queues dependents first if a scientific part changed
                                      # (an argument that names no source page is an error, not a silent no-op)
  zot.py changed [--queue]            # source pages whose Zotero item changed since stamping; --queue adds review items to pending.md
"""
import datetime
import hashlib
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikimeta import (FP_PARTS, FP_VERSION, PENDING, atomic_write, dependents, load_pages,  # noqa: E402
                      parse_fingerprint, pending_items, propagate, queue_reviews, source_states)
import urllib.parse
import urllib.request

API = "http://localhost:23119/api/users/0"
BBT = "http://localhost:23119/better-bibtex/json-rpc"
BBT_READ_METHODS = {"item.citationkey"}  # the only RPC method this tool may call
PENDING_HEADER = """# Pending review

Pages whose synthesis must be re-checked against their sources. Items are added by
`zot.py changed --queue`, `zot.py stamp`, `review.py touched|since`, or by hand. Resolve an item with
`review.py done PAGE --outcome O --basis TEXT [--cause ID]` only after re-reading the page against its sources;
the resolution is kept in reviewed.md. Re-stamping a source does **not** clear its dependents.
`wikilint.py --strict` fails while items remain.

"""
WIKI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFS_GLOBS = ["~/Library/Application Support/Zotero/Profiles/*/prefs.js",  # macOS
               "~/.zotero/zotero/*/prefs.js",                             # Linux
               os.path.join(os.environ.get("APPDATA", "~"), "Zotero/Zotero/Profiles/*/prefs.js")]  # Windows


def zotero_pref(name):
    """A string preference from the Zotero profile's prefs.js (read only), or ''."""
    import glob
    for pattern in PREFS_GLOBS:
        for prefs in glob.glob(os.path.expanduser(pattern)):
            m = re.search(r'"' + re.escape(name) + r'",\s*"([^"]*)"', open(prefs, encoding="utf-8", errors="replace").read())
            if m:
                return m.group(1)
    return ""


# Zotero's data directory: $ZOTERO_DATA_DIR, else the profile's custom dataDir, else the default ~/Zotero.
DATA = os.environ.get("ZOTERO_DATA_DIR") or zotero_pref("extensions.zotero.dataDir") or os.path.expanduser("~/Zotero")
TMP = os.path.join(os.environ.get("TMPDIR", tempfile.gettempdir()), "zotero-wiki")


def get(path, **params):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)
    except OSError as e:
        sys.exit(f"Zotero local API unreachable ({e}). Is Zotero running with "
                 "Settings > Advanced > 'Allow other applications to communicate' on?")


def get_all(path, **params):
    out, start = [], 0
    while True:
        page = get(path, limit=100, start=start, **params)
        out += page
        if len(page) < 100:
            return out
        start += 100


def collections():
    cols = {c["key"]: c for c in get_all("/collections")}

    def path(c):
        p = [c["data"]["name"]]
        while c["data"]["parentCollection"]:
            c = cols[c["data"]["parentCollection"]]
            p.insert(0, c["data"]["name"])
        return "/".join(p)

    return {k: (path(c), c["meta"].get("numItems", 0), c["data"]["parentCollection"])
            for k, c in cols.items()}


def subtree(cols, key):
    keys = [key]
    for k, (_, _, parent) in cols.items():
        if parent == key:
            keys += subtree(cols, k)
    return keys


def first_author(d):
    cr = d.get("creators") or []
    return (cr[0].get("lastName") or cr[0].get("name", "")) if cr else ""


def fallback_citekey(d):
    """A key in Better BibTeX's default style (authorTitleWordsYear) when Zotero has none: the first creator's last
    name in lower case, the first three title words that are not function words (markup removed, accents folded,
    each word's first letter capitalized and the rest kept, so acronyms survive), and the year."""
    import unicodedata

    def ascii_fold(s):
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    # Better BibTeX's skip words (English prepositions, articles and conjunctions, plus common European ones)
    stop = set("""a ab aboard about above across after against al along amid among an and anti around as at before behind
        below beneath beside besides between beyond but by d da das de del dell dello dei degli della delle dem den der
        des despite die do down du during ein eine einem einen einer eines el en et except for from gli i il in inside
        into is l la las le les like lo los near nor of off on onto or over past per plus round save since so some sur
        than the through to toward towards un una unas uno unos under underneath une unlike until up upon versus via von
        while with within without yet zu zum""".split())
    author = re.sub(r"[^a-z-]", "", ascii_fold(first_author(d)).lower()).strip("-") or "anon"
    title = ascii_fold(re.sub(r"<[^>]+>", "", html.unescape(d.get("title", ""))))
    words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in re.split(r"[\s/:;,!?]+", title)]
    words = [w for w in words if w and w.lower() not in stop][:3]
    year = (re.search(r"\d{4}", d.get("date", "")) or [""])[0]
    return author + "".join(w[:1].upper() + w[1:] for w in words) + year


def citekey(item, fallback=False):
    """The item's citation key: Zotero 7's native field, an 'extra' line, Better BibTeX if installed, or, with
    fallback=True, a generated key (callers must then say it was generated)."""
    ck = item["data"].get("citationKey")
    if ck:
        return ck
    m = re.search(r"^Citation Key:\s*(\S+)", item["data"].get("extra", ""), re.M)
    if m:
        return m.group(1)
    method = "item.citationkey"
    assert method in BBT_READ_METHODS
    req = json.dumps({"jsonrpc": "2.0", "method": method,
                      "params": [[item["key"]]], "id": 1}).encode()
    try:
        r = urllib.request.Request(BBT, req, {"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=10) as f:
            ck = json.load(f)["result"].get(item["key"], "")
    except (OSError, ValueError, KeyError, AttributeError):
        ck = ""
    return ck or (fallback_citekey(item["data"]) if fallback else "")


def row(it):
    d, m = it["data"], it["meta"]
    return f'{it["key"]} | {m.get("parsedDate", "")[:4]} | {first_author(d)} | {d.get("title", "")}'


def ingested_keys():  # kept for relink-style callers
    keys = {}
    src = os.path.join(WIKI, "sources")
    for f in os.listdir(src) if os.path.isdir(src) else []:
        if f.endswith(".md"):
            m = re.search(r"^zotero_key:\s*(\w+)", open(os.path.join(src, f)).read(), re.M)
            if m:
                keys[m.group(1)] = f[:-3]
    return keys


def strip_html(s):
    s = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def cmd_status(a):
    it = get("/items/top", limit=1)
    if not it:
        print("OK: Zotero local API reachable; the library is empty")
        return
    lib = it[0]["library"]
    print(f"OK: Zotero local API reachable; library = {lib['name']} ({lib['type']}:{lib['id']})")


def match_collections(cols, query):
    """Collections whose path matches `query`, case-insensitively: every query word must start a word of the path
    (so "cement" finds "Materials/Cement" but not "Reinforcement"). If nothing matches, the closest paths by
    similarity are returned with fuzzy=True. Returns (keys, fuzzy)."""
    import difflib
    q = [w for w in re.split(r"[^a-z0-9]+", query.lower()) if w]

    def words(path):
        return [w for w in re.split(r"[^a-z0-9]+", path.lower()) if w]
    hits = [k for k, (p, _, _) in cols.items() if all(any(w.startswith(x) for w in words(p)) for x in q)]
    if hits or not q:
        return hits, False
    by_path = {p.lower(): k for k, (p, _, _) in cols.items()}
    leaf = {p.lower().rsplit("/", 1)[-1]: k for k, (p, _, _) in cols.items()}
    close = difflib.get_close_matches(query.lower(), list(by_path) + list(leaf), n=5, cutoff=0.6)
    return list(dict.fromkeys(by_path.get(c) or leaf[c] for c in close)), True


def cmd_collections(a):
    cols = collections()
    keys, fuzzy = match_collections(cols, a.match) if a.match else (list(cols), False)
    if a.match and not keys:
        print(f"(no collection matches {a.match!r}; run without --match to list all)")
        return
    if fuzzy:
        print(f"(no collection contains every word of {a.match!r}; closest by spelling, confirm with the user:)")
    elif a.match and not all(cols[k][0] == min((cols[j][0] for j in keys), key=len) or
                             cols[k][0].startswith(min((cols[j][0] for j in keys), key=len) + "/") for k in keys):
        print(f"(matches in more than one collection tree; confirm with the user which is meant:)")
    for k in sorted(keys, key=lambda k: cols[k][0].lower()):
        p, n, _ = cols[k]
        print(f"{k} | {n:4d} | {p}")


def cmd_items(a):
    keys = subtree(collections(), a.key) if a.recursive else [a.key]
    seen = set()
    for k in keys:
        for it in get_all(f"/collections/{k}/items/top"):
            if it["key"] not in seen:
                seen.add(it["key"])
                print(row(it))


def cmd_search(a):
    for it in get_all("/items/top", q=a.query, qmode="titleCreatorYear"):
        print(row(it))


def cmd_item(a):
    it = get(f"/items/{a.key}")
    d = it["data"]
    cols = collections()
    print(f"zotero_key: {it['key']}")
    ck = citekey(it)
    print(f"citekey: {ck}" if ck else f"citekey: {citekey(it, fallback=True)}  (generated: no native or Better BibTeX key)")
    print(f"item_type: {d.get('itemType')}")
    print(f"title: {d.get('title')}")
    print("authors: " + "; ".join(
        (c.get("lastName", "") + (", " + c["firstName"] if c.get("firstName") else "")) or c.get("name", "")
        for c in d.get("creators", [])))
    print(f"year: {it['meta'].get('parsedDate', '')[:4]}")
    print(f"venue: {d.get('publicationTitle') or d.get('proceedingsTitle') or d.get('repository') or d.get('publisher', '')}")
    for f in ("volume", "issue", "pages", "DOI", "url"):
        if d.get(f):
            print(f"{f.lower()}: {d[f]}")
    print("collections: " + "; ".join(cols[c][0] for c in d.get("collections", []) if c in cols))
    print("zotero_tags: " + ", ".join(t["tag"] for t in d.get("tags", [])))
    print(f"abstract: {d.get('abstractNote', '')}")
    print("children:")
    for c in get(f"/items/{a.key}/children"):
        cd = c["data"]
        if cd["itemType"] == "attachment":
            n_ann = len(get(f"/items/{c['key']}/children")) if cd.get("contentType") == "application/pdf" else 0
            print(f"  attachment {c['key']} | {cd.get('linkMode')} | {cd.get('contentType')} | "
                  f"{cd.get('filename') or cd.get('path') or cd.get('url', '')} | annotations={n_ann}")
        elif cd["itemType"] == "note":
            print(f"  note {c['key']} | {strip_html(cd.get('note', ''))[:80]!r}")


def cmd_notes(a):
    n = 0
    for c in get(f"/items/{a.key}/children"):
        if c["data"]["itemType"] == "note":
            n += 1
            print(f"--- note {c['key']} ---\n{strip_html(c['data']['note'])}\n")
    if not n:
        print(f"(no notes on {a.key})")


def cmd_annotations(a):
    n = 0
    for c in get_all(f"/items/{a.key}/children"):
        d = c["data"]
        if d["itemType"] != "annotation":
            continue
        n += 1
        print(f"[p.{d.get('annotationPageLabel', '?')}] {d.get('annotationType')} "
              f"{d.get('annotationColor', '')}: {d.get('annotationText', '').strip()}")
        if d.get("annotationComment"):
            print(f"    comment: {d['annotationComment'].strip()}")
    if not n:
        print(f"(no annotations on {a.key})")


def base_attachment_path():
    return zotero_pref("extensions.zotero.baseAttachmentPath")


def pdf_attachments(key):
    """(attachment key, absolute path, exists) for each PDF of an item, or for a PDF attachment key itself."""
    it = get(f"/items/{key}")
    atts = [it] if it["data"]["itemType"] == "attachment" else \
        [c for c in get(f"/items/{key}/children") if c["data"]["itemType"] == "attachment"]
    out = []
    for c in atts:
        d = c["data"]
        if d.get("contentType") != "application/pdf":
            continue
        if d["linkMode"] in ("imported_file", "imported_url"):
            path = os.path.join(DATA, "storage", c["key"], d["filename"])
        elif d["linkMode"] == "linked_file":
            path = d["path"]
            if path.startswith("attachments:"):
                path = os.path.join(base_attachment_path(), path[len("attachments:"):])
        else:
            continue
        out.append((c["key"], path, os.path.exists(path)))
    return out


def cmd_pdfpath(a):
    pdfs = pdf_attachments(a.key)
    if not pdfs:
        sys.exit("No PDF attachment.")
    for k, path, ok in pdfs:
        print(f"{k}\t{path}\t{'OK' if ok else 'MISSING'}")


def page_range(spec, n):
    """'4', '3-7', '5-' or None (all) -> (first, last), 1-based PDF page indices within 1..n."""
    if not spec:
        return 1, n
    m = re.fullmatch(r"(\d+)(?:-(\d*))?", spec.strip())
    if not m:
        sys.exit(f"--pages must look like 4, 3-7 or 5-, not {spec!r}")
    first = int(m.group(1))
    last = n if m.group(2) == "" else int(m.group(2) or first)
    if not 1 <= first <= last <= n:
        sys.exit(f"--pages {spec} is outside this PDF's pages 1-{n}")
    return first, last


def cmd_render(a):
    """Render PDF pages to PNG files outside the wiki, so any agent that can view an image file reads the page as
    printed (AGENTS.md §7). Overwrites earlier renders of the same pages; `clean` deletes them all."""
    missing = [t for t in ("pdftoppm", "pdfinfo") if shutil.which(t) is None]
    if missing:
        sys.exit(f"{' and '.join(missing)} not found: install poppler (macOS: brew install poppler; Debian/Ubuntu: "
                 "apt install poppler-utils). Without it, read the text index and record read_mode: text-index.")
    pdfs = [p for p in pdf_attachments(a.key) if p[2]]
    if not pdfs:
        sys.exit(f"No PDF file found for {a.key}; `zot.py pdfpath {a.key}` shows what Zotero records.")
    if len(pdfs) > 1:
        sys.exit("Several PDFs; pass one attachment key:\n" + "\n".join(f"{k}\t{p}" for k, p, _ in pdfs))
    att, path, _ = pdfs[0]
    info = subprocess.run(["pdfinfo", path], capture_output=True, text=True)
    m = re.search(r"^Pages:\s+(\d+)", info.stdout, re.M)
    if info.returncode or not m:
        sys.exit(f"pdfinfo could not read {path}: {(info.stderr or info.stdout).strip()}")
    n = int(m.group(1))
    first, last = page_range(a.pages, n)
    out = os.path.join(TMP, "pages", att)
    assert not os.path.abspath(out).startswith(WIKI + os.sep), "refusing to write inside the wiki"
    os.makedirs(out, exist_ok=True)
    r = subprocess.run(["pdftoppm", "-r", str(a.dpi), "-f", str(first), "-l", str(last), "-png", path,
                        os.path.join(out, "p")], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"pdftoppm failed: {r.stderr.strip()}")
    print(f"{att}: pages {first}-{last} of {n} at {a.dpi} dpi; view each file as an image (PAGE<TAB>PATH):")
    for f in sorted(os.listdir(out)):
        num = re.fullmatch(r"p-0*(\d+)\.png", f)
        if num and first <= int(num.group(1)) <= last:
            print(f"{num.group(1)}\t{os.path.join(out, f)}")


def cmd_clean(a):
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"removed {TMP}")


def cmd_fulltext(a):
    ft = get(f"/items/{a.key}/fulltext")
    if not ft or "content" not in ft:
        sys.exit("No full-text index for this attachment (re-index it in Zotero).")
    lines = ft["content"].splitlines()
    os.makedirs(TMP, exist_ok=True)
    out = os.path.join(TMP, f"{a.key}.txt")
    assert not os.path.abspath(out).startswith(WIKI + os.sep), "refusing to write inside the wiki"
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print(f"{out}  (indexed pages {ft.get('indexedPages')}/{ft.get('totalPages')}, {len(lines)} lines)")


def cmd_coverage(a):
    keys = subtree(collections(), a.key) if a.recursive else [a.key]
    states = source_states()
    mark = {"metadata": "m", "read": "r", "integrated": "x"}
    seen, counts = set(), {}
    for k in keys:
        for it in get_all(f"/collections/{k}/items/top"):
            if it["key"] in seen:
                continue
            seen.add(it["key"])
            state = states.get(it["key"], (None, "none"))[1]
            counts[state] = counts.get(state, 0) + 1
            print(f"[{mark.get(state, ' ')}] {row(it)}")
    print(f"\n{len(seen)} items: " + ", ".join(f"{counts.get(s, 0)} {s}" for s in ("integrated", "read", "metadata", "none")))
    print("legend: [x] integrated  [r] read, not yet integrated  [m] metadata/abstract only  [ ] no page")


def _h(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]


BIBLIO_FIELDS = ("title", "creators", "date", "DOI", "itemType", "publicationTitle", "proceedingsTitle",
                 "bookTitle", "volume", "issue", "pages", "publisher", "repository", "archiveID", "url")
V2_META_FIELDS = ("title", "creators", "date", "DOI", "itemType", "abstractNote", "publicationTitle",
                  "proceedingsTitle", "bookTitle", "volume", "issue", "pages", "publisher", "repository",
                  "archiveID", "url")
SCIENTIFIC = {"abstract", "pdf", "notes", "ann", "meta"}  # v2 'meta' mixes abstract and bibliography: treat as content


def library_version():
    """Zotero's library-wide version (Last-Modified-Version); it increases on every change in the library.
    A missing or non-integer header makes snapshot consistency unknowable, so it is an error, never a value
    (two missing headers must not compare equal and pass as "unchanged")."""
    try:
        with urllib.request.urlopen(API + "/items/top?limit=1&format=keys", timeout=15) as r:
            raw = r.headers.get("Last-Modified-Version")
    except OSError as e:
        sys.exit(f"Zotero local API unreachable ({e}).")
    if raw is None or not str(raw).strip().isdigit():
        sys.exit(f"Zotero returned no valid Last-Modified-Version ({raw!r}); cannot verify a consistent snapshot.")
    return int(raw)


def _collect(key):
    """Raw Zotero content an ingest depends on: item data, PDF attachments, notes, annotations."""
    d = get(f"/items/{key}")["data"]
    pdfs, notes, ann = [], [], []
    for c in get_all(f"/items/{key}/children"):
        cd = c["data"]
        if cd["itemType"] == "note":
            notes.append((c["key"], cd.get("note", "")))
        elif cd["itemType"] == "attachment" and cd.get("contentType") == "application/pdf":
            ident = cd.get("md5") or f"nomd5:{cd.get('linkMode')}:{cd.get('path') or cd.get('filename') or ''}:{cd.get('mtime') or ''}"
            pdfs.append((c["key"], ident))
            for x in get_all(f"/items/{c['key']}/children"):
                xd = x["data"]
                if xd["itemType"] == "annotation":
                    ann.append((c["key"], x["key"], xd.get("annotationType", ""), xd.get("annotationText", ""),
                                xd.get("annotationComment", ""), xd.get("annotationColor", ""),
                                xd.get("annotationPageLabel", ""), xd.get("annotationPosition", ""),
                                xd.get("annotationSortIndex", "")))
    return d, pdfs, notes, ann


def snapshot(key, retries=3):
    """One consistent read of an item: collect it between two reads of the library version, and retry if
    anything in the library changed meanwhile. Every comparison *and* the fingerprint that replaces a
    baseline derive from the same snapshot, so a change can never fall between them."""
    for _ in range(retries):
        before = library_version()
        raw = _collect(key)
        after = library_version()
        if not isinstance(before, int) or not isinstance(after, int):  # defense in depth: never trust None == None
            sys.exit(f"Library version unknown while reading {key}; cannot verify a consistent snapshot.")
        if after == before:
            return raw
    sys.exit(f"Zotero kept changing while {key} was being read; try again when it is idle.")


def fingerprint_from(raw, version=FP_VERSION):
    """Content hashes of a snapshot. Item versions are avoided on purpose: they also change when tags or
    collections change, which needs no re-read.
    v3 parts: biblio (bibliographic and venue fields; alone = metadata refresh), abstract, pdf (each PDF bound
    to its attachment key: MD5, or link mode + path + mtime), notes, ann (with page label and position).
    v2 (legacy, only to compare old baselines): meta = bibliographic fields + abstract, then pdf, notes, ann."""
    d, pdfs, notes, ann = raw
    tail = {"pdf": _h(sorted(pdfs)) if pdfs else "none",
            "notes": _h(sorted(notes)) if notes else "none",
            "ann": _h(sorted(ann)) if ann else "none"}
    if version == "v2":
        return {"meta": _h({f: d.get(f) for f in V2_META_FIELDS}), **tail}
    return {"biblio": _h({f: d.get(f) for f in BIBLIO_FIELDS}),
            "abstract": _h(d["abstractNote"]) if d.get("abstractNote") else "none", **tail}


def fingerprint(key, version=FP_VERSION):
    return fingerprint_from(snapshot(key), version)


def fp_string(fp, version=FP_VERSION):
    return version + " " + " ".join(f"{k}:{fp[k]}" for k in FP_PARTS[version])


def fp_parse(s):
    """{part: hash} of a complete fingerprint in any known format, else None (incomplete or unreadable)."""
    r = parse_fingerprint(s)
    return r[1] if r else None


def compare(stored, raw):
    """Compare a stored fingerprint with a snapshot, *using the stored fingerprint's own algorithm*.
    Returns (status, diff, kind): status 'ok' | 'changed' | 'incomplete'; kind None | 'metadata refresh' |
    'scientific re-read'. An incomplete baseline certifies nothing, so it counts as a scientific change."""
    if isinstance(raw, str):  # a Zotero key (convenience for callers and tests)
        raw = snapshot(raw)
    r = parse_fingerprint(stored)
    if r is None:
        return "incomplete", [], "scientific re-read"
    version, old = r
    new = fingerprint_from(raw, version)
    diff = [k for k in FP_PARTS[version] if old[k] != new[k]]
    if not diff:
        return "ok", [], None
    return "changed", diff, ("scientific re-read" if SCIENTIFIC & set(diff) else "metadata refresh")


def review_entries(pages, name, diff, kind, today, new_fp):
    """(page, cause, note) review items for a source that changed in Zotero. The cause names the source
    and the fingerprint revision under review. Metadata refresh: the source only. Scientific: the source,
    its evidence dependents, and (through chains of source pages that quote each other) theirs."""
    what = ", ".join(diff) if diff else "baseline fingerprint incomplete or unreadable"
    cause = f"zotero:{name}@{_h(new_fp)}"
    if kind == "metadata refresh":
        return [(name, cause, f"bibliographic metadata changed in Zotero ({what}): refresh frontmatter, then `zot.py stamp {name}` · {today}")]
    out = [(name, cause, f"source changed in Zotero ({what}): re-read and update the page · {today}")]
    for d, via in sorted(propagate(pages, name).items()):
        how = f"uses [[{name}]] as evidence" if via is None else f"uses [[{via}]], which quotes [[{name}]]"
        out.append((d, cause, f"{how}; [[{name}]] changed in Zotero ({what}): re-check · {today}"))
    return out


def cmd_fingerprint(a):
    print(fp_string(fingerprint(a.key)))


def _source_pages(pages=None):
    for name, versions in (pages or load_pages()).items():
        pg = versions[0]
        if pg["dir"] == "sources" and pg["fields"].get("zotero_key"):
            yield name, pg


def cmd_stamp(a):
    """Record the v3 fingerprint of one consistent snapshot. Before replacing a previous baseline, compare
    it (with its own algorithm) against that same snapshot; if a scientific part changed, or the baseline
    was incomplete, queue the dependents first. Safe at any point, and under concurrency (locked queue).
    In batch mode readers stamp only the pages they create (no baseline, nothing to queue).

    A page is named by its filename, its zotero_key or its citekey: after a re-ingest the citekey can
    differ from the filename, which the page keeps (AGENTS.md §4). An argument that matches nothing is
    an error, not a silent no-op."""
    today = datetime.date.today().isoformat()
    wanted = set(a.keys)
    matched = set()
    pages = load_pages()
    for name, pg in _source_pages(pages):
        ids = {name, pg["fields"]["zotero_key"], pg["fields"].get("citekey")} - {None}
        hit = ids & wanted
        if not (hit or "ALL" in wanted):
            continue
        matched |= hit
        raw = snapshot(pg["fields"]["zotero_key"])
        fp = fp_string(fingerprint_from(raw))
        stored = pg["fields"].get("zotero_fingerprint")
        queued = 0
        if stored:  # a page with no baseline at all is a first ingest: nothing can be stale yet
            status, diff, kind = compare(stored, raw)
            if kind == "scientific re-read":
                deps = [e for e in review_entries(pages, name, diff, kind, today, fp) if e[0] != name]
                queued = queue_reviews(deps, PENDING_HEADER)
        text = open(pg["path"]).read()
        head, sep, rest = text.partition("\n---\n")
        head = re.sub(r"^(zotero_fingerprint|zotero_checked):.*\n?", "", head + "\n", flags=re.M).rstrip("\n")
        head = re.sub(r"^(zotero_uri:.*)$", lambda m: f'{m.group(1)}\nzotero_fingerprint: "{fp}"\nzotero_checked: {today}',
                      head, count=1, flags=re.M)
        atomic_write(pg["path"], head + sep + rest)
        print(f"stamped {name}: {fp}" + (f"  (queued {queued} dependent review(s) in pending.md)" if queued else ""))
    unmatched = sorted(wanted - matched - {"ALL"})
    if unmatched:
        sys.exit(f"stamped nothing for: {', '.join(unmatched)}. A source page is named by its filename, its "
                 f"zotero_key or its citekey; `zot.py changed` lists the pages that exist.")


def cmd_changed(a):
    """List source pages whose Zotero item changed since `stamp`, or whose baseline is incomplete. With
    --queue, record review items (with causes) in pending.md."""
    pages = load_pages()
    today = datetime.date.today().isoformat()
    queue, n = [], 0
    for name, pg in _source_pages(pages):
        stored = pg["fields"].get("zotero_fingerprint")
        if not stored:
            print(f"UNSTAMPED  {name}: run `zot.py stamp {name}`")
            n += 1
            continue
        raw = snapshot(pg["fields"]["zotero_key"])
        status, diff, kind = compare(stored, raw)
        if status == "ok":
            continue
        n += 1
        entries = review_entries(pages, name, diff, kind, today, fp_string(fingerprint_from(raw)))
        label = "INCOMPLETE" if status == "incomplete" else "CHANGED   "
        print(f"{label} {name} ({pg['fields']['zotero_key']}): {', '.join(diff) or 'baseline unreadable'} -> {kind}; "
              f"to review: {', '.join(p for p, _, _ in entries if p != name) or 'none'}")
        queue += entries
    print(f"{n} need attention")
    if a.queue and queue:
        print(f"queued {queue_reviews(queue, PENDING_HEADER)} item(s) in pending.md")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("collections"); s.add_argument("--match")
    s = sub.add_parser("items"); s.add_argument("key"); s.add_argument("--recursive", action="store_true")
    s = sub.add_parser("search"); s.add_argument("query")
    s = sub.add_parser("item"); s.add_argument("key")
    s = sub.add_parser("notes"); s.add_argument("key")
    s = sub.add_parser("annotations"); s.add_argument("key")
    s = sub.add_parser("pdfpath"); s.add_argument("key")
    s = sub.add_parser("render"); s.add_argument("key"); s.add_argument("--pages"); s.add_argument("--dpi", type=int, default=150)
    s = sub.add_parser("fulltext"); s.add_argument("key")
    sub.add_parser("clean")
    s = sub.add_parser("coverage"); s.add_argument("key"); s.add_argument("--recursive", action="store_true")
    s = sub.add_parser("fingerprint"); s.add_argument("key")
    s = sub.add_parser("stamp"); s.add_argument("keys", nargs="+", help="page names, citekeys, Zotero keys, or ALL")
    s = sub.add_parser("changed"); s.add_argument("--queue", action="store_true", help="add review items to pending.md")
    a = p.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
