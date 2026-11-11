#!/usr/bin/env python3
"""Generated bookkeeping (AGENTS.md §9): fields that follow from the pages themselves, so nobody maintains
them by hand. Editorial text (summaries, synthesis, reading histories) is never rewritten.

  - `sources:` of project, concept, entity, topic and analysis pages = exactly the source pages their body cites
    (existing order kept, new ones appended in sorted order);
  - index.md, written whole below its preamble (the text before the first `## ` heading, kept as is apart
    from the count header): one line per page, `- [[page|Display]] — summary · <metadata>`, sorted (sources
    by year and name; other pages by name). Display is "Title (doc_kind, year)" for sources and the page's `# `
    heading otherwise; the summary is the page's `summary:` field (one line, about 200
    characters). A page without one keeps the summary its current index line has, so nothing editorial is
    lost before `--adopt-index-summaries` has moved those summaries into the pages.

Usage:
  catalog.py [--apply]                 dry run by default (prints what would change); --apply writes
  catalog.py --nav                     print the index preamble and its Topics and Projects sections only: the
                                       orientation read at session start (AGENTS.md §8.1). It grows with the
                                       number of topics and projects, not pages; every other page is found by
                                       search
  catalog.py --adopt-index-summaries [--apply]
                                       copy each page's summary from its index.md line into a `summary:`
                                       field, for pages that lack one (one-time migration)

wikilint.py reports drift as a `catalog` warning, so the strict gate fails until this has been run.
"""
import datetime
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wikimeta  # noqa: E402

SECTION_DIRS = {"Topics": "topics", "Projects": "projects", "Sources": "sources", "Concepts": "concepts",
                "Entities": "entities", "Analyses": "analyses"}
LINE = re.compile(r"^- \[\[([^\]|#\\]+)(?:\\?\|[^\]]*)?\]\]")
SRC_META = re.compile(r" · [^·\n]+ · (?:full|partial|metadata-only)$")
N_META = re.compile(r"(?: · [a-z-]+)? · \d+ sources?$")
HEADER = re.compile(r"\*\*\d+ topics? · \d+ projects? · \d+ sources? · \d+ concepts? · \d+ entit(?:y|ies) · \d+ analys[ie]s\*\* · updated \d{4}-\d{2}-\d{2}")


def abbrev(path):
    """'Proposals/NSF-CAREER/reports' -> 'NSF-CAREER/reports': the last two folders of a path."""
    return "/".join(path.split("/")[-2:])


def source_meta(f):
    files = [x for x in f.get("files") or [] if isinstance(x, str)]
    where = f.get("project") or (abbrev(files[0].rsplit("/", 1)[0]) if files and "/" in files[0] else "?")
    return f" · {where} · {f.get('read_depth', '?')}"


def cited_sources(pages, name):
    vs = pages[name][0]
    return {t for t in wikimeta.links(vs["body"]) if t in pages and pages[t][0]["dir"] == "sources"}


def fix_sources(pages, name, text):
    f = pages[name][0]["fields"]
    if not isinstance(f.get("sources"), list):
        return text
    old, cited = [s for s in f["sources"]], cited_sources(pages, name)
    new = [s for s in old if s in cited] + sorted(cited - set(old))
    if new == old:
        return text
    fm_end = text.index("\n---", 3)
    head, rest = text[:fm_end], text[fm_end:]
    head2, n = re.subn(r"(?m)^sources: .*$", "sources: [" + ", ".join(new) + "]", head, count=1)
    return head2 + rest if n else text


SECTIONS = ("Topics", "Projects", "Sources", "Concepts", "Entities", "Analyses")


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def heading(vs, name):
    h = re.search(r"(?m)^# (.+?)\s*$", vs["body"])
    return h.group(1) if h else name


def display(vs, name, pages=None):
    """'Title (doc_kind, year)' for a source, '<source display>, part: <heading>' for a part note, the
    `# ` heading for other pages; safe inside a wikilink."""
    f = vs["fields"]
    parent = str(f.get("part_of") or "")
    if f.get("type") == "source-part" and pages and parent in pages:
        d = f"{display(pages[parent][0], parent)}, part: {heading(vs, name)}"
    elif vs["dir"] == "sources" and f.get("type") != "source-part":
        d = f"{f.get('title') or name} ({f.get('doc_kind', 'document')}, {f.get('date') or f.get('year', 'undated')})"
    else:
        d = heading(vs, name)
    return " ".join(str(d).replace("|", "/").replace("[", "(").replace("]", ")").split())


def summary_of(f):
    v = f.get("summary")
    return " ".join(v.split()) if isinstance(v, str) and v.strip() else None


def index_summaries(text):
    """{page: summary} from existing index lines (the text after ' — ', without the generated metadata)."""
    out = {}
    for line in text.split("\n"):
        m = LINE.match(line)
        if m and line[m.end():].startswith(" — "):
            summ = N_META.sub("", SRC_META.sub("", line[m.end() + 3:])).strip()
            if summ:
                out[m.group(1).strip()] = summ
    return out


def index_line(pages, name, prefixes, fallback):
    vs = pages[name][0]
    f = vs["fields"]
    d = display(vs, name, pages)
    summ = summary_of(f) or fallback.get(name)
    if f.get("type") == "source-part":
        meta = " · part"
    elif vs["dir"] == "sources":
        meta = source_meta(f)
    else:
        n = len(f.get("sources") or []) if isinstance(f.get("sources"), list) else 0
        meta = (f" · {f['status']}" if vs["dir"] == "projects" and isinstance(f.get("status"), str) else "") + \
            f" · {n} source" + ("" if n == 1 else "s")
    return f"- [[{name}" + ("" if d == name else f"|{d}") + "]]" + (f" — {summ}" if summ else "") + meta


