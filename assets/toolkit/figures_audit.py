#!/usr/bin/env python3
"""
Check that the figures on disk and the figures the documents ask for agree.

Usage:
    python3 scripts/figures_audit.py            # report
    python3 scripts/figures_audit.py --delete   # report, and remove the orphans

Two things go wrong over time and neither shows up in any other check. A figure
can be renamed in its drawing script while an older file of the old name stays
behind, so the directory accumulates images nothing uses and they end up in the
next archive. Or a document can reference a figure that no script writes any
more, which fails the build only when someone rebuilds that one document.

So this compares three sets:

  * every .svg in figures/;
  * every figure referenced from a Markdown source;
  * every figure name a scripts/figures/make_figures_*.py script writes.

A figure missing from disk, or sitting on disk with nothing referencing it, is
an error. A figure whose name a script builds at run time rather than writing
out as a literal string cannot be traced statically, so those are listed
separately as unverifiable rather than counted against the run.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # scripts/
ROOT = HERE.parent                              # the project root
FIGDIR = ROOT / "figures"
SCRIPTS = HERE / "figures"                      # the drawing scripts
sys.path.insert(0, str(ROOT))                   # for contents.py

MD_REF = re.compile(r"\]\(([^)\s]+\.svg)\)")
SCRIPT_WRITE = re.compile(r'write\(\s*["\']([^"\']+\.svg)["\']')

def documents():
    """Every document in contents.yaml, held back from the website or not."""
    import contents
    return [d.file for d in contents.documents()]


def collect():
    on_disk = {p.name for p in FIGDIR.glob("*.svg")}

    referenced = {}
    for md in documents():
        label = str(md.relative_to(ROOT)).replace("\\", "/")
        for name in MD_REF.findall(md.read_text(encoding="utf-8")):
            referenced.setdefault(Path(name).name, set()).add(label)

    written = {}
    for script in sorted(SCRIPTS.glob("make_figures*.py")):
        for name in SCRIPT_WRITE.findall(script.read_text(encoding="utf-8")):
            written.setdefault(name, set()).add(script.name)

    return on_disk, referenced, written


def main():
    on_disk, referenced, written = collect()
    delete = "--delete" in sys.argv

    missing = sorted(set(referenced) - on_disk)
    orphans = sorted(on_disk - set(referenced))
    # A name that no script contains as a literal may still be drawn: several
    # scripts build the file name in a loop or take it as an argument. Those
    # are reported for information, not as failures, and the proof that they
    # are drawn is that the file is on disk.
    dynamic = sorted((set(referenced) - set(written)) & on_disk)
    undrawn = sorted(set(referenced) - set(written) - on_disk)
    unused_output = sorted(set(written) - set(referenced))

    def report(title, names, detail=None):
        if not names:
            return 0
        print(f"\n{title} ({len(names)})")
        for n in names:
            extra = ""
            if detail and n in detail:
                extra = "   " + ", ".join(sorted(detail[n]))
            print(f"    {n}{extra}")
        return len(names)

    problems = 0
    # A document missing from contents.yaml is silently absent from the
    # website, the archive and every other check, so it is caught here, where
    # package.py already refuses to run on a failure.
    import contents
    gone, unlisted = contents.discrepancies()
    problems += report("listed in contents.yaml but not on disk", gone)
    problems += report("on disk but not listed in contents.yaml", unlisted)
    problems += report("referenced by a document but not on disk", missing,
                       referenced)
    problems += report("on disk but referenced by no document", orphans)
    problems += report("referenced, not on disk, and written by no script",
                       undrawn, referenced)
    problems += report("written by a script but used by no document",
                       unused_output, written)

    if dynamic:
        print(f"\nnames built at run time, not traceable to a literal "
              f"(all present on disk) ({len(dynamic)})")
        for n in dynamic:
            print(f"    {n}")

    if delete and orphans:
        for name in orphans:
            (FIGDIR / name).unlink()
        print(f"\ndeleted {len(orphans)} orphan(s)")
        problems -= len(orphans)

    print()
    if problems:
        print(f"{problems} discrepancy(ies).")
    else:
        print(f"All {len(on_disk)} figures are referenced, drawn and present.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
