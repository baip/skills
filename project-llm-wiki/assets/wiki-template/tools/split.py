#!/usr/bin/env python3
"""Split an oversized concept, entity, topic or source page (AGENTS.md §11; lint `size`) by moving one
section, verbatim, to a new child page. The child of a source page is a part note (`type: source-part`,
`part_of: <source>`) in sources/: the same work's reading notes, not a second identity. The agent chooses the section, the child's name and its one-line summary; the
tool moves the text, so nothing is retyped and no claim changes.

Usage:
  split.py PARENT --section HEADING --to CHILD --summary TEXT [--title TITLE] [--apply]

  - HEADING is the exact text of a `##`, `###` or `####` heading in PARENT. The section runs to the next heading
    of the same or a higher level.
  - For a source PARENT, CHILD is PARENT--<part-slug>, a part note in sources/ (`type: source-part`,
    `part_of: PARENT`, the summary, today's dates) whose body is `# TITLE`, a pointer back, `## Notes` with the
    moved text and `## Connections`. Coverage, provenance and the reading history stay on the source page.
  - Otherwise CHILD (new, lowercase kebab-case) is created in concepts/ (entities/ for an entity parent) with the
    parent's tags, `summary: TEXT`, `sources: []` (catalog.py --apply derives it) and today's dates. Its body is
    `# TITLE` (default: HEADING without a leading number), a pointer back to the parent, `## Details` holding the
    moved text with its subheadings re-levelled, and `## Related`.
  - In PARENT the heading stays and its text is replaced by one line: TEXT → [[CHILD]].
  - Dry run by default. --apply writes both files after checking that the protected text of the two pages
    together is unchanged.

A split moves claims without changing them: pass PARENT to `review.py since --neutral`, and list the split in
the log. Then run catalog.py --apply, which derives both pages' sources: lists and their index lines.
"""
import argparse
import datetime
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import wikimeta  # noqa: E402

