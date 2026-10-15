#!/usr/bin/env python3
"""
Build the installable .skill file for every skill in this repository.

Usage:
    python3 package.py                        # every skill, to dist/<name>.skill
    python3 package.py funding-monitor        # only the named skill(s)
    python3 package.py --list [NAME ...]      # show what would go in, write nothing

A skill is any folder at the top of the repository with a SKILL.md in it.
A .skill file is a zip archive holding one folder named for the skill, with
SKILL.md at its top.

Everything in a skill's folder goes in except what is about maintaining the
skill rather than part of it: its README.md and .gitignore, dist/, Python
caches, and anything the repository's .gitignore leaves out (a personal
funding-monitor profile, scan output, local secrets). Inside a git checkout
the last is decided by git itself, so the package matches what a clone
would hold plus any new files not yet committed.

The frontmatter of SKILL.md is checked first: a kebab-case name of at most
64 characters that matches the folder name, a description of at most 1024
characters without angle brackets, and no top-level fields beyond those the
app accepts.
"""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
LEAVE_OUT = {"README.md", ".gitignore", "dist", ".git"}
ALLOWED_FIELDS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def skills():
    return sorted(p.name for p in ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def frontmatter(skill):
    text = (ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError("SKILL.md has no frontmatter")
    try:
        import yaml
        fields = yaml.safe_load(m.group(1))
        if not isinstance(fields, dict):
            raise ValueError("SKILL.md frontmatter is not a mapping")
        return fields
    except ImportError:
        # Without PyYAML, read the top-level keys only. Nested blocks such as
        # metadata keep their key with an empty value, which is enough here.
        fields = {}
        for line in m.group(1).splitlines():
            if line and not line[0].isspace() and ":" in line:
                k, _, v = line.partition(":")
                fields[k.strip()] = v.strip().strip("'\"")
        return fields


def check(skill):
    f = frontmatter(skill)
    problems = []
    name = f.get("name")
    if name != skill:
        problems.append("name is %r, expected the folder name %r" % (name, skill))
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name or "") or len(name) > 64:
        problems.append("name must be kebab-case and at most 64 characters")
    desc = f.get("description")
    if not isinstance(desc, str) or not desc.strip():
        problems.append("description is missing")
    elif len(desc) > 1024:
        problems.append("description is %d characters, over 1024" % len(desc))
    elif "<" in desc or ">" in desc:
        problems.append("description contains angle brackets")
    extra = set(f) - ALLOWED_FIELDS
    if extra:
        problems.append("unexpected frontmatter field(s): %s" % ", ".join(sorted(extra)))
    if problems:
        raise ValueError("; ".join(problems))


def git_files(skill):
    """Tracked and untracked files git does not ignore, or None outside git."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard", "--", skill],
            check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {Path(p) for p in out.decode("utf-8").split("\0") if p}


def files(skill):
    base = ROOT / skill
    allowed = git_files(skill)
    out = []
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base)
        if not p.is_file() or rel.parts[0] in LEAVE_OUT:
            continue
        if "__pycache__" in rel.parts or p.suffix in (".pyc", ".pyo") or p.name == ".DS_Store":
            continue
        if allowed is not None and Path(skill) / rel not in allowed:
            continue
        out.append(rel)
    return out


def build(skill, list_only):
    check(skill)
    items = files(skill)
    if list_only:
        print("%s:" % skill)
        for rel in items:
            print("  %s" % rel.as_posix())
        print("  %d file(s)\n" % len(items))
        return
    DIST.mkdir(exist_ok=True)
    out = DIST / (skill + ".skill")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in items:
            z.write(ROOT / skill / rel, "%s/%s" % (skill, rel.as_posix()))
    print("wrote %s: %d files, %.0f kB"
          % (out.relative_to(ROOT), len(items), out.stat().st_size / 1e3))


def main(argv):
    list_only = "--list" in argv
    names = [a for a in argv if not a.startswith("-")]
    known = skills()
    unknown = [n.rstrip("/") for n in names if n.rstrip("/") not in known]
    if unknown:
        sys.exit("not a skill folder: %s (found: %s)" % (", ".join(unknown), ", ".join(known)))
    failed = []
    for skill in [n.rstrip("/") for n in names] or known:
        try:
            build(skill, list_only)
        except ValueError as e:
            print("%s: %s" % (skill, e), file=sys.stderr)
            failed.append(skill)
    if failed:
        sys.exit("not packaged: %s" % ", ".join(failed))


if __name__ == "__main__":
    main(sys.argv[1:])
