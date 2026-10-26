#!/usr/bin/env python3
"""Structural lint for the wiki (AGENTS.md §8.4). Read-only; prints a report and exits 1 on errors.

Errors (must be fixed):
  frontmatter   unparseable frontmatter, missing or mistyped fields, values outside the permitted sets (a full or
                partial read must record `supplement`)
  identity      duplicate (library, zotero_key), a page name used in two folders or clashing with a root file
  broken link   wikilink to a page that does not exist
  sources       sources: lists an unknown page, misses a cited source, or lists one never cited
  callout       [!contradiction] without a status (open|scope|superseded|corrected)
  pending       a pending.md checkbox line that cannot be read, or a completed item left in place
  ledger        a reviewed.md line that cannot be read, has an unknown outcome, or lacks a basis
  provenance    a read source page without zotero_fingerprint / zotero_checked
  consistency   fields that contradict each other (read_depth vs read_mode, uri vs key, citekey vs filename, version_of)
Warnings (judgment calls; `--strict` makes them fail too, which is the ingest completion gate, AGENTS.md §8.2):
  index drift   page not listed in index.md
  orphan        page with no inbound link (besides index/log)
  stale ↗ link  ↗ Zotero link to an item that now has a source page (run tools/relink.py)
  catalog       a generated field is out of date: a sources: list or index.md counts/metadata (run tools/catalog.py)
  unintegrated  source read but not cited in the text of any concept, entity or topic page; a page whose
                `version_of:` target is cited counts as integrated (§4 cites the later version of a work)
  pending       an open item in pending.md (pages awaiting a synthesis review)
  supplement    `supplement: not-read` without a line "Supplement not read: <reason>" in the page body
  tools         a tools/*.py file differs from the installed zotero-llm-wiki skill, or the skill is not installed
                (tools are changed in the skill first, then copied in with init_wiki.py --upgrade-tools; AGENTS.md §12)
"""
import datetime
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikimeta import WIKI, FP_VERSION, ledger_parse, load_pages, links, parse_fingerprint, pending_parse, source_states  # noqa: E402

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEY = re.compile(r"^[A-Z0-9]{8}$")
AUTHOR = re.compile(r"^(et al\.|[^,]+, [^,]+)$")  # "Last, F." or "et al."
ROOT_FILES = {"index", "log", "pending", "reviewed", "AGENTS", "CLAUDE", "llm-wiki"}
LIBRARY = re.compile(r"^(user|group):(\d+)$")
ALLOWED = {
    "type": {"source", "concept", "entity", "topic", "analysis"},
    "read_depth": {"full", "partial", "abstract", "metadata-only"},
    "read_mode": {"rendered", "text-index", "mixed", "none"},
    "supplement": {"read", "skimmed", "not-read", "none"},
    "item_type": {"review", "article", "preprint", "book", "chapter", "thesis", "software", "dataset", "conference", "patent", "presentation", "report"},
    "entity_kind": {"model", "method", "software", "dataset", "benchmark", "instrument", "material", "organism", "site",
                    "group", "person"},
}
REQUIRED = {
    "source": ["title", "authors", "year", "venue", "item_type", "library", "zotero_key", "citekey", "zotero_uri",
               "collections", "read_depth", "read_mode", "ingested", "updated"],
    "concept": ["sources", "created", "updated"],
    "entity": ["entity_kind", "sources", "created", "updated"],
    "topic": ["zotero_collections", "sources", "created", "updated"],
    "analysis": ["question", "sources", "created"],
}
LISTS = {"authors", "collections", "sources", "tags", "aliases", "zotero_tags"}
STRINGS = {"library", "title", "venue", "citekey", "zotero_uri", "zotero_key", "attachment_key", "doi", "url", "question",
           "zotero_fingerprint", "version_of", "entity_kind", "item_type", "read_depth", "read_mode", "supplement"}
TOOLS = ("catalog.py", "relink.py", "review.py", "search.py", "test_tools.py", "wikilint.py", "wikimeta.py", "zot.py")
MODES_FOR_DEPTH = {"full": {"rendered", "text-index", "mixed"}, "partial": {"rendered", "text-index", "mixed"},
                   "abstract": {"none"}, "metadata-only": {"none"}}
CONTRA = re.compile(r"^> \[!contradiction(\|([a-z-]+))?\]", re.M)
CONTRA_STATUS = {"open", "scope", "superseded", "corrected"}
SUPP_REASON = re.compile(r"Supplement not read: *\S", re.I)
ZLINK = re.compile(r"\]\(zotero://select/library/items/(\w+)\)")


