#!/usr/bin/env python3
"""Structural lint for the wiki (AGENTS.md §8.4). Read-only; prints a report and exits 1 on errors.
Usage: wikilint.py [--strict] [--since REV]. With --since, warnings are counted by category and listed only for
pages changed since git REV (errors are always listed), so the output stays short as the wiki grows.

Errors (must be fixed):
  frontmatter   unparseable frontmatter, missing or mistyped fields, values outside the permitted sets
  identity      duplicate doc_id, a file listed by two source pages, a page name used in two folders or clashing
                with a root file
  broken link   wikilink to a page that does not exist (log.md and reviewed.md are history and not checked)
  sources       sources: lists an unknown page, misses a cited source, or lists one never cited
  callout       [!contradiction] without a status (open|scope|superseded|corrected); a [!reuse] block outside a
                source page, or without "label · locator" in its header
  pending       a pending.md checkbox line that cannot be read, or a completed item left in place
  ledger        a reviewed.md line that cannot be read, has an unknown outcome, or lacks a basis
  provenance    a read source page without doc_fingerprint / doc_checked, or a fingerprint that does not match files:
  authorship    explicitly uncredited work lacks evidence or contradicts a nonempty author list
  consistency   fields that contradict each other (read_depth vs read_mode, read_file not in files:, project: not a
                project page, version_of, part_of)
Warnings (judgment calls; `--strict` makes them fail too, which is the ingest completion gate, AGENTS.md §8.2):
  index drift   page not listed in index.md
  summary       page without a one-line `summary:` field, the editorial text of its index line (catalog.py)
  size          page over 40,000 bytes: split a concept, entity, topic or project page into a parent and child pages
                by sub-question, and a source page into part notes (`type: source-part`), because every integration,
                review or audit reads the whole page (AGENTS.md §11); an analysis kept as a frozen historical
                record (`frozen: true`) is exempt
  orphan        page with no inbound link (besides index/log)
  stale ↗ link  ↗ file link to a document that now has a source page (run tools/relink.py)
  catalog       a generated field is out of date: a sources: list or index.md counts/metadata (run tools/catalog.py)
  unintegrated  source read but not cited in the text of any project, concept, entity or topic page; a page whose
                `version_of:` target is cited counts as integrated (§4 cites the later version of a document)
  claim status  a bullet under a source page's `## Claims and results` without [proposed], [preliminary], [reported]
                or [published] (AGENTS.md §6.8)
  pending       an open item in pending.md (pages awaiting a synthesis review)
  tools         a tools/*.py file differs from the installed project-llm-wiki skill, or the skill is not installed
                (tools are changed in the skill first, then copied in with init_wiki.py --upgrade-tools; AGENTS.md §12)
"""
import datetime
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikimeta import WIKI, DIRS, FP_VERSION, ledger_parse, load_pages, links, parse_fingerprint, pending_parse, source_states  # noqa: E402

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PARTIAL_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
SIZE_LIMIT = 40000  # bytes: about 10k tokens, read whole by every integration, review or audit of the page
SIZE_DIRS = ("sources", "projects", "concepts", "entities", "topics", "analyses")  # analyses with `frozen: true` are exempt
DOC_ID = re.compile(r"^[0-9a-f]{8}$")
AUTHOR = re.compile(r"^(et al\.|[^,]+, [^,]+)$")  # "Last, F." or "et al."
ROOT_FILES = {"index", "log", "pending", "reviewed", "AGENTS", "CLAUDE", "llm-wiki"}
HISTORY_FILES = {"log", "reviewed"}  # append-only records: their links are history, not navigation
DOC_KINDS = {"proposal", "proposal-section", "pre-proposal", "white-paper", "report", "presentation", "paper",
             "thesis", "review", "solicitation", "correspondence", "plan", "other"}
