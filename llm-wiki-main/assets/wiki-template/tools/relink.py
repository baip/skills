#!/usr/bin/env python3
"""Replace ↗ links to documents that now have a source page with wikilinks.

  [CAREER report 2024 ↗](file:///…/AnnualProjectReport-202408.docx)  ->  [[2024-career-annual-report|CAREER report 2024]]

A link matches a page when its file is one of the page's files: (relative to the raw root, tools/config.json).

Never touches protected spans (AGENTS.md §2.9): `> [!user]` callouts, fenced code and inline code.
After rewriting a file it verifies those spans are byte-identical, and refuses to write otherwise.
A source page's links to its own item are left alone. Dry run by default; pass --apply to write.
Run only when no reader agent is still writing (AGENTS.md §8.2b).
"""
import os
import re
import sys

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import docs  # noqa: E402
from wikimeta import DIRS, WIKI, atomic_write, in_spans, parse_frontmatter, protected_spans, protected_text  # noqa: E402

LINK = re.compile(r"\[([^\[\]\n]*?)\s*↗\]\((file://[^)\s]+)\)")


def relink_text(text, keys, self_name=None):
    """Return (new_text, n_rewritten). Pure function, so it can be tested."""
    spans = protected_spans(text)
    n = 0

    def sub(m):
        nonlocal n
        label, path = m.group(1).strip(), docs.url_path(m.group(2))
        key = os.path.normcase(os.path.realpath(path)) if path else None
        if key not in keys or keys[key] == self_name or in_spans(m.start(), spans):
            return m.group(0)
        n += 1
        return f"[[{keys[key]}|{label}]]" if label else f"[[{keys[key]}]]"

    new = LINK.sub(sub, text)
    if protected_text(new) != protected_text(text):
        raise RuntimeError("protected text would change")
    return new, n


def source_keys(directory, root):
    """{normalized absolute path: page} for every file of every source page, read with the same YAML parser used
    by lint and stamping."""
    keys = {}
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".md"):
            continue
        with open(os.path.join(directory, filename), encoding="utf-8") as source:
            fields, _, errors = parse_frontmatter(source.read())
        files = fields.get("files")
        if not errors and fields.get("type") == "source" and isinstance(files, list):
            for p in files:
                keys[os.path.normcase(os.path.realpath(os.path.join(root, str(p))))] = filename[:-3]
    return keys


def main():
    apply = "--apply" in sys.argv
    keys = source_keys(os.path.join(WIKI, "sources"), docs.raw_root())
    total = 0
    for d in DIRS:
        p = os.path.join(WIKI, d)
        for f in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            if not f.endswith(".md"):
                continue
            path = os.path.join(p, f)
            text = open(path, encoding="utf-8").read()
            try:
                new, n = relink_text(text, keys, f[:-3])
            except RuntimeError as e:
                print(f"SKIPPED {d}/{f}: {e}")
                continue
            if n:
                total += n
                print(f"{n:3d}  {d}/{f}")
                if apply:
                    atomic_write(path, new)
    print(f"{total} links {'rewritten' if apply else 'would be rewritten (dry run)'}")


if __name__ == "__main__":
    main()