def sort_key(pages, name):
    vs = pages[name][0]
    parent = str(vs["fields"].get("part_of") or "")
    if vs["fields"].get("type") == "source-part" and parent in pages:
        return sort_key(pages, parent) + (name.casefold(),)  # right after its source
    if vs["dir"] == "sources":
        return (str(vs["fields"].get("date") or vs["fields"].get("year", "")), name.casefold())
    return (name.casefold(),)


def index_sections(pages, fallback, skip=()):
    prefixes = None
    out = []
    for sec in SECTIONS:
        if sec in skip:
            continue
        names = sorted((n for n, vs in pages.items() if vs[0]["dir"] == SECTION_DIRS[sec]),
                       key=lambda n: sort_key(pages, n))
        out += [f"## {sec}"] + [index_line(pages, n, prefixes, fallback) for n in names]
    return out


def preamble(text):
    m = re.search(r"(?m)^## ", text)
    return (text[:m.start()] if m else text).rstrip("\n")


def fix_index(pages, text, today):
    new = preamble(text) + "\n\n" + "\n".join(index_sections(pages, index_summaries(text))) + "\n"
    c = {d: sum(1 for vs in pages.values() if vs[0]["dir"] == d and vs[0]["fields"].get("type") != "source-part")
         for d in SECTION_DIRS.values()}  # part notes are not counted as sources
    header = (f"**{plural(c['topics'], 'topic', 'topics')} · {plural(c['projects'], 'project', 'projects')} · "
              f"{plural(c['sources'], 'source', 'sources')} · "
              f"{plural(c['concepts'], 'concept', 'concepts')} · {plural(c['entities'], 'entity', 'entities')} · "
              f"{plural(c['analyses'], 'analysis', 'analyses')}**")
    m = HEADER.search(new)
    if m and (new != text or not m.group(0).startswith(header + " ·")):  # anything regenerated: restamp the date
        new = new[:m.start()] + f"{header} · updated {today}" + new[m.end():]
    return new


def nav(pages, text):
    """The index preamble and Topics and Projects sections: the orientation read at session start."""
    skip = [s for s in SECTIONS if s not in ("Topics", "Projects")]
    return preamble(text) + "\n\n" + "\n".join(index_sections(pages, index_summaries(text), skip=skip)) + "\n"


def yaml_quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def adopt_summaries(apply):
    """Copy summaries from index.md lines into pages without a `summary:` field (one-time migration)."""
    pages = wikimeta.load_pages()
    idx = os.path.join(wikimeta.WIKI, "index.md")
    found = index_summaries(open(idx, encoding="utf-8").read()) if os.path.exists(idx) else {}
    n = 0
    for name, summ in sorted(found.items()):
        if name not in pages or summary_of(pages[name][0]["fields"]):
            continue
        path = pages[name][0]["path"]
        text = open(path, encoding="utf-8").read()
        fm_end = text.index("\n---", 3)
        lines = text[:fm_end].split("\n")
        at = next((i for i, ln in enumerate(lines) if ln.startswith("title:")), None)
        if at is None:
            at = next((i for i, ln in enumerate(lines) if ln.startswith("type:")), len(lines) - 1)
        lines.insert(at + 1, "summary: " + yaml_quote(summ))
        new = "\n".join(lines) + text[fm_end:]
        fields, _, errors = wikimeta.parse_frontmatter(new)
        if errors or fields.get("summary") != summ:
            print(f"SKIPPED {name}: the quoted summary does not parse back unchanged")
            continue
        n += 1
        if apply:
            wikimeta.atomic_write(path, new)
    print(f"{n} page(s) {'given' if apply else 'would get (dry run)'} a summary: field from index.md")


def plan(today=None):
    """[(path, new_text, label)] for every generated field that is out of date."""
    today = today or datetime.date.today().isoformat()
    pages = wikimeta.load_pages()
    changes = []
    for name, vs in sorted(pages.items()):
        if vs[0]["dir"] == "sources":
            continue
        text = open(vs[0]["path"], encoding="utf-8").read()
        new = fix_sources(pages, name, text)
        if new != text:
            changes.append((vs[0]["path"], new, f"{name}: sources: re-derived from the body"))
    if changes:  # index counts use the re-derived lists
        for path, new, _ in changes:
            name = os.path.basename(path)[:-3]
            pages[name][0]["fields"] = wikimeta.parse_frontmatter(new)[0]
    idx = os.path.join(wikimeta.WIKI, "index.md")
    if os.path.exists(idx):
        text = open(idx, encoding="utf-8").read()
        new = fix_index(pages, text, today)
        if new != text:
            changes.append((idx, new, "index.md: counts or line metadata regenerated"))
    return changes


def main():
    apply = "--apply" in sys.argv
    if "--adopt-index-summaries" in sys.argv:
        return adopt_summaries(apply)
    if "--nav" in sys.argv:
        idx = os.path.join(wikimeta.WIKI, "index.md")
        return print(nav(wikimeta.load_pages(), open(idx, encoding="utf-8").read() if os.path.exists(idx) else "# Index\n"), end="")
    changes = plan()
    for path, new, label in changes:
        old = open(path, encoding="utf-8").read()
        if wikimeta.protected_text(new) != wikimeta.protected_text(old):
            print(f"SKIPPED {label}: protected text would change")
            continue
        print(label)
        if apply:
            wikimeta.atomic_write(path, new)
    print(f"{len(changes)} file(s) {'updated' if apply else 'would change (dry run)'}")


if __name__ == "__main__":
    main()