ALLOWED = {
    "type": {"source", "source-part", "project", "concept", "entity", "topic", "analysis"},
    "frozen": {"true"},
    "read_depth": {"full", "partial", "metadata-only"},
    "read_mode": {"rendered", "source", "text-index", "mixed", "none"},
    "author_status": {"uncredited"},
    "doc_kind": DOC_KINDS,
    "my_role": {"PI", "co-PI", "senior-personnel", "lead-author", "co-author", "contributor", "reviewer", "recipient",
                "none"},
    "status": {"idea", "in-preparation", "submitted", "pending", "awarded", "declined", "withdrawn", "active",
               "completed", "unknown"},
    "entity_kind": {"model", "method", "software", "dataset", "benchmark", "instrument", "material", "organism", "site",
                    "group", "person", "agency", "program", "facility", "institution", "course"},
}
REQUIRED = {
    "source": ["title", "authors", "year", "doc_kind", "doc_id", "files", "read_depth", "read_mode", "ingested", "updated"],
    "project": ["sponsor", "status", "sources", "created", "updated"],
    "concept": ["sources", "created", "updated"],
    "entity": ["entity_kind", "sources", "created", "updated"],
    "topic": ["sources", "created", "updated"],
    "analysis": ["question", "sources", "created"],
    "source-part": ["part_of", "created", "updated"],
}
LISTS = {"authors", "corporate_authors", "files", "sources", "tags", "aliases", "team", "folders"}
STRINGS = {"title", "read_file", "doc_fingerprint", "version_of", "part_of", "entity_kind", "doc_kind",
           "read_depth", "read_mode", "author_status", "project", "sponsor", "program", "solicitation", "status",
           "my_role", "award_number", "period", "budget", "question"}
TOOLS = ("catalog.py", "docs.py", "relink.py", "review.py", "search.py", "split.py", "test_tools.py", "wikilint.py",
         "wikimeta.py")
MODES_FOR_DEPTH = {"full": {"rendered", "source", "text-index", "mixed"}, "partial": {"rendered", "source", "text-index", "mixed"},
                   "metadata-only": {"none"}}
CONTRA = re.compile(r"^> \[!contradiction(\|([a-z-]+))?\]", re.M)
CONTRA_STATUS = {"open", "scope", "superseded", "corrected"}
REUSE = re.compile(r"^> \[!reuse\]([^\n]*)", re.M)
AUTHOR_REASON = re.compile(r"No credited author: *\S", re.I)
FLINK = re.compile(r"↗\]\((file://[^)\s]+)\)")
CLAIM_STATUS = re.compile(r"^\s*[-*+] \[(proposed|preliminary|reported|published)\]")