def check_fields(name, f, errs):
    typ = f.get("type")
    if not isinstance(typ, str) or typ not in REQUIRED:
        errs.append(("frontmatter", f"{name}: missing/unknown type {typ!r}"))
        return
    for field in REQUIRED[typ]:
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
    for field in ("ingested", "updated", "created", "zotero_checked"):
        if field in f:
            try:
                ok = bool(DATE.match(str(f[field]))) and datetime.date.fromisoformat(str(f[field]))
            except ValueError:
                ok = False
            if not ok:
                errs.append(("frontmatter", f"{name}: {field}={f[field]!r} is not a valid YYYY-MM-DD date"))
    if typ == "source":
        for a in f["authors"] if isinstance(f.get("authors"), list) else []:
            if not AUTHOR.match(str(a)):
                errs.append(("frontmatter", f"{name}: author entry {a!r} is not \"Last, F.\" (quote each author)"))
                break
        if not isinstance(f.get("year"), int) and f.get("year") != "undated":
            errs.append(("frontmatter", f"{name}: year must be an integer or undated"))
        for k in ("zotero_key", "attachment_key"):
            if k in f and not KEY.match(str(f[k])):
                errs.append(("frontmatter", f"{name}: {k}={f[k]!r} is not an 8-character Zotero key"))
        if f.get("read_depth") in ("full", "partial") and f.get("supplement") in (None, ""):
            errs.append(("frontmatter", f"{name}: a {f['read_depth']} read must record supplement: read, skimmed, not-read or none"))
        if f.get("read_depth") in ("full", "partial") and not (f.get("zotero_fingerprint") and f.get("zotero_checked")):
            errs.append(("provenance", f"{name}: read source lacks zotero_fingerprint/zotero_checked (run zot.py stamp)"))
        if f.get("zotero_fingerprint"):
            fp = parse_fingerprint(f["zotero_fingerprint"])
            if fp is None:
                errs.append(("provenance", f"{name}: fingerprint is incomplete or malformed; it certifies nothing (run zot.py stamp)"))
            elif fp[0] != FP_VERSION:
                errs.append(("provenance", f"{name}: fingerprint uses an old format {fp[0]} (run zot.py stamp)"))
        depth, mode = f.get("read_depth"), f.get("read_mode")
        if isinstance(depth, str) and isinstance(mode, str) and depth in MODES_FOR_DEPTH \
                and mode in ALLOWED["read_mode"] and mode not in MODES_FOR_DEPTH[depth]:
            errs.append(("consistency", f"{name}: read_depth={depth} cannot have read_mode={mode}"))
        if mode in ("rendered", "mixed") and not f.get("attachment_key"):
            errs.append(("consistency", f"{name}: read_mode={mode} but no attachment_key"))
        lib = LIBRARY.match(str(f.get("library", "")))
        if f.get("library") and not lib:
            errs.append(("frontmatter", f"{name}: library={f['library']!r} is not user:<id> or group:<id>"))
        if f.get("zotero_key") and lib:
            want = ("zotero://select/library/items/" if lib.group(1) == "user" else
                    f"zotero://select/groups/{lib.group(2)}/items/") + str(f["zotero_key"])
            if str(f.get("zotero_uri", "")) != want:
                errs.append(("consistency", f"{name}: zotero_uri should be {want} for library {f['library']}"))
        if f.get("citekey") and f["citekey"] != name and f["citekey"] not in (f.get("aliases") or []):
            errs.append(("consistency", f"{name}: citekey {f['citekey']!r} is neither the filename nor in aliases"))
    if typ == "topic" and not isinstance(f.get("zotero_collections"), dict):
        errs.append(("frontmatter", f"{name}: zotero_collections must be a {{KEY: \"path\"}} map"))


def skill_tools():
    """The installed skill's template tools: $ZOTERO_LLM_WIKI_SKILL, else ~/.claude/skills/zotero-llm-wiki."""
    root = os.path.expanduser(os.environ.get("ZOTERO_LLM_WIKI_SKILL") or "~/.claude/skills/zotero-llm-wiki")
    return os.path.join(root, "assets", "wiki-template", "tools")


