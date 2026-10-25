#!/usr/bin/env python3
"""
Build a tagged PDF/UA-1 file from one of the project's LaTeX sources, then check
its structure.

Usage:
    python3 buildtex.py 09_Mixtures              # src/09_Mixtures.tex -> .pdf
    python3 buildtex.py homework01_solution      # 2026/homework01_solution.tex
    python3 buildtex.py src/09_Mixtures.tex      # by path
    python3 buildtex.py --all

Run md2tex.py first: this builds from the .tex it writes. The PDF and LaTeX's
scratch files (.aux, .log) are written beside the .tex, which is beside the
Markdown.

Steps:
  1. every figure the .tex includes is converted from SVG to PDF with cairosvg,
     but only when the SVG is newer than the PDF;
  2. lualatex runs twice, so the page count in the footer settles;
  3. twelve checks run against the result.

Ten are structural checks on the tagged PDF: language, tagging, structure
tree, title, PDF/UA identifier, heading levels (read through the role map,
because the tagging code emits its own tag names and maps them onto the
standard ones), figure alt text and table headers. The eleventh counts the
formulas whose alternative text is raw LaTeX, which is the thing to watch
when the TeX Live in use is too old to tag mathematics properly; see
BUILD.md. The twelfth reads the LaTeX log for characters the fonts lack,
which LaTeX drops from the page silently. Lines or tables too wide for the
page, and pages whose text runs past the bottom margin, are reported as
warnings.
"""

import re
import subprocess
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
FIGDIR = HERE / "figures"       # the SVG sources and their PDF conversions
GRAPHIC = re.compile(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}")


# --------------------------------------------------------------------------
# figures
# --------------------------------------------------------------------------

def make_figures(tex):
    """Convert each included figure from SVG to PDF when it is out of date."""
    import cairosvg
    made = 0
    for name in GRAPHIC.findall(tex.read_text(encoding="utf-8")):
        pdf = HERE / name
        svg = pdf.with_suffix(".svg")
        if not svg.exists():
            sys.exit(f"missing figure source: {svg.name}")
        if pdf.exists() and pdf.stat().st_mtime >= svg.stat().st_mtime:
            continue
        cairosvg.svg2pdf(url=str(svg), write_to=str(pdf))
        made += 1
    if made:
        print(f"converted {made} figure(s) to PDF")


# --------------------------------------------------------------------------
# latex
# --------------------------------------------------------------------------

def run_latex(tex, passes=2):
    """Compile from the project root, keeping LaTeX's scratch files out of it.

    Running from the root is what makes the class file and the figures, which
    md2tex.py writes as root-relative paths ("figures/fig_c09_01_….pdf"),
    resolve whichever folder the .tex itself sits in.

    The scratch files and the PDF are written beside the .tex: src/ for a
    lecture, the course-year folder (2026/) for a homework set,
    so a document's source, LaTeX and PDF always sit together.
    """
    workdir = tex.parent
    rel = tex.relative_to(HERE) if tex.is_absolute() else tex
    out_rel = workdir.relative_to(HERE)
    for k in range(passes):
        proc = subprocess.run(
            ["lualatex", "-interaction=nonstopmode", "-halt-on-error",
             "-output-directory=" + str(out_rel), str(rel)],
            cwd=HERE, capture_output=True, text=True)
        if proc.returncode:
            log = workdir / (tex.stem + ".log")
            text = log.read_text(errors="replace") if log.exists() else proc.stdout
            errs = [ln for ln in text.splitlines() if ln.startswith("! ")]
            print("\n".join(errs[:12]) or proc.stdout[-2000:], file=sys.stderr)
            sys.exit(f"lualatex failed on {tex.name} (pass {k + 1})")
    final = workdir / (tex.stem + ".pdf")
    print("wrote", str(final.relative_to(HERE)).replace("\\", "/"))
    return final


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

STANDARD_HEADINGS = {"/H1", "/H2", "/H3", "/H4", "/H5", "/H6"}


def walk(node, rolemap, tags, alts, formulas, depth=0, out=None):
    if depth > 120:
        return
    obj = node.get_object() if hasattr(node, "get_object") else node
    if isinstance(obj, list):
        for k in obj:
            walk(k, rolemap, tags, alts, formulas, depth + 1, out)
        return
    if not isinstance(obj, dict):
        return
    s = obj.get("/S")
    if s is not None:
        name = str(s)
        std = rolemap.get(name, name)
        tags[std] += 1
        if std in STANDARD_HEADINGS and out is not None:
            out.append(int(std[2:]))
        if std == "/Formula":
            formulas.append(obj)
        # Only a figure's alt text counts towards check 9. Equations carry
        # alt text too, where the Markdown gave them a spoken form, and
        # counting those would let a figure without alt text hide behind them.
        if std == "/Figure" and "/Alt" in obj:
            alts.append(str(obj["/Alt"]))
    k = obj.get("/K")
    if k is not None:
        walk(k, rolemap, tags, alts, formulas, depth + 1, out)


WIDE = []   # overfull boxes of the last document checked
TALL = []   # (page, points) of pages whose text runs past the bottom