def check_fields(name, f, errs):
    typ = f.get("type")
    if not isinstance(typ, str) or typ not in REQUIRED:
        errs.append(("frontmatter", f"{name}: missing/unknown type {typ!r}"))
        return
    for field in REQUIRED[typ]:
        if field == "authors" and f.get(field) == [] and (f.get("read_depth") == "metadata-only" or
                (f.get("read_depth") in ("full", "partial") and f.get("author_status") == "uncredited")):
            continue
        if f.get(field) in (None, "", [], {}):
            errs.append(("frontmatter", f"{name}: missing {field}"))
    for field, allowed in ALLOWED.items():
        if field in f and (not isinstance(f[field], str) or f[field] not in allowed):
            errs.append(("frontmatter", f"{name}: {field}={f[field]!r} not in {sorted(allowed)}"))
    for field in LISTS:
        if field in f and not isinstance(f[field], list):
            errs.append(("frontmatter", f"{name}: {field} must be a [list]"))
    for field in STRINGS:
        if field in f and not isinstance(f[field], str):
            errs.append(("frontmatter", f"{name}: {field} must be a single string, not {type(f[field]).__name__}"))
    for field in ("ingested", "updated", "created", "doc_checked"):
        if field in f:
            try:
                ok = bool(DATE.match(str(f[field]))) and datetime.date.fromisoformat(str(f[field]))
            except ValueError:
                ok = False
            if not ok:
                errs.append(("frontmatter", f"{name}: {field}={f[field]!r} is not a valid YYYY-MM-DD date"))
    for field in ("date", "submitted", "decision"):
        if field in f and not PARTIAL_DATE.match(str(f[field])):
            errs.append(("frontmatter", f"{name}: {field}={f[field]!r} is not YYYY, YYYY-MM or YYYY-MM-DD (quote it)"))
    if typ == "source":
        authors = f["authors"] if isinstance(f.get("authors"), list) else []
        if f.get("author_status") == "uncredited" and f.get("authors") != []:
            errs.append(("authorship", f"{name}: author_status: uncredited requires authors: []"))
        if f.get("author_status") == "uncredited" and f.get("read_depth") not in ("full", "partial"):
            errs.append(("authorship", f"{name}: author_status: uncredited requires a full or partial read"))
        corporate = f.get("corporate_authors", [])
        declared_corporate = set()
        if isinstance(corporate, list):
            seen_corporate = set()
            for author in corporate:
                if not isinstance(author, str) or not author.strip():
                    errs.append(("frontmatter", f"{name}: corporate_authors entries must be nonempty strings"))
                    continue
                if author in seen_corporate:
                    errs.append(("frontmatter", f"{name}: duplicate corporate_authors entry {author!r}"))
                seen_corporate.add(author)
                if author not in authors:
                    errs.append(("frontmatter", f"{name}: corporate_authors entry {author!r} is not in authors"))
                else:
                    declared_corporate.add(author)
        for a in authors:
            if not (isinstance(a, str) and a in declared_corporate) and not AUTHOR.match(str(a)):
                errs.append(("frontmatter", f"{name}: author entry {a!r} is not \"Last, F.\" (quote each author)"))
                break
        if not isinstance(f.get("year"), int) and f.get("year") != "undated":
            errs.append(("frontmatter", f"{name}: year must be an integer or undated"))
        if isinstance(f.get("doc_id"), int):  # all digits parse as a number, which would drop leading zeros
            errs.append(("frontmatter", f'{name}: doc_id must be quoted, e.g. doc_id: "{f["doc_id"]:08d}"'))
        elif "doc_id" in f and not DOC_ID.match(str(f["doc_id"])):
            errs.append(("frontmatter", f"{name}: doc_id={f['doc_id']!r} is not 8 lowercase hex digits (docs.py info)"))
        files = [str(x) for x in f["files"]] if isinstance(f.get("files"), list) else []
        for p in files:
            if p.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", p) or "\\" in p or ".." in p.split("/"):
                errs.append(("frontmatter", f"{name}: files entry {p!r} must be relative to the raw root, with / separators"))
        if len(set(files)) != len(files):
            errs.append(("frontmatter", f"{name}: files lists a path twice"))
        if f.get("read_depth") in ("full", "partial") and not (f.get("doc_fingerprint") and f.get("doc_checked")):
            errs.append(("provenance", f"{name}: read source lacks doc_fingerprint/doc_checked (run docs.py stamp)"))
        if f.get("doc_fingerprint"):
            fp = parse_fingerprint(f["doc_fingerprint"])
            if fp is None:
                errs.append(("provenance", f"{name}: fingerprint is incomplete or malformed; it certifies nothing (run docs.py stamp)"))
            elif fp[0] != FP_VERSION:
                errs.append(("provenance", f"{name}: fingerprint uses an old format {fp[0]} (run docs.py stamp)"))
            elif len(fp[1]) != len(files):
                errs.append(("provenance", f"{name}: fingerprint has {len(fp[1])} hash(es) for {len(files)} file(s); "
                                           "files: changed since the stamp (run docs.py stamp)"))
        depth, mode = f.get("read_depth"), f.get("read_mode")
        if isinstance(depth, str) and isinstance(mode, str) and depth in MODES_FOR_DEPTH \
                and mode in ALLOWED["read_mode"] and mode not in MODES_FOR_DEPTH[depth]:
            errs.append(("consistency", f"{name}: read_depth={depth} cannot have read_mode={mode}"))
        if mode in ("rendered", "source", "mixed") and not f.get("read_file"):
            errs.append(("consistency", f"{name}: read_mode={mode} but no read_file (the file whose pages or source were read)"))
        if f.get("read_file") and str(f["read_file"]) not in files:
            errs.append(("consistency", f"{name}: read_file {f['read_file']!r} is not in files:"))
    if typ in ("topic", "project") and "folders" in f and isinstance(f["folders"], list):
        for p in f["folders"]:
            if str(p).startswith(("/", "~")) or "\\" in str(p):
                errs.append(("frontmatter", f"{name}: folders entry {p!r} must be relative to the raw root"))


def skill_tools():
    """The installed skill's template tools: $PROJECT_LLM_WIKI_SKILL, else ~/.claude/skills/project-llm-wiki."""
    root = os.path.expanduser(os.environ.get("PROJECT_LLM_WIKI_SKILL") or "~/.claude/skills/project-llm-wiki")
    return os.path.join(root, "assets", "wiki-template", "tools")


def check_tools(wiki, warns, template=None):
    """Warn when tools/ differs from the installed skill, whose copy is the one that gets changed."""
    here = os.path.join(wiki, "tools")
    template = template or skill_tools()
    if not os.path.isfile(os.path.join(here, "wikilint.py")) or os.path.realpath(here) == os.path.realpath(template):
        return  # not a wiki with its own tools (test fixtures), or the skill's template itself
    if not os.path.isdir(template):
        warns.append(("tools", f"the project-llm-wiki skill is not installed ({os.path.dirname(os.path.dirname(os.path.dirname(template)))}); "
                               "install it or set PROJECT_LLM_WIKI_SKILL"))
        return
    for n in TOOLS:
        a, b = os.path.join(here, n), os.path.join(template, n)
        if not os.path.isfile(a) or not os.path.isfile(b) or open(a, "rb").read() != open(b, "rb").read():
            warns.append(("tools", f"tools/{n} differs from the installed skill: change it there, then run "
                                   "init_wiki.py --upgrade-tools (AGENTS.md §12)"))


