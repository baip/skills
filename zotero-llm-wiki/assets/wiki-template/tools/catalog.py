#!/usr/bin/env python3
"""Generated bookkeeping (AGENTS.md §9): fields that follow from the pages themselves, so nobody maintains
them by hand. Editorial text (index summaries, synthesis, reading histories) is never touched.

  - `sources:` of concept, entity, topic and analysis pages = exactly the source pages their body cites
    (existing order kept, new ones appended in sorted order);
  - index.md: the page counts in the header, and the trailing metadata of each line
    (sources: `· <collection> · <read_depth>`; other pages: `· <n> sources`).

Dry run by default (prints what would change); pass --apply to write. wikilint.py reports any drift as a
`catalog` warning, so the strict gate fails until this has been run.
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


def fix_index(pages, text, today):
    prefixes = mirrored_prefixes(pages)
    counts = {d: sum(1 for vs in pages.values() if vs[0]["dir"] == d) for d in SECTION_DIRS.values()}
    out, section = [], None
    for line in text.split("\n"):
        h = re.match(r"^## (\w+)", line)
        if h:
            section = SECTION_DIRS.get(h.group(1))
        m = LINE.match(line)
        if m and section and m.group(1).strip() in pages:
            name = m.group(1).strip()
            f = pages[name][0]["fields"]
            if section == "sources":
                base, meta = SRC_META.sub("", line), source_meta(f, prefixes)
            else:
                base = N_META.sub("", line)
                n = len(f.get("sources") or []) if isinstance(f.get("sources"), list) else 0
                meta = f" · {n} source" + ("" if n == 1 else "s")
            line = base + meta
        out.append(line)
    new = "\n".join(out)
    c = counts

    def plural(n, one, many):
        return f"{n} {one if n == 1 else many}"
    header = (f"**{plural(c['topics'], 'topic', 'topics')} · {plural(c['sources'], 'source', 'sources')} · "
              f"{plural(c['concepts'], 'concept', 'concepts')} · {plural(c['entities'], 'entity', 'entities')} · "
              f"{plural(c['analyses'], 'analysis', 'analyses')}**")
    m = HEADER.search(new)
    if m and (new != text or not m.group(0).startswith(header + " ·")):  # anything regenerated: restamp the date
        new = new[:m.start()] + f"{header} · updated {today}" + new[m.end():]
    return new


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
