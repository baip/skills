#!/usr/bin/env python3
"""
Flag the notation compromises a transcription should not keep.

Usage:
    python3 notation_lint.py src/*.md 2026/*.md
    python3 notation_lint.py --errors-only src/05_Equilibrium.md

The builds check structure, not notation, so an equation can pass every
check while its limits are given in words, a struck term is described in a
sentence, or a symbol outside the mathematics is silently dropped from the
PDF. This reads the Markdown and reports, with line numbers:

  error    an alt block that holds more or fewer than one display equation,
           or whose sentence contains LaTeX or a double quote
  error    a character outside the mathematics that the PDF text font is
           known to lack (⋮, ①, ′, ≪, ≫, π): write it as $...$
  error    an italic letter or a function name left outside the dollars
           (*a* $= ...$, ln $x$, e$^{...}$)
  warn     a superscript or subscript attached to prose (m$^{3}$,
           $^{4}$He): fine for units and isotopes, not for a variable
  warn     a flattened subscript (x_{U,\\, j} written without the comma)
  warn     limits given in words (from 0 to ∞, over all i, Π over i)
  warn     a sentence describing a hand annotation (the original strikes,
           braces, circles, underlines ...) that may want typesetting
  warn     \\left( \\frac{a}{b} \\right) around a bare fraction: keep the
           brackets only if the original draws them
  warn     an upright running index (_{\\mathrm{i}}): indices are italic
  info     an "About this transcription" note or an [Original page N ends
           here.] marker, which are removed before a document is handed over

Warnings are prompts to look at the original, not verdicts: a phrase such as
"over all states" can be prose that belongs in the text. Exit status is 1
when there are errors.
"""

import re
import sys
from pathlib import Path

ALT_BLOCK = re.compile(r'^::: \{\.eq alt="([^"]*)"\}\n(.*?)\n:::$', re.M | re.S)
ALT_ANY = re.compile(r'^::: \{\.eq alt=(.*)$', re.M)
MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$", re.S)
# Characters seen dropped from the PDFs in practice: the vertical ellipsis,
# circled digits, primes, much-less and much-greater, and pi. The authority
# is the build itself, whose twelfth check reads the LaTeX log; this only
# catches them earlier.
FONT_LACKS = re.compile("[\u22ee\u2460-\u2473\u2032\u2033\u226a\u226b\u03c0]")
REMNANT = re.compile(r"\*[A-Za-z]\* ?\$|\$\*[A-Za-z]\*|\bln \$|\be\$\^\{")
SCRIPT_ONLY = re.compile(r"(?<![\\\w])[A-Za-z]+\$[\^_]\{[^}]*\}\$|\$[\^_]\{[^}]*\}\$[A-Za-z]")
FLAT_SUB = re.compile(r"_\{[^{}]*[^,{\s]\\,\s*[a-zA-Z]\}|\\vec\{[a-z]\}[a-z]\}")
WORD_LIMITS = re.compile(r"\bfrom \$?[-−]?[0-9a-zA-Z∞\\]+\$? to \$?[-−+]?[0-9a-zA-Z∞\\]"
                         r"|“Π over|“Σ over|\bsummed over\b|\bover all [a-z]\b",
                         re.I)
ANNOTATION = re.compile(r"\bthe original (?:strikes|braces|circles|underlines|"
                        r"rings|boxes|labels|marks|crosses)\b"
                        r"|\b(?:struck|crossed) out\b", re.I)
PAREN_FRAC = re.compile(r"\\left\(\\frac\{[^{}]{1,4}\}\{[^{}]{1,4}\}\\right\)")
UPRIGHT_INDEX = re.compile(r"_\{\\mathrm\{[ijkln]\}\}")
NOTE = re.compile(r"^## About this transcription", re.M)
PAGE = re.compile(r"^\[Original page[^\]]*\]\{\.src\}", re.M)
LATEXY = re.compile(r"\\[A-Za-z]|[_^{}$]")


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def closing_start(text):
    m = re.search(r"^## Notes on changes made for accessibility", text, re.M)
    return m.start() if m else len(text)