def check_author_credit(name, fields, body, errs):
    if fields.get("type") != "source" or fields.get("author_status") != "uncredited":
        return
    history = re.search(r"(?im)^> \[!note\] Reading history\s*\n((?:>[^\n]*(?:\n|$))*)", body)
    if not history or not AUTHOR_REASON.search(history.group(1)):
        errs.append(("authorship", f'{name}: author_status: uncredited needs a line "No credited author: <evidence>" in Reading history'))


def main():
    pages = load_pages()
    specials = {}
    for n in ("index", "log", "pending", "reviewed"):
        p = os.path.join(WIKI, n + ".md")
        if os.path.exists(p):
            specials[n] = open(p, encoding="utf-8").read()
    errs, warns = [], []

    # identity
    for name, versions in pages.items():
        if len(versions) > 1:
            errs.append(("identity", f"{name}: page name used in {', '.join(v['dir'] for v in versions)}"))
        if name in ROOT_FILES:
            errs.append(("identity", f"{name}: page name clashes with a root file"))
    ids, owner = {}, {}
    for name, versions in pages.items():
        f = versions[0]["fields"]
        if versions[0]["dir"] != "sources" or f.get("type") != "source":
            continue
        k = f.get("doc_id")
        if k:
            if k in ids:
                errs.append(("identity", f"doc_id {k} used by both {ids[k]} and {name}"))
            ids[k] = name
        for p in f.get("files") or [] if isinstance(f.get("files"), list) else []:
            if p in owner and owner[p] != name:
                errs.append(("identity", f"file {p} is listed by both {owner[p]} and {name}: one document, one page"))
            owner.setdefault(p, name)
    import docs  # noqa: E402  (file URLs of ↗ links)
    try:
        root = docs.raw_root()
    except SystemExit:
        root = None
    keys = {os.path.normcase(os.path.realpath(os.path.join(root, p))): n for p, n in owner.items()} if root else {}

    inbound = {n: set() for n in pages}
    for name, versions in pages.items():
        pg = versions[0]
        f, body = pg["fields"], pg["body"]
        for e in pg["errors"]:
            errs.append(("frontmatter", f"{name}: {e}"))
        try:
            check_fields(name, f, errs)
        except Exception as e:  # a validator crash must be reported, never hide a page
            errs.append(("frontmatter", f"{name}: could not be validated ({type(e).__name__}: {e})"))
        out = links(body)
        for t in out:
            if t not in pages and t not in specials:
                errs.append(("broken link", f"{name} -> [[{t}]]"))
            elif t in inbound and t != name:
                inbound[t].add(name)
        for url in FLINK.findall(body):
            path = docs.url_path(url)
            k = os.path.normcase(os.path.realpath(path)) if path else None
            if k in keys and keys[k] != name:
                warns.append(("stale ↗ link", f"{name}: {os.path.basename(path)} is now [[{keys[k]}]]"))
        if "sources" in f and isinstance(f["sources"], list):
            declared = set(f["sources"])
            cited = {t for t in out if t in pages and pages[t][0]["dir"] == "sources"}
            for s in sorted(declared - set(pages)):
                errs.append(("sources", f"{name}: lists unknown source {s}"))
            for s in sorted(cited - declared):
                errs.append(("sources", f"{name}: cites [[{s}]] but not in sources:"))
            for s in sorted((declared & set(pages)) - cited):
                errs.append(("sources", f"{name}: lists {s} in sources: but never cites it"))
        check_author_credit(name, f, body, errs)
        po = f.get("part_of")
        if f.get("type") == "source-part" and (po not in pages or pages[po][0]["fields"].get("type") != "source"):
            errs.append(("consistency", f"{name}: part_of={po!r} is not a source page"))
        if f.get("type") == "source-part" and versions[0]["dir"] != "sources":
            errs.append(("consistency", f"{name}: a source-part page belongs in sources/"))
        vo = f.get("version_of")
        if vo and (vo not in pages or pages[vo][0]["dir"] != "sources" or vo == name):
            errs.append(("consistency", f"{name}: version_of={vo!r} is not another source page"))
        for m in REUSE.finditer(body):
            line = body[:m.start()].count("\n") + 1
            if versions[0]["dir"] != "sources":
                errs.append(("callout", f"{name} (body line {line}): a [!reuse] block belongs in a source page; link to it from here"))
            elif " · " not in m.group(1) or not m.group(1).split(" · ", 1)[1].strip():
                errs.append(("callout", f"{name} (body line {line}): [!reuse] header needs '<label> · <locator>'"))
        if f.get("type") == "source":
            claims = re.search(r"(?ms)^## Claims and results\s*\n(.*?)(?=^## |\Z)", body)
            for ln in (claims.group(1).splitlines() if claims else []):
                if re.match(r"^[-*+] ", ln) and not CLAIM_STATUS.match(ln):
                    warns.append(("claim status", f"{name}: claim without [proposed|preliminary|reported|published]: {ln.strip()[:70]}"))
        pj = f.get("project")
        if pj and (pj not in pages or pages[pj][0]["dir"] != "projects"):
            errs.append(("consistency", f"{name}: project={pj!r} is not a page in projects/"))
        for m in CONTRA.finditer(body):
            if m.group(2) not in CONTRA_STATUS:
                line = body[:m.start()].count("\n") + 1
                errs.append(("callout", f"{name} (body line {line}): [!contradiction] needs |open, |scope, |superseded or |corrected"))

    for n, text in specials.items():
        if n in HISTORY_FILES:
            continue  # history may name pages since merged, renamed or removed
        for t in links(text):
            if t not in pages and t not in specials:
                errs.append(("broken link", f"{n} -> [[{t}]]"))
    index_links = links(specials.get("index", ""))
    for n, versions in pages.items():
        if n not in index_links:
            warns.append(("index drift", f"{n} not listed in index.md"))
        if not (isinstance(versions[0]["fields"].get("summary"), str) and versions[0]["fields"]["summary"].strip()):
            warns.append(("summary", f"{n} has no summary: field (its index line's text; catalog.py --adopt-index-summaries)"))
        if (versions[0]["dir"] in SIZE_DIRS and versions[0]["fields"].get("frozen") != "true"
                and os.path.getsize(versions[0]["path"]) > SIZE_LIMIT):
            warns.append(("size", f"{n} is {os.path.getsize(versions[0]['path'])} bytes, over {SIZE_LIMIT}: split it "
                                  "into a parent and child pages (split.py)"))
        if not inbound[n] and versions[0]["dir"] not in ("topics", "projects"):
            warns.append(("orphan", f"{n} has no inbound links (besides index/log)"))
    for key, (name, state) in source_states(pages).items():
        if state == "read":
            warns.append(("unintegrated", f"{name} ({key}) is read but no project, concept, entity or topic page cites it"))

    items, problems = pending_parse()
    for msg in problems:
        errs.append(("pending", f"pending.md {msg}"))
    for page, note, _cause in items:
        if page not in pages:
            errs.append(("broken link", f"pending.md -> [[{page}]]"))
        warns.append(("pending", f"{page}: {note}"))
    records, problems = ledger_parse()
    for msg in problems:
        errs.append(("ledger", f"reviewed.md {msg}"))

    import catalog
    for path, _, label in catalog.plan():
        warns.append(("catalog", f"{label} (run tools/catalog.py --apply)"))
    check_tools(WIKI, warns)

    strict = "--strict" in sys.argv
    print(f"{len(pages)} pages checked: {len(errs)} errors, {len(warns)} warnings" + (" (strict)" if strict else ""))
    shown = warns
    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv[:-1] else None
    if since:  # bounded output: every error, but warning details only for pages changed since REV
        mine = changed_pages(since)
        counts = {}
        for cat, _ in warns:
            counts[cat] = counts.get(cat, 0) + 1
        print("warnings by category: " + (", ".join(f"{v} {k}" for k, v in sorted(counts.items())) or "none"))
        shown = [(c, m) for c, m in warns if c in ("catalog", "tools") or WARN_PAGE.match(m) and WARN_PAGE.match(m).group(1) in mine]
        print(f"details below: errors, and the {len(shown)} warning(s) on pages changed since {since} (omit --since for all)")
    for kind, msgs in (("ERROR", errs), ("warn", shown)):
        for cat, msg in sorted(msgs):
            print(f"{kind:5s} {cat:13s} {msg}")
    sys.exit(1 if errs or (strict and warns) else 0)


WARN_PAGE = re.compile(r"^([^\s:]+)")


def changed_pages(rev):
    """Page names changed since git REV, committed or not, including new untracked pages."""
    import subprocess
    out = set()
    for args in (["diff", "--name-only", rev, "--"], ["ls-files", "--others", "--exclude-standard", "--"]):
        r = subprocess.run(["git", "-C", WIKI, *args, *DIRS], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            sys.exit(f"--since {rev}: {r.stderr.strip()}")
        out |= {os.path.basename(p)[:-3] for p in r.stdout.split("\n") if p.endswith(".md")}
    return out


if __name__ == "__main__":
    main()
