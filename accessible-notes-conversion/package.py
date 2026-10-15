#!/usr/bin/env python3
"""
Build the installable .skill file from this branch.

Usage:
    python3 package.py                  # writes dist/accessible-notes-conversion.skill
    python3 package.py --list           # show what would go in, write nothing

A .skill file is a zip archive holding one folder named for the skill, with
SKILL.md at its top. Everything in this branch goes in except the files that
are about maintaining the skill rather than part of it: this script, the
README, .gitignore, dist/ and Python caches.

The frontmatter of SKILL.md is checked first: a name of at most 64
characters that matches the folder name, and a description of at most 1024
characters, which is what the app requires.
"""

import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "accessible-notes-conversion"
LEAVE_OUT = {"package.py", "README.md", ".gitignore", ".git"}


def frontmatter():
    text = (HERE / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        sys.exit("SKILL.md has no frontmatter")
    fields = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    return fields


def files():
    out = []
    for p in sorted(HERE.rglob("*")):
        rel = p.relative_to(HERE)
        if not p.is_file() or rel.parts[0] in LEAVE_OUT | {"dist"}:
            continue
        if "__pycache__" in rel.parts or p.suffix == ".pyc":
            continue
        out.append(rel)
    return out


def main():
    f = frontmatter()
    if f.get("name") != NAME:
        sys.exit("SKILL.md name is %r, expected %r" % (f.get("name"), NAME))
    if len(f.get("description", "")) > 1024 or not f.get("description"):
        sys.exit("SKILL.md description is missing or over 1024 characters")
    items = files()
    if "--list" in sys.argv:
        for rel in items:
            print(rel)
        print("\n%d file(s)" % len(items))
        return
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / (NAME + ".skill")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in items:
            z.write(HERE / rel, "%s/%s" % (NAME, rel.as_posix()))
    print("wrote %s: %d files, %.0f kB"
          % (out.relative_to(HERE), len(items), out.stat().st_size / 1e3))


if __name__ == "__main__":
    main()