def lint(path):
    text = path.read_text(encoding="utf-8")
    body_end = closing_start(text)
    out = []

    def add(level, pos, kind, snippet):
        out.append((level, line_of(text, pos), kind,
                    snippet.replace("\n", " ")[:90]))

    blocks = {m.start(): m for m in ALT_BLOCK.finditer(text)}
    for m in ALT_ANY.finditer(text):
        b = blocks.get(m.start())
        if b is None:
            add("error", m.start(), "alt block not closed or alt not quoted",
                m.group(0))
            continue
        alt, body = b.group(1), b.group(2)
        n = len(re.findall(r"^\$\$", body, re.M))
        if n != 1:
            add("error", m.start(), "alt block holds %d display equations" % n,
                alt)
        if LATEXY.search(alt):
            add("error", m.start(), "LaTeX in alt text", alt)

    # prose only: the text with the mathematics, link targets, attribute
    # blocks and code removed, keeping offsets so line numbers stay right
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    prose = re.sub(r"^---\n.*?\n---\n", blank, text, count=1, flags=re.S)
    prose = MATH.sub(blank, prose)
    prose = re.sub(r"```.*?```", blank, prose, flags=re.S)
    prose = re.sub(r"\]\([^)]*\)\{[^}]*\}", blank, prose)
    prose = re.sub(r'alt="[^"]*"', blank, prose)
    for m in FONT_LACKS.finditer(prose):
        add("error", m.start(), "character the PDF text font lacks",
            text[max(0, m.start() - 30):m.end() + 30])
    for m in REMNANT.finditer(text):
        add("error", m.start(), "letter or function outside the mathematics",
            text[max(0, m.start() - 20):m.end() + 30])
    for m in SCRIPT_ONLY.finditer(text):
        add("warn", m.start(), "script attached to prose (units, isotopes and "
            "term symbols may be fine; a variable is not)",
            text[max(0, m.start() - 20):m.end() + 20])
    for m in FLAT_SUB.finditer(text):
        add("warn", m.start(), "flattened subscript", m.group(0))
    for m in WORD_LIMITS.finditer(prose[:body_end]):
        add("warn", m.start(), "limits given in words?",
            text[max(0, m.start() - 30):m.end() + 30])
    for m in ANNOTATION.finditer(prose[:body_end]):
        add("warn", m.start(), "annotation described in words?",
            text[max(0, m.start() - 20):m.end() + 50])
    for m in PAREN_FRAC.finditer(text):
        add("warn", m.start(), "brackets round a bare fraction", m.group(0))
    ups = list(UPRIGHT_INDEX.finditer(text))
    if ups:
        add("warn", ups[0].start(),
            "upright running index (%d in the file)" % len(ups), ups[0].group(0))
    for m in NOTE.finditer(text):
        add("info", m.start(), "About-this-transcription note", m.group(0))
    pages = list(PAGE.finditer(text))
    if pages:
        add("info", pages[0].start(),
            "%d original-page markers" % len(pages), pages[0].group(0))
    return out


def main():
    args = sys.argv[1:]
    errors_only = "--errors-only" in args
    files = [Path(a) for a in args if not a.startswith("--")]
    if not files:
        sys.exit(__doc__)
    n_err = 0
    for f in files:
        rows = lint(f)
        for level, ln, kind, snip in rows:
            if errors_only and level != "error":
                continue
            print("%s:%d: %s: %s: %s" % (f, ln, level, kind, snip))
        n_err += sum(1 for r in rows if r[0] == "error")
        counts = {}
        for r in rows:
            counts[r[0]] = counts.get(r[0], 0) + 1
        print("%s: %s" % (f, ", ".join("%d %s" % (v, k) for k, v in
                                       sorted(counts.items())) or "clean"))
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
