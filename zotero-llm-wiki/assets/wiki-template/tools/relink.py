#!/usr/bin/env python3
"""Replace ↗ Zotero links to items that now have a source page with wikilinks.

  [Parker 2026 ↗](zotero://select/library/items/LA52H69Y)  ->  [[parkerFalse...2026|Parker 2026]]

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
from wikimeta import DIRS, WIKI, atomic_write, in_spans, protected_spans, protected_text  # noqa: E402

LINK = re.compile(r"\[([^\[\]\n]*?)\s*↗\]\(zotero://select/library/items/(\w+)\)")


def relink_text(text, keys, self_name=None):
    """Return (new_text, n_rewritten). Pure function, so it can be tested."""
    spans = protected_spans(text)
    n = 0

    def sub(m):
        nonlocal n
        label, key = m.group(1).strip(), m.group(2)
        if key not in keys or keys[key] == self_name or in_spans(m.start(), spans):
            return m.group(0)
        n += 1
        return f"[[{keys[key]}|{label}]]" if label else f"[[{keys[key]}]]"

    new = LINK.sub(sub, text)
    if protected_text(new) != protected_text(text):
        raise RuntimeError("protected text would change")
    return new, n


def main():
    apply = "--apply" in sys.argv
    keys = {}
    for f in os.listdir(os.path.join(WIKI, "sources")):
        if f.endswith(".md"):
            m = re.search(r"^zotero_key:\s*(\w+)", open(os.path.join(WIKI, "sources", f)).read(), re.M)
            if m:
                keys[m.group(1)] = f[:-3]
    total = 0
    for d in DIRS:
        p = os.path.join(WIKI, d)
        for f in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            if not f.endswith(".md"):
                continue
            path = os.path.join(p, f)
            text = open(path).read()
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
