#!/usr/bin/env python3
"""
Assemble the deliverable archive from an explicit manifest.

Usage:
    python3 package.py                 # writes <archive>.zip (contents.yaml)
    python3 package.py --out DIR       # also copy the zip to DIR
    python3 package.py --with-site     # include the built website
    python3 package.py --list          # show what would go in, write nothing

Earlier archives were put together by globbing the working directory, which is
how a renamed figure's old file, a superseded drawing script and a directory of
backups all ended up shipped. This builds the archive from a stated list
instead, and refuses to run if the figure audit fails, so a stale file has to be
added deliberately rather than merely left lying around.

The archive mirrors the working folder: unzip it and every command in BUILD.md
runs as written. An earlier version sorted the files by role into markdown/,
latex/, build/ and docs/, which read well as a listing but meant the archive
could not be built in, and did not match what the project actually looks like.

What stays out: the staging directory web/, LaTeX's auxiliary files, the figure PDFs that cairosvg generates in figures/,
__pycache__, node_modules, and anything on disk that no document references.
"""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIGDIR = HERE / "figures"
FIGSCRIPTS = HERE / "scripts" / "figures"
import contents                                    # noqa: E402
NAME = contents.site("archive")

# The documents come from contents.yaml, in reading order, whether or not the
# website publishes them: the archive is the whole project, and a document is
# held back from the site precisely so that its PDF can be proofread.
# Each document's Markdown, generated .tex and PDF sit together: in src/ for a
# lecture, in the year folder for course-year material.

# Everything else. A name that is not here does not ship.
SUPPORT = [
    contents.site("latex_class") + ".cls", "contents.yaml", "contents.py",
    "md2tex.py", "buildtex.py", "mkweb.py", "checkweb.py", "package.py",
    "scripts/figures_audit.py", "scripts/figures/figlib.py",
    "BUILD.md", "CONVENTIONS.md", ".gitignore", "package.json",
] + list(contents.site("support"))

MD_REF = re.compile(r"\]\(([^)\s]+\.svg)\)")


def figure_scripts():
    return sorted("scripts/figures/" + p.name
                  for p in FIGSCRIPTS.glob("make_figures_*.py"))


def figures_for(md_rel):
    md = HERE / md_rel
    if not md.exists():
        return []
    return sorted({Path(n).name
                   for n in MD_REF.findall(md.read_text(encoding="utf-8"))})


def manifest(with_site=False):
    """Return a list of (path on disk, path in the archive)."""
    items, missing = [], []

    def add(rel):
        src = HERE / rel
        if src.exists():
            items.append((src, f"{NAME}/{rel}"))
        else:
            missing.append(rel)

    for doc in contents.documents():
        add(doc.path)
        add(f"{doc.stem}.tex")
        add(f"{doc.stem}.pdf")
        for fig in figures_for(doc.path):
            add(f"figures/{fig}")

    for name in figure_scripts() + SUPPORT:
        add(name)

    if with_site:
        site = HERE / "site"
        for p in sorted(site.rglob("*")):
            if p.is_file():
                items.append((p, f"{NAME}/site/{p.relative_to(site)}"))

    # de-duplicate, keeping the first destination for a given source
    seen, unique = set(), []
    for src, dest in items:
        if dest in seen:
            continue
        seen.add(dest)
        unique.append((src, dest))
    return unique, missing


def main():
    args = sys.argv[1:]
    with_site = "--with-site" in args
    listing = "--list" in args
    out_dir = None
    if "--out" in args:
        out_dir = Path(args[args.index("--out") + 1])

    audit = subprocess.run([sys.executable,
                            str(HERE / "scripts" / "figures_audit.py")],
                           capture_output=True, text=True)
    if audit.returncode:
        sys.stderr.write(audit.stdout)
        sys.exit("figure audit failed: fix it before packaging")

    items, missing = manifest(with_site)

    if missing:
        print("not on disk, left out of the archive:")
        for m in sorted(set(missing)):
            print("   ", m)
        print()

    if listing:
        for _, dest in items:
            print(dest)
        print(f"\n{len(items)} file(s)")
        return

    zip_path = HERE / f"{NAME}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for src, dest in items:
            z.write(src, dest)

    size = zip_path.stat().st_size / 1e6
    print(f"wrote {zip_path.name}: {len(items)} files, {size:.1f} MB")
    by_part = {}
    for _, dest in items:
        rest = dest.split("/", 1)[1]
        part = rest.split("/")[0] if "/" in rest else "(top level)"
        by_part[part] = by_part.get(part, 0) + 1
    for part in sorted(by_part):
        print(f"    {part}: {by_part[part]}")

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / zip_path.name).write_bytes(zip_path.read_bytes())
        print(f"copied to {out_dir}")


if __name__ == "__main__":
    main()