def check_tools(wiki, warns, template=None):
    """Warn when tools/ differs from the installed skill, whose copy is the one that gets changed."""
    here = os.path.join(wiki, "tools")
    template = template or skill_tools()
    if not os.path.isfile(os.path.join(here, "wikilint.py")) or os.path.realpath(here) == os.path.realpath(template):
        return  # not a wiki with its own tools (test fixtures), or the skill's template itself
    if not os.path.isdir(template):
        warns.append(("tools", f"the zotero-llm-wiki skill is not installed ({os.path.dirname(os.path.dirname(os.path.dirname(template)))}); "
                               "install it or set ZOTERO_LLM_WIKI_SKILL"))
        return
    for n in TOOLS:
        a, b = os.path.join(here, n), os.path.join(template, n)
        if not os.path.isfile(a) or not os.path.isfile(b) or open(a, "rb").read() != open(b, "rb").read():
            warns.append(("tools", f"tools/{n} differs from the installed skill: change it there, then run "
                                   "init_wiki.py --upgrade-tools (AGENTS.md §12)"))


def main():
    pages = load_pages()
    specials = {}
    for n in ("index", "log", "pending", "reviewed"):
        p = os.path.join(WIKI, n + ".md")
        if os.path.exists(p):
            specials[n] = open(p).read()
    errs, warns = [], []

    # identity
    for name, versions in pages.items():
        if len(versions) > 1:
            errs.append(("identity", f"{name}: page name used in {', '.join(v['dir'] for v in versions)}"))
        if name in ROOT_FILES:
            errs.append(("identity", f"{name}: page name clashes with a root file"))
    keys, ids = {}, {}
    for name, versions in pages.items():
        k = versions[0]["fields"].get("zotero_key")
        if k and versions[0]["dir"] == "sources":
            ident = (versions[0]["fields"].get("library"), k)  # identity is (library, key): keys are unique per library only
            if ident in ids:
                errs.append(("identity", f"{ident[0]}:{k} used by both {ids[ident]} and {name}"))
            ids[ident] = name
            if versions[0]["fields"].get("library", "").startswith("user:"):
                keys[k] = name  # ↗ links (zotero://select/library/items/KEY) address the user library

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
        for k in ZLINK.findall(body):
            if k in keys and keys[k] != name:
                warns.append(("stale ↗ link", f"{name}: Zotero {k} is now [[{keys[k]}]]"))
        if "sources" in f and isinstance(f["sources"], list):
            declared = set(f["sources"])
            cited = {t for t in out if t in pages and pages[t][0]["dir"] == "sources"}
            for s in sorted(declared - set(pages)):
                errs.append(("sources", f"{name}: lists unknown source {s}"))
            for s in sorted(cited - declared):
                errs.append(("sources", f"{name}: cites [[{s}]] but not in sources:"))
            for s in sorted((declared & set(pages)) - cited):
                errs.append(("sources", f"{name}: lists {s} in sources: but never cites it"))
        if f.get("type") == "source" and f.get("supplement") == "not-read" and not SUPP_REASON.search(body):
            warns.append(("supplement", f"{name}: supplement: not-read needs a line \"Supplement not read: <reason>\" in the Reading history"))
        vo = f.get("version_of")
        if vo and (vo not in pages or pages[vo][0]["dir"] != "sources" or vo == name):
            errs.append(("consistency", f"{name}: version_of={vo!r} is not another source page"))
        for m in CONTRA.finditer(body):
            if m.group(2) not in CONTRA_STATUS:
                line = body[:m.start()].count("\n") + 1
                errs.append(("callout", f"{name} (body line {line}): [!contradiction] needs |open, |scope, |superseded or |corrected"))

    for n, text in specials.items():
        for t in links(text):
            if t not in pages and t not in specials:
                errs.append(("broken link", f"{n} -> [[{t}]]"))
    index_links = links(specials.get("index", ""))
    for n, versions in pages.items():
        if n not in index_links:
            warns.append(("index drift", f"{n} not listed in index.md"))
        if not inbound[n] and versions[0]["dir"] != "topics":
            warns.append(("orphan", f"{n} has no inbound links (besides index/log)"))
    for key, (name, state) in source_states(pages).items():
        if state == "read":
            warns.append(("unintegrated", f"{name} ({key}) is read but no concept, entity or topic page cites it"))

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
    for _, _, _, plist, _ in records:
        for page in plist:
            if page not in pages:
                errs.append(("broken link", f"reviewed.md -> [[{page}]]"))

    import catalog
    for path, _, label in catalog.plan():
        warns.append(("catalog", f"{label} (run tools/catalog.py --apply)"))
    check_tools(WIKI, warns)

    strict = "--strict" in sys.argv
    print(f"{len(pages)} pages checked: {len(errs)} errors, {len(warns)} warnings" + (" (strict)" if strict else ""))
    for kind, msgs in (("ERROR", errs), ("warn", warns)):
        for cat, msg in sorted(msgs):
            print(f"{kind:5s} {cat:13s} {msg}")
    sys.exit(1 if errs or (strict and warns) else 0)


if __name__ == "__main__":
    main()