def verify(pdf):
    from pypdf import PdfReader
    reader = PdfReader(str(pdf))
    root = reader.trailer["/Root"]
    checks, failures = [], 0

    def check(name, ok, note=""):
        nonlocal failures
        checks.append((name, ok, note))
        if not ok:
            failures += 1

    check("document language set", root.get("/Lang") is not None)
    mark = root.get("/MarkInfo")
    mark = mark.get_object() if mark is not None else {}
    check("marked as tagged", bool(mark.get("/Marked")))
    has_tree = "/StructTreeRoot" in root
    check("structure tree present", has_tree)

    title = (reader.metadata or {}).get("/Title")
    check("document title in metadata", bool(title), str(title or ""))
    vp = root.get("/ViewerPreferences")
    vp = vp.get_object() if vp is not None else {}
    check("title shown in window bar", bool(vp.get("/DisplayDocTitle")))

    part = None
    md = root.get("/Metadata")
    if md is not None:
        xmp = md.get_object().get_data().decode("utf-8", "replace")
        m = re.search(r"pdfuaid:part>([^<]*)", xmp)
        part = m.group(1) if m else None
    check("PDF/UA identifier in XMP", part is not None, f"part {part}")

    tags, alts, formulas, levels = Counter(), [], [], []
    if has_tree:
        st = root["/StructTreeRoot"].get_object()
        rm = st.get("/RoleMap")
        rolemap = ({str(k): str(v) for k, v in rm.get_object().items()}
                   if rm is not None else {})
        walk(st, rolemap, tags, alts, formulas, out=levels)

    check("headings start at level 1", bool(levels) and levels[0] == 1)
    skipped = [(a, b) for a, b in zip(levels, levels[1:]) if b - a > 1]
    check("no skipped heading levels", not skipped, str(skipped[:3]))

    figures = tags.get("/Figure", 0)
    fig_alts = sum(1 for a in alts if a)
    check("every figure has alt text", fig_alts >= figures,
          f"{fig_alts} alt for {figures} figures")

    has_table = tags.get("/Table", 0) > 0
    check("table headers are tagged", (not has_table) or tags.get("/TH", 0) > 0,
          f"{tags.get('/TH', 0)} header cells")

    # The eleventh check. A formula whose only alternative text is its own
    # LaTeX source reads aloud as "backslash frac" and so on, which is worse
    # than no formula tagging at all.
    bad = 0
    for f in formulas:
        act = str(f.get("/ActualText", "")) + str(f.get("/Alt", ""))
        if "\\" in act or "LaTeX formula" in act:
            bad += 1
    check("formula alternative text is not raw LaTeX", bad == 0,
          f"{bad} of {len(formulas)} formulas carry LaTeX source")

    # Two faults the PDF structure cannot show, read from LaTeX's own log. A
    # character the text font lacks (a vertical ellipsis, a circled digit)
    # is dropped from the page with nothing but a log line to say so, so it
    # fails the build. A box too wide for the page is reported, not failed,
    # since a few points over is invisible; tens of points is a table or an
    # equation running off the page.
    log = pdf.with_suffix(".log")
    text = log.read_text(errors="replace") if log.exists() else ""
    missing = sorted(set(re.findall(r"Missing character: There is no (\S+)",
                                    text)))
    check("no characters missing from the fonts", not missing,
          ", ".join(missing[:8]))
    WIDE.clear()
    WIDE.extend(float(w) for w in
                re.findall(r"Overfull \\hbox \(([0-9.]+)pt too wide\)", text)
                if float(w) > 10)
    # A page too tall: top floats left less room than the block of text that
    # follows them (a display, a minipage), which cannot be split, so it runs
    # down towards the running foot. The page is the next one shipped out.
    # Nothing in the class prevents this without cost: placing the floats
    # with [ht] and a larger \textfraction pushes figures pages away from
    # their text, and shrinkable space reflows every document. A few points
    # is invisible, so only more than 6 pt is reported.
    TALL.clear()
    for m in re.finditer(r"Overfull \\vbox \(([0-9.]+)pt too high\) has "
                         r"occurred while \\output is active", text):
        page = re.search(r"\[(\d+)", text[m.end():])
        if float(m.group(1)) > 6:
            TALL.append((page.group(1) if page else "?", float(m.group(1))))

    print(f"\npages: {len(reader.pages)}")
    print("tags: ", dict(tags))
    print()
    for name, ok, note in checks:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name}" + (f"   ({note})" if note else ""))
    print()
    if WIDE:
        print(f"  [WARN] {len(WIDE)} line(s) or table(s) too wide for the page, "
              f"by up to {max(WIDE):.0f} pt: see 'Overfull' in the .log")
        print()
    if TALL:
        print(f"  [WARN] text runs past the bottom of the page, towards the "
              f"running foot: "
              + ", ".join(f"page {p} by {pt:.0f} pt" for p, pt in TALL))
        print()
    if failures:
        print(f"{failures} check(s) failed.")
    else:
        print("All structural checks passed.")
    print("Passing these is necessary, not sufficient. "
          "Run a validator such as PAC 2024 before publishing.")
    return failures


def tex_for(doc):
    """Where md2tex.py puts a document's LaTeX: beside its Markdown."""
    return HERE / (doc.stem + ".tex")


def tex_sources():
    """Every document's .tex, in the order contents.yaml lists them.

    Every document, not only the published ones: a document is held back from
    the website precisely so that its PDF can be proofread.
    """
    import contents
    return [tex_for(d) for d in contents.documents()]


def resolve(name):
    """Accept a document name, a bare .tex name, or a path."""
    import contents
    doc = contents.find(str(name))
    if doc is not None and tex_for(doc).exists():
        return tex_for(doc).resolve()
    p = Path(name)
    for cand in (p, HERE / p):
        if cand.exists() and cand.suffix == ".tex":
            return cand.resolve()
    return None


def build(name):
    tex = resolve(name)
    if tex is None:
        sys.exit(f"no such file: {name}")
    make_figures(tex)
    pdf = run_latex(tex)
    return verify(pdf)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--all":
        targets = tex_sources()
    else:
        targets = [Path(a) for a in args]
    worst = 0
    for t in targets:
        print("=" * 68)
        print(t.name)
        worst = max(worst, build(t))
    sys.exit(1 if worst else 0)


if __name__ == "__main__":
    main()