HEADING = re.compile(r"^(#{2,4})\s+(.*?)\s*$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PART = re.compile(r"^[^\s/|#\]\[]+--[a-z0-9]+(?:-[a-z0-9]+)*$")


def headings(body):
    """[(line index, level, text)] for ## to #### headings outside fenced code."""
    spans = wikimeta.fenced_blocks(body)
    out, pos = [], 0
    for i, line in enumerate(body.split("\n")):
        m = HEADING.match(line)
        if m and not wikimeta.in_spans(pos, spans):
            out.append((i, len(m.group(1)), m.group(2)))
        pos += len(line) + 1
    return out


def plan_split(parent_text, heading, child, summary, title, parent_name, today):
    """(new parent text, child text). Raises ValueError when the heading is missing or ambiguous."""
    fields, body, errors = wikimeta.parse_frontmatter(parent_text)
    if errors:
        raise ValueError(f"{parent_name}: frontmatter does not parse: {errors}")
    hs = headings(body)
    hits = [h for h in hs if h[2] == heading]
    if len(hits) != 1:
        raise ValueError(f"{parent_name}: heading {heading!r} found {len(hits)} times, need exactly one")
    start, level, _ = hits[0]
    lines = body.split("\n")
    end = next((i for i, lv, _ in hs if i > start and lv <= level), len(lines))
    real = {i: lv for i, lv, _ in hs}  # headings outside fenced code
    relevel = [("#" * (real[i] - level + 2) + " " + HEADING.match(lines[i]).group(2)) if i in real else lines[i]
               for i in range(start + 1, end)]
    while relevel and not relevel[-1].strip():
        relevel.pop()
    while relevel and not relevel[0].strip():
        relevel.pop(0)
    if not relevel:
        raise ValueError(f"{parent_name}: section {heading!r} is empty")
    new_body = "\n".join(lines[:start + 1] + ["", f"{summary} → [[{child}]]", ""] + lines[end:])
    parent_new = parent_text[:len(parent_text) - len(body)] + new_body

    if fields.get("type") == "source":
        fm = ["type: source-part", f"part_of: {parent_name}", f"summary: {catalog.yaml_quote(summary)}",
              f"created: {today}", f"updated: {today}"]
        child_text = ("---\n" + "\n".join(fm) + "\n---\n"
                      f"# {title}\n\n"
                      f"→ [[{parent_name}]]. Part of the reading notes for this source, split from its page on {today};"
                      " the text below moved verbatim. Coverage and provenance stay on the source page.\n\n"
                      "## Notes\n\n" + "\n".join(relevel) + "\n\n"
                      f"## Connections\n\n- [[{parent_name}]]\n")
        return parent_new, child_text
    kind = "entity" if fields.get("type") == "entity" else "concept"
    tags = [t for t in fields.get("tags") or [] if isinstance(t, str)]
    fm = [f"type: {kind}", f"summary: {catalog.yaml_quote(summary)}"]
    if kind == "entity":
        fm.append(f"entity_kind: {fields.get('entity_kind', 'method')}")
    fm += ["aliases: []", "tags: [" + ", ".join(catalog.yaml_quote(t) if "," in t else t for t in tags) + "]",
           "sources: []", f"created: {today}", f"updated: {today}"]
    child_text = ("---\n" + "\n".join(fm) + "\n---\n"
                  f"# {title}\n\n"
                  f"→ [[{parent_name}]]. This page was split from that page on {today}; the text below moved verbatim.\n\n"
                  "## Details\n\n" + "\n".join(relevel) + "\n\n"
                  f"## Related\n\n- [[{parent_name}]]\n")
    return parent_new, child_text


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("parent")
    p.add_argument("--section", required=True)
    p.add_argument("--to", required=True, dest="child")
    p.add_argument("--summary", required=True)
    p.add_argument("--title")
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    pages = wikimeta.load_pages()
    if a.parent not in pages or pages[a.parent][0]["fields"].get("type") not in ("concept", "entity", "topic", "source"):
        sys.exit(f"{a.parent}: not a concept, entity, topic or source page")
    is_source = pages[a.parent][0]["fields"].get("type") == "source"
    if a.child in pages or not (PART.match(a.child) and a.child.startswith(a.parent + "--") if is_source else SLUG.match(a.child)):
        sys.exit(f"{a.child}: needs a new page name, lowercase kebab-case"
                 + (f", of the form {a.parent}--<part-slug> for a part note" if is_source else ""))
    if "\n" in a.summary or not a.summary.strip():
        sys.exit("--summary must be one nonempty line")
    vs = pages[a.parent][0]
    text = open(vs["path"], encoding="utf-8").read()
    title = a.title or re.sub(r"^\d+[.)]\s*", "", a.section)
    try:
        parent_new, child_text = plan_split(text, a.section, a.child, a.summary.strip(), title, a.parent,
                                            datetime.date.today().isoformat())
    except ValueError as e:
        sys.exit(str(e))
    before = sorted(wikimeta.protected_text(text))
    after = sorted(wikimeta.protected_text(parent_new) + wikimeta.protected_text(child_text))
    if before != after:
        sys.exit("protected text would change: split refused")
    child_dir = {"entities": "entities", "sources": "sources"}.get(vs["dir"], "concepts")
    child_path = os.path.join(wikimeta.WIKI, child_dir, a.child + ".md")
    print(f"{a.parent}: {len(text)} -> {len(parent_new)} bytes; {child_dir}/{a.child}.md: {len(child_text)} bytes")
    if a.apply:
        wikimeta.atomic_write(child_path, child_text)
        wikimeta.atomic_write(vs["path"], parent_new)
        print("written; next: review.py since REV --neutral " + a.parent + ", then catalog.py --apply")
    else:
        print("dry run: pass --apply to write")


if __name__ == "__main__":
    main()
