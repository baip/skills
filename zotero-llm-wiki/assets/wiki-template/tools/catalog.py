#!/usr/bin/env python3
"""Generated bookkeeping (AGENTS.md §9): fields that follow from the pages themselves, so nobody maintains
them by hand. Editorial text (summaries, synthesis, reading histories) is never rewritten.

  - `sources:` of concept, entity, topic and analysis pages = exactly the source pages their body cites
    (existing order kept, new ones appended in sorted order);
  - index.md, written whole below its preamble (the text before the first `## ` heading, kept as is apart
    from the count header): one line per page, `- [[page|Display]] — summary · <metadata>`, sorted (sources
    by first author, year and name; other pages by name). Display is "First-author year, title" for sources
    and the page's `# ` heading otherwise; the summary is the page's `summary:` field (one line, about 200
    characters). A page without one keeps the summary its current index line has, so nothing editorial is
    lost before `--adopt-index-summaries` has moved those summaries into the pages.

Usage:
  catalog.py [--apply]                 dry run by default (prints what would change); --apply writes
  catalog.py --nav                     print the index without its Sources section: the orientation read at
                                       session start (AGENTS.md §8.1), so nobody reads the whole index
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

SECTION_DIRS = {"Topics": "topics", "Sources": "sources", "Concepts": "concepts", "Entities": "entities",
                "Analyses": "analyses"}
LINE = re.compile(r"^- \[\[([^\]|#\\]+)(?:\\?\|[^\]]*)?\]\]")
SRC_META = re.compile(r" · [^·\n]+ · (?:full|partial|abstract|metadata-only)$")
N_META = re.compile(r" · \d+ sources?$")
HEADER = re.compile(r"\*\*\d+ topics? · \d+ sources? · \d+ concepts? · \d+ entit(?:y|ies) · \d+ analys[ie]s\*\* · updated \d{4}-\d{2}-\d{2}")


def abbrev(path):
    """'Force Fields/Machine Learning/Active learning' -> 'FF/ML/Active learning' (multi-word parents
    become initials; the leaf is kept)."""
    parts = path.split("/")
    return "/".join([("".join(w[0].upper() for w in p.split()) if len(p.split()) > 1 else p) for p in parts[:-1]]
                    + parts[-1:])


def mirrored_prefixes(pages):
    out = []
    for vs in pages.values():
        if vs[0]["dir"] == "topics" and isinstance(vs[0]["fields"].get("zotero_collections"), dict):
            for path in vs[0]["fields"]["zotero_collections"].values():
                out.append(re.sub(r"/_root$", "", str(path)) + "/")
    return out


def source_meta(f, prefixes):
    cols = [c for c in f.get("collections") or [] if isinstance(c, str)]
    col = next((c for c in cols if any((c + "/").startswith(p) or c.startswith(p) for p in prefixes)), cols[0] if cols else "?")
    return f" · {abbrev(col)} · {f.get('read_depth', '?')}"


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


SECTIONS = ("Topics", "Sources", "Concepts", "Entities", "Analyses")


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def first_author(f):
    a = [x for x in f.get("authors") or [] if isinstance(x, str)]
    if a and a[0] != "et al.":
        return a[0].split(",")[0].strip()
    return "Uncredited" if f.get("author_status") == "uncredited" else "No verified author"


def display(vs, name):
    """'First-author year, title' for a source, the `# ` heading for other pages; safe inside a wikilink."""
    f = vs["fields"]
    if vs["dir"] == "sources":
        d = f"{first_author(f)} {f.get('year', 'undated')}, {f.get('title') or name}"
    else:
        h = re.search(r"(?m)^# (.+?)\s*$", vs["body"])
        d = h.group(1) if h else name
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
    d = display(vs, name)
    summ = summary_of(f) or fallback.get(name)
    if vs["dir"] == "sources":
        meta = source_meta(f, prefixes)
    else:
        n = len(f.get("sources") or []) if isinstance(f.get("sources"), list) else 0
        meta = f" · {n} source" + ("" if n == 1 else "s")
    return f"- [[{name}" + ("" if d == name else f"|{d}") + "]]" + (f" — {summ}" if summ else "") + meta


def sort_key(pages, name):
    vs = pages[name][0]
    if vs["dir"] == "sources":
        return (first_author(vs["fields"]).casefold(), str(vs["fields"].get("year", "")), name.casefold())
    return (name.casefold(),)


def index_sections(pages, fallback, skip=()):
    prefixes = mirrored_prefixes(pages)
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
    c = {d: sum(1 for vs in pages.values() if vs[0]["dir"] == d) for d in SECTION_DIRS.values()}
    header = (f"**{plural(c['topics'], 'topic', 'topics')} · {plural(c['sources'], 'source', 'sources')} · "
              f"{plural(c['concepts'], 'concept', 'concepts')} · {plural(c['entities'], 'entity', 'entities')} · "
              f"{plural(c['analyses'], 'analysis', 'analyses')}**")
    m = HEADER.search(new)
    if m and (new != text or not m.group(0).startswith(header + " ·")):  # anything regenerated: restamp the date
        new = new[:m.start()] + f"{header} · updated {today}" + new[m.end():]
    return new


def nav(pages, text):
    """The index without its Sources section: the orientation read at session start."""
    return preamble(text) + "\n\n" + "\n".join(index_sections(pages, index_summaries(text), skip=("Sources",))) + "\n"


def yaml_quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def adopt_summaries(apply):
    """Copy summaries from index.md lines into pages without a `summary:` field (one-time migration)."""
    pages = wikimeta.load_pages()
    idx = os.path.join(wikimeta.WIKI, "index.md")
    found = index_summaries(open(idx).read()) if os.path.exists(idx) else {}
    n = 0
    for name, summ in sorted(found.items()):
        if name not in pages or summary_of(pages[name][0]["fields"]):
            continue
        path = pages[name][0]["path"]
        text = open(path).read()
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
        text = open(vs[0]["path"]).read()
        new = fix_sources(pages, name, text)
        if new != text:
            changes.append((vs[0]["path"], new, f"{name}: sources: re-derived from the body"))
    if changes:  # index counts use the re-derived lists
        for path, new, _ in changes:
            name = os.path.basename(path)[:-3]
            pages[name][0]["fields"] = wikimeta.parse_frontmatter(new)[0]
    idx = os.path.join(wikimeta.WIKI, "index.md")
    if os.path.exists(idx):
        text = open(idx).read()
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
        return print(nav(wikimeta.load_pages(), open(idx).read() if os.path.exists(idx) else "# Index\n"), end="")
    changes = plan()
    for path, new, label in changes:
        old = open(path).read()
        if wikimeta.protected_text(new) != wikimeta.protected_text(old):
            print(f"SKIPPED {label}: protected text would change")
            continue
        print(label)
        if apply:
            wikimeta.atomic_write(path, new)
    print(f"{len(changes)} file(s) {'updated' if apply else 'would change (dry run)'}")


if __name__ == "__main__":
    main()
