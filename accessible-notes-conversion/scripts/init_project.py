#!/usr/bin/env python3
"""
Set up a new accessible-notes project, or refresh the toolkit in an old one.

Usage:
    python3 init_project.py DEST --title "CHEM 101 — General Chemistry" \
        --short "CHEM 101" --class chem101 [--author "..."] [--copyright "..."]
        [--archive chem101-notes] [--no-example] [--force]

    python3 init_project.py DEST --update-toolkit

A new project gets this layout, with every placeholder in the templates
filled from the options:

    md2tex.py buildtex.py mkweb.py checkweb.py package.py contents.py
                            the build scripts, run from the project root
    <class>.cls             the LaTeX class, renamed to --class
    contents.yaml           the table of contents and the site settings
    CONVENTIONS.md BUILD.md .gitignore package.json
    AGENTS.md CLAUDE.md     instructions for coding agents (CLAUDE.md
                            loads AGENTS.md for Claude Code)
    src/                    the lectures' Markdown, with their .tex and .pdf
                            beside them (an example lecture unless
                            --no-example)
    scripts/figures_audit.py
    scripts/figures/        figlib.py and one make_figures_NN.py per document
    figures/                the SVG figures the drawing scripts write
    originals/, work/       the originals and page images, untracked

Homework and exams go in a course-year folder such as 2026/, created when
the first one is added.

--update-toolkit replaces only the build scripts in an existing project with
the ones bundled here. It never touches the documents, the drawing scripts,
the class file, contents.yaml or the documentation files, since those
carry the project's own decisions. It prints what changed.

Nothing that already exists is overwritten without --force, and the files
that would have been are listed.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TOOLKIT = SKILL / "assets" / "toolkit"
TEMPLATES = SKILL / "assets" / "templates"
REFS = SKILL / "references"

# Where each toolkit file goes in a project.
SCRIPTS = {
    "md2tex.py": "md2tex.py",
    "buildtex.py": "buildtex.py",
    "mkweb.py": "mkweb.py",
    "checkweb.py": "checkweb.py",
    "contents.py": "contents.py",
    "package.py": "package.py",
    "figures_audit.py": "scripts/figures_audit.py",
    "figlib.py": "scripts/figures/figlib.py",
}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower()) or "notes"


def fill(text, values):
    for k, v in values.items():
        text = text.replace("{{%s}}" % k, v)
    left = sorted(set(re.findall(r"\{\{([A-Z]+)\}\}", text)))
    if left:
        sys.exit("unfilled placeholder(s): %s" % ", ".join(left))
    return text


def plan_new(dest, values, example):
    """Every file a new project gets, as (destination, text or source path)."""
    cls = values["CLASS"]
    items = [(dest / rel, TOOLKIT / name) for name, rel in SCRIPTS.items()]
    klass = (TOOLKIT / "notes.cls").read_text(encoding="utf-8")
    klass = klass.replace(r"\ProvidesClass{notes}", r"\ProvidesClass{%s}" % cls)
    klass = klass.replace("%% notes.cls —", "%% %s.cls —" % cls, 1)
    items.append((dest / (cls + ".cls"), klass))
    items.append((dest / "contents.yaml",
                  fill((TEMPLATES / "contents.yaml").read_text(), values)))
    items.append((dest / "CONVENTIONS.md",
                  fill((REFS / "conventions.md").read_text(), values)))
    items.append((dest / "BUILD.md",
                  fill((REFS / "building.md").read_text(), values)))
    items.append((dest / "AGENTS.md",
                  fill((TEMPLATES / "AGENTS.template.md").read_text(), values)))
    items.append((dest / "CLAUDE.md", TEMPLATES / "CLAUDE.template.md"))
    items.append((dest / ".gitignore",
                  fill((TEMPLATES / "gitignore").read_text(), values)))
    items.append((dest / "package.json", TEMPLATES / "package.json"))
    if example:
        items.append((dest / "src" / "01_Example.md",
                      fill((TEMPLATES / "01_Example.md").read_text(), values)))
        items.append((dest / "scripts" / "figures" / "make_figures_01.py",
                      TEMPLATES / "make_figures_01.py"))
    else:
        # an empty table of contents rather than one naming a missing file
        text = dict(items)[dest / "contents.yaml"]
        text = re.sub(r"parts:.*\Z", "parts:\n  - title: Lectures\n    "
                      "documents: []\n", text, flags=re.S)
        items = [(p, text if p == dest / "contents.yaml" else c)
                 for p, c in items]
    return items


def write_all(items, force):
    clashes = [p for p, _ in items if p.exists()]
    if clashes and not force:
        print("these already exist and were left alone (use --force):")
        for p in clashes:
            print("   ", p)
        items = [(p, c) for p, c in items if not p.exists()]
    for p, content in items:
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, Path):
            shutil.copyfile(content, p)
        else:
            p.write_text(content, encoding="utf-8")
        print("wrote", p)


def update_toolkit(dest, force=False):
    if not (dest / "contents.yaml").exists():
        sys.exit("%s has no contents.yaml: not a project to update" % dest)
    old = [n for n in ("figlib.py", "figures_audit.py") if (dest / n).exists()]
    if old:
        print("note: %s at the project root is the earlier layout. The "
              "current one keeps figures_audit.py in scripts/ and figlib.py "
              "with the drawing scripts in scripts/figures/, and the "
              "lectures in src/. See BUILD.md for moving a project over, "
              "then run this again (or pass --force to install anyway)."
              % " and ".join(old))
        if not force:
            sys.exit(1)
    changed = 0
    for name, rel in SCRIPTS.items():
        src, dst = TOOLKIT / name, dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        new = src.read_bytes()
        existed = dst.exists()
        if existed and dst.read_bytes() == new:
            continue
        dst.write_bytes(new)
        changed += 1
        print("updated" if existed else "added", dst)
    print("%d script(s) changed. Check contents.yaml has the site settings "
          "the scripts read: title, project, short, author, copyright, intro, "
          "latex_class, archive, support, language, show_source." % changed)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dest", type=Path)
    ap.add_argument("--title", help='website and document title, '
                    'e.g. "CHEM 101 — General Chemistry"')
    ap.add_argument("--short", help='short course name for running feet, '
                    'e.g. "CHEM 101"')
    ap.add_argument("--project", help="Sphinx project name (default: title)")
    ap.add_argument("--author", default="")
    ap.add_argument("--copyright", default="")
    ap.add_argument("--class", dest="klass",
                    help="LaTeX class name (default: from --short)")
    ap.add_argument("--archive", help="archive name (default: <class>-notes)")
    ap.add_argument("--no-example", action="store_true",
                    help="leave out the example document and drawing script")
    ap.add_argument("--update-toolkit", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    dest = a.dest.resolve()
    if a.update_toolkit:
        update_toolkit(dest, a.force)
        return
    if not a.title or not a.short:
        ap.error("--title and --short are required for a new project")
    cls = a.klass or slug(a.short)
    values = {
        "TITLE": a.title,
        "SHORT": a.short,
        "PROJECT": a.project or a.title,
        "AUTHOR": a.author,
        "COPYRIGHT": a.copyright,
        "CLASS": cls,
        "ARCHIVE": a.archive or cls + "-notes",
    }
    if (dest / "contents.yaml").exists() and not a.force:
        sys.exit("%s already holds a project (it has contents.yaml). Use "
                 "--update-toolkit to refresh its scripts, or --force to "
                 "scaffold over it." % dest)
    dest.mkdir(parents=True, exist_ok=True)
    write_all(plan_new(dest, values, not a.no_example), a.force)
    for folder in ("figures", "src", "scripts/figures", "originals", "work"):
        (dest / folder).mkdir(parents=True, exist_ok=True)
    print("\nNext: put the originals in originals/, then see BUILD.md for the "
          "one-time installs (lualatex, pandoc, cairosvg, pypdf, sphinx, "
          "myst-parser, furo, pyyaml, playwright, mathjax).")


if __name__ == "__main__":
    main()
