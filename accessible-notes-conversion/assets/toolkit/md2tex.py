#!/usr/bin/env python3
"""
Build step: accessible Markdown -> LaTeX for the project's document class.

Usage:
    python3 md2tex.py 09_Mixtures               # writes src/09_Mixtures.tex
    python3 md2tex.py src/09_Mixtures.md        # the same, by path
    python3 md2tex.py homework01_solution       # writes 2026/homework01_solution.tex
    python3 md2tex.py --all                     # every document

A document can be named by its path or by its bare name as contents.yaml
lists it. The .tex is always written beside the .md it comes from.

The Markdown is the source of truth and the .tex is generated output, so this
runs on every build and its output is overwritten each time. Fix a document by
editing its .md, never its .tex.

Mathematics written as Unicode running text (italic variables as emphasis,
~x~ and ^x^ for scripts) is still compiled to LaTeX by the passes below, so a
transcription that slipped into that older style is caught rather than
printed as prose.

How it works
------------
Structure is taken from pandoc's abstract syntax tree, so lists, tables,
figures, fenced divs and headings are converted by pandoc's own parser rather
than by pattern matching on the Markdown.

Mathematics between dollar signs is passed through. Anything else that looks
like mathematics goes through four passes:

  1. inlines_to_tokens  turns the syntax tree into typed atoms
  2. fold_fractions     turns a slash between two factors into \\frac
  3. fold_integrals     turns "from A to B" into the limits of the preceding
                        integral sign
  4. render             emits LaTeX

Greek letters, relations and most operators pass through untouched, because the
class loads unicode-math under LuaLaTeX and those characters are valid math
input there. Accents are the exception: a precomposed or combining mark is
rewritten as \\hat, \\tilde, \\bar or \\dot so that it sits at the right height
over its base letter.

Anything the converter cannot resolve confidently is left as readable LaTeX and
reported on standard error with its source line, so it can be fixed in the
Markdown. The three kinds are: prose inside an equation, an integral or sum whose limits are given
in words the "from A to B" rule does not match, and a fraction fold that
spanned more than a couple of tokens.
"""

import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIGDIR = HERE / "figures"       # the SVG sources and their PDF conversions

# --------------------------------------------------------------------------
# character tables
# --------------------------------------------------------------------------

# Marks that must become a LaTeX accent rather than a precomposed glyph,
# because the math fonts have no composed form at the right height.
COMBINING = {
    "\u0302": "hat",      # circumflex, per unit mass
    "\u0303": "tilde",    # tilde, per mole
    "\u0304": "bar",      # macron, mean value
    "\u0305": "bar",      # overline
    "\u0307": "dot",      # dot, rate
    "\u20d7": "vec",      # combining arrow, vector
}

# Any precomposed character that decomposes into a base letter plus one of the
# marks above is handled the same way. Unicode's own decomposition data is used
# rather than a hand-written list, so V-tilde, rho-hat and the rest are all
# covered without anyone having to remember them.

def decompose_accent(ch):
    """Return (accent, base) for a precomposed character, else None."""
    nfd = unicodedata.normalize("NFD", ch)
    if len(nfd) == 2 and nfd[1] in COMBINING:
        return COMBINING[nfd[1]], nfd[0]
    return None


# Characters that need an explicit command rather than passing through.
SYMBOL = {
    "·": r"\cdot", "×": r"\times", "÷": r"\div",
    "−": "-", "–": "-", "—": r"\text{---}",
    "≈": r"\approx", "≅": r"\cong", "≡": r"\equiv",
    "≤": r"\le", "≥": r"\ge", "≠": r"\ne",
    "∝": r"\propto", "∞": r"\infty",
    "→": r"\to", "←": r"\gets", "↔": r"\leftrightarrow",
    "⟶": r"\longrightarrow", "⟹": r"\implies", "⇒": r"\Rightarrow",
    "⟨": r"\langle", "⟩": r"\rangle",
    "⋯": r"\cdots", "…": r"\dots", "⋮": r"\vdots",
    "∴": r"\therefore", "∵": r"\because",
    "∂": r"\partial", "∇": r"\nabla",
    "∫": r"\int", "∮": r"\oint", "∬": r"\iint",
    "Σ": r"\sum", "∑": r"\sum", "Π": r"\prod", "∏": r"\prod",
    "√": r"\sqrt", "±": r"\pm", "∓": r"\mp",
    "∈": r"\in", "∉": r"\notin", "⊂": r"\subset", "∅": r"\emptyset",
    "½": r"\tfrac{1}{2}", "⅓": r"\tfrac{1}{3}", "¼": r"\tfrac{1}{4}",
    "°": r"^\circ", "′": r"'", "″": r"''",
    "ℋ": r"\mathcal{H}", "ℒ": r"\mathcal{L}", "ℛ": r"\mathcal{R}",
    "⟂": r"\perp", "∥": r"\parallel", "∎": "",
    "\u00a0": r"\,", "\u2009": r"\,", "\u2007": r"\;",
}

# Multi-letter runs that are operators, not prose.
# "min" and "max" are deliberately absent: in these notes they are minutes and
# a maximum value, never the operators \min and \max.
FUNCS = {"ln", "log", "exp", "sin", "cos", "tan", "sinh", "cosh", "tanh",
         "lim", "det", "erf", "sgn", "arg"}

# Words that appear inside equations as ordinary prose. Anything else made of
# letters and longer than one character is reported for review.
KNOWN_PROSE = re.compile(
    r"^(?:and|or|of|for|with|when|where|which|is|are|at|in|on|to|from|the|a|an"
    r"|if|then|so|that|all|any|each|over|along|path|large|small|const|constant"
    r"|otherwise|ideal|gas|monatomic|diatomic|true|false|law|first|second"
    r"|noting|assuming|since|because|therefore|hence|thus|yields|gives)$",
    re.I)

ESCAPE_TEXT = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$",
    "&": r"\&", "#": r"\#", "_": r"\_", "%": r"\%", "~": r"$\sim$",
    "^": r"\textasciicircum{}",
}


def esc_bookmark(s):
    """Escape for a PDF bookmark: LaTeX specials only, no mathematics.

    A bookmark is plain text, so the arrows, infinity signs and Greek letters
    stay as the Unicode characters they already are. Putting $...$ in here is
    what "Improper alphabetic constant" means.
    """
    out = []
    for c in s:
        if c in "\\{}$&#_%~^":
            out.append(" ")
        else:
            out.append(c)
    return "".join(out)


def esc_text(s):
    """Escape a string for LaTeX text mode."""
    s = s.replace("\u201c", "``").replace("\u201d", "''")
    s = s.replace("\u2018", "`").replace("\u2019", "'")
    return "".join(ESCAPE_TEXT.get(c, c) for c in s)


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.items = []

    def add(self, kind, detail, context):
        self.items.append((kind, detail, context))

    def dump(self, stem):
        if not self.items:
            print(f"{stem}: nothing flagged for review", file=sys.stderr)
            return
        by_kind = {}
        for kind, detail, ctx in self.items:
            by_kind.setdefault(kind, []).append((detail, ctx))
        print(f"\n{stem}: {len(self.items)} item(s) to review", file=sys.stderr)
        for kind, rows in sorted(by_kind.items()):
            print(f"  {kind} ({len(rows)})", file=sys.stderr)
            seen = set()
            for detail, ctx in rows:
                key = (detail, ctx)
                if key in seen:
                    continue
                seen.add(key)
                print(f"    {detail}\n        in: {ctx}", file=sys.stderr)


REPORT = Report()

# Every figure label defined in the document, and every cross-reference made
# to one. They are compared at the end: a reference with no figure behind it
# prints "Figure ??" in the PDF and nothing else would say so.
LABELS = set()
REFS = set()


# --------------------------------------------------------------------------
# pass 1: syntax tree -> tokens
# --------------------------------------------------------------------------

def split_accents(s):
    """Yield (char, accent-or-None), decomposing precomposed and combining."""
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        acc = None
        d = decompose_accent(ch)
        if d is not None:
            acc, ch = d
        if i + 1 < len(s) and s[i + 1] in COMBINING:
            acc = COMBINING[s[i + 1]]
            i += 1
        out.append((ch, acc))
        i += 1
    return out


def str_to_tokens(s):
    """Tokenise a plain (non-emphasised) run inside an equation."""
    toks, i = [], 0
    pairs = split_accents(s)
    while i < len(pairs):
        ch, acc = pairs[i]
        if acc:
            toks.append({"k": "acc", "a": acc, "v": [{"k": "var", "v": ch}]})
            i += 1
            continue
        if ch in SYMBOL:
            toks.append({"k": "sym", "v": SYMBOL[ch]})
            i += 1
            continue
        if ch.isdigit() or ch == ".":
            j = i
            while j < len(pairs) and (pairs[j][0].isdigit() or pairs[j][0] == "."):
                j += 1
            toks.append({"k": "num", "v": "".join(p[0] for p in pairs[i:j])})
            i = j
            continue
        if ch.isalpha() and not ch.isascii():
            # Greek and the like: a variable in its own right.
            toks.append({"k": "var", "v": ch})
            i += 1
            continue
        if ch.isalpha():
            j = i
            while (j < len(pairs) and pairs[j][0].isalpha()
                   and pairs[j][0].isascii() and not pairs[j][1]):
                j += 1
            word = "".join(p[0] for p in pairs[i:j])
            if word.lower() in FUNCS:
                toks.append({"k": "sym", "v": "\\" + word.lower()})
            elif len(word) == 1:
                # A lone upright letter: the differential d, and little else.
                toks.append({"k": "up", "v": word})
            else:
                toks.append({"k": "text", "v": word})
            i = j
            continue
        if ch == "/":
            toks.append({"k": "slash"})
        elif ch in "([{":
            toks.append({"k": "open", "v": ch})
        elif ch in ")]}":
            toks.append({"k": "close", "v": ch})
        elif ch in "+=<>|!,;:'":
            toks.append({"k": "op", "v": ch})
        elif ch == "-":
            toks.append({"k": "op", "v": "-"})
        elif ch == " ":
            toks.append({"k": "space"})
        elif ch.isspace():
            toks.append({"k": "space"})
        else:
            # Greek and anything else unicode-math handles directly.
            toks.append({"k": "var", "v": ch})
        i += 1
    return toks


def inlines_to_tokens(inls, ctx):
    toks = []
    for n in inls:
        t = n["t"]
        if t == "Str":
            toks += str_to_tokens(n["c"])
        elif t == "Space":
            toks.append({"k": "space"})
        elif t == "SoftBreak":
            toks.append({"k": "space"})
        elif t == "Emph":
            inner = inlines_to_tokens(n["c"], ctx)
            # Emphasis inside an equation marks a variable: keep it italic by
            # leaving letters as ordinary math letters.
            for tk in inner:
                if tk["k"] == "up":
                    tk["k"] = "var"
                elif tk["k"] == "text" and tk["v"].isalpha():
                    tk["k"] = "var"
            toks += inner
        elif t == "Strong":
            inner = inlines_to_tokens(n["c"], ctx)
            for tk in inner:
                if tk["k"] == "up":
                    tk["k"] = "var"
            toks.append({"k": "bold", "v": inner})
        elif t == "Subscript":
            toks.append({"k": "sub", "v": inlines_to_tokens(n["c"], ctx)})
        elif t == "Superscript":
            toks.append({"k": "sup", "v": inlines_to_tokens(n["c"], ctx)})
        elif t == "Span":
            classes = n["c"][0][1]
            inner = inlines_to_tokens(n["c"][1], ctx)
            if "vec" in classes:
                # the span marks a vector, but the letter inside usually
                # already carries the combining arrow, and the subscript that
                # follows it is not part of the arrow's reach
                if any(tk["k"] == "acc" and tk["a"] == "vec" for tk in inner):
                    toks += inner
                else:
                    toks.append({"k": "acc", "a": "vec", "v": inner})
            else:
                toks += inner
        elif t == "Quoted":
            toks.append({"k": "text", "v": "\u201c"})
            toks += inlines_to_tokens(n["c"][1], ctx)
            toks.append({"k": "text", "v": "\u201d"})
        elif t == "Math":
            toks.append({"k": "raw", "v": n["c"][1]})
        elif t == "RawInline":
            toks.append({"k": "raw", "v": n["c"][1]})
        elif t == "Link":
            toks += inlines_to_tokens(n["c"][1], ctx)
        elif t == "Note":
            pass
        else:
            REPORT.add("unhandled inline in equation", t, ctx)
    return toks


# --------------------------------------------------------------------------
# pass 2: fractions
# --------------------------------------------------------------------------

FACTOR_KINDS = {"var", "num", "up", "sub", "sup", "acc", "sym", "raw", "grp",
                "bold", "frac", "sqrt"}


def _factor_before(toks, i):
    """Index range [a, i) of the factor immediately left of position i."""
    if i == 0:
        return None
    j = i - 1
    if toks[j]["k"] == "close":
        depth = 0
        while j >= 0:
            if toks[j]["k"] == "close":
                depth += 1
            elif toks[j]["k"] == "open":
                depth -= 1
                if depth == 0:
                    # keep any factors written directly in front of the
                    # bracket: in N(N-1)/p^2 the numerator is all of N(N-1)
                    a = j
                    while a > 0 and toks[a - 1]["k"] in FACTOR_KINDS:
                        a -= 1
                    return (a, i)
            j -= 1
        return None
    a = i
    while a > 0 and toks[a - 1]["k"] in FACTOR_KINDS:
        a -= 1
        # a symbol that is an operator, not a factor, stops the run
        if toks[a]["k"] == "sym" and toks[a]["v"] in (
                r"\to", r"\implies", r"\approx", r"\equiv", r"\le", r"\ge",
                r"\ne", r"\pm", r"\mp", r"\cdots", r"\dots", r"\int", r"\sum",
                r"\prod", r"\therefore"):
            a += 1
            break
    return (a, i) if a < i else None


def _factor_after(toks, i):
    """Index range (i, b] as a slice (i+1, b) of the factor right of i."""
    n = len(toks)
    if i + 1 >= n:
        return None
    j = i + 1
    if toks[j]["k"] == "open":
        depth = 0
        while j < n:
            if toks[j]["k"] == "open":
                depth += 1
            elif toks[j]["k"] == "close":
                depth -= 1
                if depth == 0:
                    return (i + 1, j + 1)
            j += 1
        return None
    b = i + 1
    while b < n and toks[b]["k"] in FACTOR_KINDS:
        if toks[b]["k"] == "sym" and toks[b]["v"] in (
                r"\to", r"\implies", r"\approx", r"\equiv", r"\int", r"\sum"):
            break
        b += 1
    return (i + 1, b) if b > i + 1 else None


def _strip_parens(seq):
    if len(seq) >= 2 and seq[0]["k"] == "open" and seq[-1]["k"] == "close":
        depth = 0
        for k, tk in enumerate(seq):
            if tk["k"] == "open":
                depth += 1
            elif tk["k"] == "close":
                depth -= 1
                if depth == 0 and k != len(seq) - 1:
                    return seq
        return seq[1:-1]
    return seq


def fold_fractions(toks, ctx):
    """Turn factor / factor into a \\frac group, innermost slash first."""
    # A slash written with spaces round it is still a fraction bar.
    trimmed = []
    for tk in toks:
        if tk["k"] == "slash":
            while trimmed and trimmed[-1]["k"] == "space":
                trimmed.pop()
        if (tk["k"] == "space" and trimmed
                and trimmed[-1]["k"] == "slash"):
            continue
        trimmed.append(tk)
    toks = trimmed
    changed = True
    while changed:
        changed = False
        for i, tk in enumerate(toks):
            if tk["k"] != "slash":
                continue
            left = _factor_before(toks, i)
            right = _factor_after(toks, i)
            if not left or not right:
                REPORT.add("slash left as a division sign",
                           "no factor on one side", ctx)
                toks[i] = {"k": "op", "v": "/"}
                changed = True
                break
            num = _strip_parens(toks[left[0]:left[1]])
            den = _strip_parens(toks[right[0]:right[1]])
            if len(num) > 8 or len(den) > 8:
                # Where the sides are long, what the slash divides is genuinely
                # ambiguous in the flat text, and guessing wrong turns
                # "exp(-bU) dr1 ... drN / Z" into a fraction over drN alone.
                # Leaving the division sign is the honest reading.
                REPORT.add("slash left as a division sign",
                           f"sides too long to group ({len(num)}/{len(den)})",
                           ctx)
                toks[i] = {"k": "op", "v": "/"}
                changed = True
                break
            frac = {"k": "frac", "n": num, "d": den}
            toks = toks[:left[0]] + [frac] + toks[right[1]:]
            changed = True
            break
    return toks


# --------------------------------------------------------------------------
# pass 3: integral and sum limits given in words
# --------------------------------------------------------------------------

BIG_OPS = {r"\int", r"\oint", r"\iint", r"\sum", r"\prod"}


def fold_sqrt(toks, ctx):
    """Turn a root sign followed by a bracketed group into \\sqrt{...}.

    The transcription writes a root as the character followed by parentheses,
    which is how it reads aloud, but LaTeX wants the radicand in braces and
    chokes on \\sqrt\\left(.
    """
    out, i = [], 0
    while i < len(toks):
        tk = toks[i]
        if not (tk["k"] == "sym" and tk["v"] == r"\sqrt"):
            out.append(tk)
            i += 1
            continue
        j = i + 1
        while j < len(toks) and toks[j]["k"] == "space":
            j += 1
        if j < len(toks) and toks[j]["k"] == "open":
            depth, k = 0, j
            while k < len(toks):
                if toks[k]["k"] == "open":
                    depth += 1
                elif toks[k]["k"] == "close":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            if k < len(toks):
                out.append({"k": "sqrt", "v": toks[j + 1:k]})
                i = k + 1
                continue
        # a bare root sign covering the next factor alone
        rng = _factor_after(toks, j - 1)
        if rng:
            out.append({"k": "sqrt", "v": toks[rng[0]:rng[1]]})
            i = rng[1]
            continue
        REPORT.add("root sign left without a radicand", "", ctx)
        out.append(tk)
        i += 1
    return out


def fold_integrals(toks, ctx):
    """Attach a trailing "from A to B" to the nearest preceding big operator."""
    out = list(toks)
    i = 0
    while i < len(out):
        tk = out[i]
        if not (tk["k"] == "text" and tk["v"].lower() == "from"):
            i += 1
            continue
        # find "to" after it
        j = i + 1
        while j < len(out) and not (out[j]["k"] == "text"
                                    and out[j]["v"].lower() == "to"):
            j += 1
        if j >= len(out):
            i += 1
            continue
        lo = [t for t in out[i + 1:j] if t["k"] != "space"]
        k = j + 1
        while k < len(out) and out[k]["k"] in ("space",):
            k += 1
        end = k
        while end < len(out) and out[end]["k"] in FACTOR_KINDS | {"frac"}:
            end += 1
        hi = [t for t in out[k:end] if t["k"] != "space"]
        # nearest big operator to the left that has no limits yet
        target = None
        for m in range(i - 1, -1, -1):
            if out[m]["k"] == "sym" and out[m]["v"] in BIG_OPS \
                    and "lo" not in out[m]:
                target = m
                break
        if target is None or not lo or not hi:
            REPORT.add("limits in words left as text",
                       "no operator to attach to" if target is None
                       else "could not read the range", ctx)
            i += 1
            continue
        out[target] = dict(out[target], lo=lo, hi=hi)
        # drop the words, leaving a preceding space tidy
        del out[i:end]
        while i > 0 and i - 1 < len(out) and out[i - 1]["k"] == "space":
            del out[i - 1]
            i -= 1
    return out


# --------------------------------------------------------------------------
# pass 4: render
# --------------------------------------------------------------------------

def merge_units(toks):
    """kJ/min and kg/m are units, not fractions: join them before folding."""
    out, i = [], 0
    while i < len(toks):
        if (i + 2 < len(toks) and toks[i]["k"] == "text"
                and toks[i + 1]["k"] in ("slash", "op")
                and toks[i + 1].get("v", "/") == "/"
                and toks[i + 2]["k"] == "text"):
            out.append({"k": "text",
                        "v": toks[i]["v"] + "/" + toks[i + 2]["v"]})
            i += 3
            continue
        out.append(toks[i])
        i += 1
    return out


NO_SPACE_BEFORE = "\u201d\u2019)],;.:"
NO_SPACE_AFTER = "\u201c\u2018(["


def _join_text(a, b):
    if b[:1] in NO_SPACE_BEFORE or a[-1:] in NO_SPACE_AFTER:
        return a + b
    return a + " " + b


def merge_text(toks):
    """Join neighbouring prose tokens into one run so \\text wraps them once."""
    out = []
    for tk in toks:
        if tk["k"] == "text" and out and out[-1].get("k") == "text":
            out[-1] = {"k": "text", "v": _join_text(out[-1]["v"], tk["v"])}
        elif (tk["k"] == "space" and out and out[-1].get("k") == "text"):
            out.append({"k": "pendingspace"})
        elif tk["k"] == "text" and out and out[-1].get("k") == "pendingspace":
            out.pop()
            out[-1] = {"k": "text", "v": _join_text(out[-1]["v"], tk["v"])}
        else:
            if out and out[-1].get("k") == "pendingspace":
                out[-1] = {"k": "space"}
            out.append(tk)
    if out and out[-1].get("k") == "pendingspace":
        out[-1] = {"k": "space"}
    return out


ACCENT_CMD = {"hat": r"\hat", "tilde": r"\tilde", "bar": r"\bar",
              "dot": r"\dot", "vec": r"\vec"}


# \left and \right as delimiter commands, not as the first six letters of
# \rightarrow, \leftrightarrow, \longrightarrow, \rightharpoonup and the
# rest. A control sequence is a maximal run of letters, so what tells them
# apart is simply whether a letter follows.
DELIM_CMD = re.compile(r"\\(left|right)(?![A-Za-z])")


def _delims_balanced(s):
    """True if every \\left is closed by a later \\right, and none is spare."""
    depth = 0
    for m in DELIM_CMD.finditer(s):
        depth += 1 if m.group(1) == "left" else -1
        if depth < 0:
            return False
    return depth == 0


def render(toks, ctx, top=True, in_script=False):
    if top:
        toks = merge_text(toks)
    out = []
    for tk in toks:
        k = tk["k"]
        if k == "var":
            out.append(tk["v"])
        elif k == "num":
            out.append(tk["v"])
        elif k == "up":
            out.append(r"\mathrm{%s}" % tk["v"])
        elif k == "op":
            out.append(tk["v"])
        elif k == "sym":
            s = tk["v"]
            if "lo" in tk:
                s += "_{%s}^{%s}" % (render(tk["lo"], ctx, False),
                                     render(tk["hi"], ctx, False))
            out.append(s + " ")
        elif k == "sub":
            out.append("_{%s}" % render(tk["v"], ctx, False, True))
        elif k == "sup":
            body = render(tk["v"], ctx, False, True)
            if out and out[-1].rstrip().endswith("'"):
                # a prime is already a superscript, so x'^2 would be two of
                # them: fold the prime into the one exponent
                out[-1] = out[-1].rstrip()[:-1]
                out.append(r"^{\prime %s}" % body)
            else:
                out.append("^{%s}" % body)
        elif k == "acc":
            inner = render(tk["v"], ctx, False)
            out.append("%s{%s}" % (ACCENT_CMD[tk["a"]], inner))
        elif k == "sqrt":
            out.append(r"\sqrt{%s}" % render(tk["v"], ctx, False))
        elif k == "frac":
            out.append(r"\frac{%s}{%s}" % (render(tk["n"], ctx, False),
                                           render(tk["d"], ctx, False)))
        elif k == "bold":
            out.append(r"\mathbf{%s}" % render(tk["v"], ctx, False))
        elif k == "text":
            word = tk["v"]
            if not in_script and not all(
                    KNOWN_PROSE.match(w) or not w.isalpha()
                    for w in word.split()):
                REPORT.add("prose inside an equation", word, ctx)
            # pad the words so they do not butt against the symbols beside
            # them: "for i = 1 to N", not "fori = 1toN"
            # The padding has to live INSIDE the braces: a space typed in
            # math mode produces no space at all, so \text{as} beside a symbol
            # would set "asΔ".
            if in_script:
                # a label such as the "eff" in V^eff wants no padding at all
                out.append(r"\text{%s}" % esc_text(word))
            else:
                anything_before = any(chunk.strip() for chunk in out)
                lead = " " if anything_before else ""
                out.append(r"\text{%s%s }" % (lead, esc_text(word)))
        elif k == "raw":
            out.append(tk["v"])
        elif k == "open":
            out.append(r"\left" + tk["v"] if tk["v"] != "{" else r"\left\{")
        elif k == "close":
            out.append(r"\right" + tk["v"] if tk["v"] != "}" else r"\right\}")
        elif k in ("space", "pendingspace"):
            out.append(" ")
        elif k == "slash":
            out.append("/")
        else:
            REPORT.add("unhandled token", k, ctx)
    s = "".join(out)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,;.])", r"\1", s)
    if top and not _delims_balanced(s):
        # an expression that opens or closes a bracket outside this run:
        # \left and \right must pair inside one formula, and in the right
        # order, so drop the sizing rather than leave an unmatched one
        s = DELIM_CMD.sub("", s)
    return s.strip()


def to_math(inls, ctx):
    toks = inlines_to_tokens(inls, ctx)
    toks = merge_units(toks)
    toks = fold_sqrt(toks, ctx)
    toks = fold_fractions(toks, ctx)
    toks = fold_integrals(toks, ctx)
    return render(toks, ctx)


# --------------------------------------------------------------------------
# running text
# --------------------------------------------------------------------------

# Emphasis in body text is a variable when it is short and has no spaces.
VARLIKE = re.compile(r"^[A-Za-z\u0370-\u03ff][A-Za-z0-9\u0370-\u03ff]{0,1}$")

# Short English words that are set in italics for emphasis, not as symbols.
NOT_A_VARIABLE = {"a", "an", "as", "at", "be", "by", "do", "go", "he", "if",
                  "in", "is", "it", "me", "my", "no", "of", "on", "or", "so",
                  "to", "up", "us", "we", "any", "all", "not", "one", "two"}


def _strip_marks(s):
    """Drop combining accents so that S-tilde tests as the single letter S."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if c not in COMBINING)


def plain_string(inls):
    """Flatten inlines to their bare text, for testing shapes."""
    out = []
    for n in inls:
        t = n["t"]
        if t == "Str":
            out.append(n["c"])
        elif t in ("Space", "SoftBreak"):
            out.append(" ")
        elif t in ("Emph", "Strong", "Subscript", "Superscript"):
            out.append(plain_string(n["c"]))
        elif t == "Span":
            out.append(plain_string(n["c"][1]))
        elif t == "Quoted":
            q = "\u201c%s\u201d" if n["c"][0]["t"] == "DoubleQuote" \
                else "\u2018%s\u2019"
            out.append(q % plain_string(n["c"][1]))
    return "".join(out)



# --------------------------------------------------------------------------
# recognising a run of mathematics inside running text
# --------------------------------------------------------------------------

# Characters that can sit inside a formula without making it prose.
MATH_CHARS = set("=+\u2212<>\u2264\u2265\u2260\u2248\u2261()[]/,.|\u00b7\u00d7"
                 "\u221e\u2202\u2192\u27f9\u2211\u222b\u22ef\u2026\u2032"
                 "0123456789")


def _is_greek(ch):
    return "\u0370" <= ch <= "\u03ff"


def _mathish_str(txt, nxt=None):
    """True if a bare string can belong to a formula."""
    if not txt.strip():
        return False
    core = txt.strip()
    # C-tilde, U-hat, m-dot and the like: an accented symbol, never prose
    if any(c in COMBINING or decompose_accent(c) for c in core):
        return True
    if all(c in MATH_CHARS or _is_greek(c) or c.isspace() for c in core):
        return True
    # the differential d, before a variable or before its own division sign
    if core == "d" and nxt is not None:
        if nxt["t"] in ("Emph", "Subscript", "Superscript", "Span"):
            return True
        if nxt["t"] == "Str" and nxt["c"].startswith("/"):
            return True
    return False


def _strong_math(n):
    """An inline that can only be mathematics."""
    t = n["t"]
    if t == "Str":
        # a bare accented letter: m-dot, C-tilde, U-hat. The text fonts have no
        # glyph for these, so they must be set as mathematics.
        core = n["c"].strip()
        return (len(_clusters(core)) == 1
                and (any(c in COMBINING for c in core)
                     or decompose_accent(core) is not None))
    if t in ("Subscript", "Superscript"):
        return True
    if t == "Span" and "vec" in n["c"][0][1]:
        return True
    if t == "Emph":
        body = _strip_marks(plain_string(n["c"]))
        if body.lower() in NOT_A_VARIABLE:
            return False
        return bool(VARLIKE.match(body))
    if t == "Strong":
        # a one- or two-letter bold symbol is a vector or a matrix, as in the
        # electric displacement D or the coefficient matrix A. Bold running
        # further than that is emphasis.
        body = plain_string(n["c"])
        if body.lower() in NOT_A_VARIABLE:
            # **on**, **in**, **is**: a short word in bold is emphasis. A
            # single bold letter, such as the vector a, is still a symbol.
            return len(body) == 1
        return len(body) <= 2 and body.isalpha()
    return False


PAIRS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {v: k for k, v in PAIRS.items()}


def _bracket_depth(text):
    """Return (final depth, went negative)."""
    depth, neg = 0, False
    for c in text:
        if c in PAIRS:
            depth += 1
        elif c in CLOSERS:
            depth -= 1
            if depth < 0:
                neg = True
    return depth, neg


def _balance_brackets(inls, start, end):
    """Trim a run so its brackets pair up inside it.

    A closing bracket that has nothing to close belongs to the sentence, so the
    run stops just before it. An opening bracket left unclosed is dropped off
    the end the same way. Returns the new end, or None if nothing is left.
    """
    depth, cut = 0, end
    for k in range(start, end):
        d, neg = _bracket_depth(plain_string([inls[k]]))
        if depth + min(d, 0) < 0 or (neg and depth == 0):
            cut = k
            break
        depth += d
    end = cut
    # an opening bracket that is never closed comes off the end
    while end > start:
        depth, neg = _bracket_depth(plain_string(inls[start:end]))
        if depth == 0 and not neg:
            break
        end -= 1
    # and a space at the boundary belongs to the prose, not the formula
    while end > start and inls[end - 1]["t"] in ("Space", "SoftBreak"):
        end -= 1
    return end if end > start else None


def _math_run(inls, start):
    """Longest run of inlines from `start` that reads as one formula, or None."""
    n = len(inls)
    if start < n and inls[start]["t"] in ("Space", "SoftBreak"):
        return None
    if (start < n and inls[start]["t"] == "Str"
            and all(c in SENTENCE_PUNCT for c in inls[start]["c"])):
        return None
    i = start
    saw_strong = False
    end = start
    while i < n:
        node = inls[i]
        t = node["t"]
        if _strong_math(node):
            saw_strong = True
            i += 1
            end = i
            continue
        if t == "Str" and _mathish_str(node["c"],
                                       inls[i + 1] if i + 1 < n else None):
            i += 1
            end = i
            continue
        if t in ("Space", "SoftBreak"):
            prev = inls[i - 1] if i > start else None
            if (prev is not None and prev["t"] == "Str"
                    and prev["c"].rstrip().endswith((".", ";", ":"))
                    and not prev["c"].rstrip().rstrip(".").isdigit()):
                break
            # a space only stays in the run if mathematics follows it
            j = i + 1
            if j < n and (_strong_math(inls[j])
                          or (inls[j]["t"] == "Str"
                              and _mathish_str(inls[j]["c"],
                                               inls[j + 1] if j + 1 < n
                                               else None))):
                i += 1
                continue
            break
        break
    if not saw_strong or end <= start:
        return None
    # A bracket opened in the prose must not be closed inside the formula, and
    # the other way round: "specified by E (or U when ...)" has parentheses
    # that belong to the sentence, not to E.
    end = _balance_brackets(inls, start, end)
    if end is None:
        return None
    # do not swallow the punctuation that ends the sentence
    while end > start:
        last = inls[end - 1]
        if (last["t"] == "Str"
                and all(c in SENTENCE_PUNCT for c in last["c"])):
            end -= 1
            continue
        break
    return end if end > start else None



# Characters that are fine in mathematics but have no glyph in the text fonts.
TEXT_SYMBOLS = (("\u2212", "--"), ("\u27f9", r"$\implies$"),
                ("\u2192", r"$\to$"), ("\u2248", r"$\approx$"),
                ("\u2261", r"$\equiv$"), ("\u2264", r"$\le$"),
                ("\u2265", r"$\ge$"), ("\u2260", r"$\ne$"),
                ("\u00b7", r"$\cdot$"), ("\u00d7", r"$\times$"),
                ("\u221e", r"$\infty$"), ("\u2202", r"$\partial$"),
                ("\u2211", r"$\sum$"), ("\u222b", r"$\int$"),
                ("\u22ef", r"$\cdots$"))


def _math_as_words(latex):
    """A rough plain-text rendering of a formula, for a PDF bookmark."""
    out = re.sub(r"\\(?:mathrm|text|mathbf|left|right)(?![A-Za-z])", "", latex)
    out = out.replace(r"\to", "\u2192").replace(r"\infty", "\u221e")
    out = out.replace(r"\partial", "\u2202").replace(r"\cdot", "\u00b7")
    out = re.sub(r"\\[A-Za-z]+", "", out)
    out = out.replace("{", "").replace("}", "").replace("^", "").replace("_", "")
    return re.sub(r"\s+", " ", out).strip()


def _text_symbols(s):
    for ch, cmd in TEXT_SYMBOLS:
        s = s.replace(ch, cmd)
    return s


def _mathish_char(c):
    return (c in MATH_CHARS or _is_greek(c) or c in COMBINING
            or decompose_accent(c) is not None)


SENTENCE_PUNCT = set(".,;:")


def _clusters(s):
    """Split a string into base characters with their combining marks."""
    out = []
    for c in s:
        if c in COMBINING and out:
            out[-1] += c
        else:
            out.append(c)
    return out


def split_strings(inls):
    """Break every Str into runs of formula characters and runs of prose.

    Without this a string such as ");" would keep its closing bracket out of
    the formula beside it, because the semicolon makes the whole string look
    like prose.
    """
    out = []
    for n in inls:
        if n["t"] != "Str" or len(n["c"]) < 2:
            out.append(n)
            continue
        piece, flag = "", None
        for cluster in _clusters(n["c"]):
            # a letter and the accent above it are one unit and stay together
            if len(cluster) > 1 or decompose_accent(cluster) is not None:
                f = "math"
            elif cluster in SENTENCE_PUNCT:
                f = "punct"
            elif _mathish_char(cluster):
                f = "math"
            else:
                f = "prose"
            if flag is None or f == flag:
                piece += cluster
                flag = f
                continue
            out.append({"t": "Str", "c": piece})
            piece, flag = cluster, f
        if piece:
            out.append({"t": "Str", "c": piece})
    return out


def inline_text(inls, ctx, pdfstring=False):
    """Convert inlines that live in running text, switching to math where the
    markup says a variable is meant."""
    inls = split_strings(inls)
    out = []
    i = 0
    while i < len(inls):
        n = inls[i]
        t = n["t"]
        end = _math_run(inls, i)
        if end is not None:
            body = to_math(inls[i:end], ctx)
            if pdfstring:
                # a heading also becomes a PDF bookmark, which is plain text
                plain = esc_bookmark(plain_string(inls[i:end]))
                out.append(r"\texorpdfstring{$%s$}{%s}" % (body, plain))
                i = end
                continue
            if len(body) > 60 and ", " in body:
                # A long list of coordinates has to be allowed to wrap. Inline
                # mathematics does not break at a comma on its own, and it
                # never breaks inside a \left...\right pair at all, so the
                # sized delimiters go as well.
                body = DELIM_CMD.sub("", body)
                body = body.replace(", ", r", \allowbreak ")
            out.append("$" + body + "$")
            i = end
            continue
        if t == "Str":
            out.append(_text_symbols(esc_text(n["c"])))
        elif t in ("Space", "SoftBreak"):
            out.append(" ")
        elif t == "Emph":
            out.append(r"\emph{%s}" % inline_text(n["c"], ctx, pdfstring))
        elif t == "Strong":
            out.append(r"\textbf{%s}" % inline_text(n["c"], ctx, pdfstring))
        elif t in ("Subscript", "Superscript"):
            m = to_math([n], ctx)
            out.append(r"\texorpdfstring{$%s$}{%s}"
                       % (m, esc_bookmark(plain_string([n])))
                       if pdfstring else "$" + m + "$")
        elif t == "Span":
            classes = n["c"][0][1]
            if "vec" in classes:
                out.append("$" + to_math([n], ctx) + "$")
            elif "src" in classes:
                out.append(r"\srcnote{%s}" % inline_text(n["c"][1], ctx))
            else:
                out.append(inline_text(n["c"][1], ctx))
        elif t == "Quoted":
            q = n["c"][0]["t"]
            body = inline_text(n["c"][1], ctx)
            out.append("``%s''" % body if q == "DoubleQuote" else "`%s'" % body)
        elif t == "Math":
            body = n["c"][1]
            if n["c"][0]["t"] == "DisplayMath":
                out.append("\\[ %s \\]" % body)
            elif pdfstring:
                # a heading is also a PDF bookmark, which is plain text
                out.append(r"\texorpdfstring{$%s$}{%s}"
                           % (body, esc_bookmark(_math_as_words(body))))
            else:
                out.append("$%s$" % body)
        elif t == "Code":
            out.append(r"\texttt{%s}" % esc_text(n["c"][1]))
        elif t == "Link":
            dest = n["c"][2][0]
            if dest.startswith("#"):
                # [](#fig-c02-04) is a cross-reference, written as an ordinary
                # Markdown link so that one source serves both builds: MyST
                # resolves it to "Figure 4", and here it becomes the same
                # thing through LaTeX's own numbering. The identifier's
                # prefix says what is referred to: fig- a figure, tbl- a
                # table, eq- a numbered equation, which prints as
                # "Equation (3)". A non-breaking space keeps the word and its
                # number on one line.
                target = dest[1:]
                REFS.add(target)
                label = inline_text(n["c"][1], ctx) if n["c"][1] else ""
                kind = target.split("-", 1)[0]
                if kind == "eq":
                    out.append(r"%s~\eqref{%s}" % (label or "Equation",
                                                     target))
                else:
                    out.append(r"%s~\ref{%s}" % (
                        label or REF_WORD.get(kind, "Figure"), target))
            else:
                out.append(r"\href{%s}{%s}" % (dest,
                                                inline_text(n["c"][1], ctx)))
        elif t == "RawInline":
            out.append(n["c"][1])
        elif t == "LineBreak":
            out.append(r"\\" + "\n")
        else:
            REPORT.add("unhandled inline", t, plain_string(inls)[:70])
        i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# blocks
# --------------------------------------------------------------------------

DIV_ENV = {"note": "notebox", "problem": "problembox", "quote": "quotebox",
           "keep": "keepbox"}


def blocks_to_tex(blocks, depth=0):
    out = []
    for b in blocks:
        out.append(block_to_tex(b, depth))
    return "\n\n".join(x for x in out if x is not None and x.strip())


def block_to_tex(b, depth=0):
    t = b["t"]
    if t == "Para" or t == "Plain":
        return inline_text(b["c"], plain_string(b["c"])[:70])
    if t == "Header":
        level, attr, inls = b["c"][0], b["c"][1], b["c"][2]
        ctx = plain_string(inls)[:70]
        body = inline_text(inls, ctx, pdfstring=True)
        if "flag" in attr[1]:
            return r"\flagsection{%s}" % body
        cmd = {1: "section", 2: "section", 3: "subsection",
               4: "subsubsection"}.get(level, "subsubsection")
        # the document's own h1 is the title block, so h2 becomes \section
        return "\\%s{%s}" % (cmd, body)
    if t == "Div":
        classes = b["c"][0][1]
        inner = b["c"][1]
        if "eq" in classes:
            # Runs of paragraphs become display equations inside one eqblock.
            # Anything else, a numbered list of equations for instance, is
            # emitted outside it: a list inside the eqblock group leaves the
            # tagging code's paragraph hooks unbalanced and aborts the run.
            #
            # An alt= attribute on the div gives the equation a spoken form of
            # its own, for notation that is right on the page and unreadable
            # aloud: a matrix, a cancelled term, an integral whose limits are
            # stacked. See eq_alt() and CONVENTIONS.md.
            alt = dict(b["c"][0][2]).get("alt")
            out, run = [], []

            def flush():
                if run:
                    out.append("\\begin{eqblock}\n" + "\n".join(run)
                               + "\n\\end{eqblock}")
                    run.clear()

            for sub in inner:
                if sub["t"] in ("Para", "Plain"):
                    ctx = plain_string(sub["c"])[:90]
                    inls, eqlabel = equation_label(sub["c"])
                    if eqlabel:
                        # a numbered equation that the text can refer to
                        LABELS.add(eqlabel)
                        body = ("\\begin{equation}\n%s\n\\label{%s}\n"
                                "\\end{equation}"
                                % (to_math(inls, ctx), eqlabel))
                    else:
                        body = r"\[ %s \]" % to_math(inls, ctx)
                    if alt:
                        body = "\\eqalt{%s}{%%\n%s}" % (esc_text(alt), body)
                    run.append(body)
                else:
                    flush()
                    out.append(block_to_tex(sub, depth + 1))
            if alt and sum(1 for s in inner
                           if s["t"] in ("Para", "Plain")) > 1:
                REPORT.add("alt= on a div holding more than one equation",
                           alt[:60], "")
            flush()
            return "\n\n".join(out)
        if "flush" in classes:
            # Set every figure still waiting before going on. An empty div is
            # the usual way to write it; anything inside follows the barrier.
            body = blocks_to_tex(inner, depth)
            return "\\FloatBarrier" + ("\n\n" + body if body.strip() else "")
        for cls, env in DIV_ENV.items():
            if cls in classes:
                return ("\\begin{%s}\n" % env + blocks_to_tex(inner, depth + 1)
                        + "\n\\end{%s}" % env)
        return blocks_to_tex(inner, depth)
    if t == "BulletList":
        items = "\n".join(list_item(it, depth) for it in b["c"])
        return "\\begin{itemize}\n%s\n\\end{itemize}" % items
    if t == "OrderedList":
        items = "\n".join(list_item(it, depth) for it in b["c"][1])
        return "\\begin{enumerate}\n%s\n\\end{enumerate}" % items
    if t == "BlockQuote":
        return ("\\begin{quotebox}\n" + blocks_to_tex(b["c"], depth + 1)
                + "\n\\end{quotebox}")
    if t == "Figure":
        return figure_to_tex(b)
    if t == "Table":
        return table_to_tex(b)
    if t == "CodeBlock":
        return "\\begin{verbatim}\n%s\n\\end{verbatim}" % b["c"][1]
    if t == "HorizontalRule":
        return r"\par\noindent\rule{\linewidth}{0.4pt}"
    if t == "RawBlock":
        return b["c"][1] if b["c"][0] == "latex" else ""
    REPORT.add("unhandled block", t, "")
    return ""


# What a cross-reference prints, by the prefix of the identifier it points
# at. An equation is handled apart, since its number goes in parentheses.
REF_WORD = {"fig": "Figure", "tbl": "Table"}

EQ_LABEL = re.compile(r"^\{#(eq-[\w-]+)\}$")


def equation_label(inls):
    """Split a trailing {#eq-c10-03} off a display equation's paragraph.

    Pandoc leaves the identifier as ordinary text after the mathematics, so
    it is taken off here and returned beside what is left.
    """
    items = list(inls)
    while items and items[-1]["t"] in ("Space", "SoftBreak"):
        items.pop()
    if items and items[-1]["t"] == "Str":
        m = EQ_LABEL.match(items[-1]["c"])
        if m:
            items.pop()
            while items and items[-1]["t"] in ("Space", "SoftBreak"):
                items.pop()
            return items, m.group(1)
    return inls, None


FIGNUM = re.compile(r"^\s*(?:Figure|Table)\s+\d+\s*[.:]\s*", re.I)


def strip_figure_number(inls):
    """Drop the "Figure N." the transcription wrote into the caption text.

    LaTeX numbers the float itself, and the figures are converted in the order
    they were written, so the two numbers agree. Leaving both in would print
    "Figure 1: Figure 1. ...".
    """
    out = list(inls)
    for k, n in enumerate(out):
        if n["t"] != "Strong":
            continue
        inner = list(n["c"])
        m = FIGNUM.match(plain_string(inner))
        if not m:
            break
        drop, trimmed, used = m.end(), [], 0
        for node in inner:
            if used >= drop:
                trimmed.append(node)
                continue
            piece = plain_string([node])
            if used + len(piece) <= drop:
                used += len(piece)
                continue
            keep = piece[drop - used:]
            used = drop
            if node["t"] == "Str" and keep:
                trimmed.append({"t": "Str", "c": keep})
            elif node["t"] not in ("Str", "Space"):
                trimmed.append(node)
        out[k] = {"t": "Strong", "c": trimmed}
        break
    return out


def list_item(blocks, depth):
    """One \\item, with a guard for an item that opens with display maths.

    A list item whose body starts with \\[ leaves the tagging code's
    paragraph hooks unbalanced and aborts the run, because the item never
    enters horizontal mode. \\leavevmode makes it do so.
    """
    body = blocks_to_tex(blocks, depth + 1)
    if body.lstrip().startswith("\\["):
        return "\\item \\leavevmode\n" + body
    return "\\item " + body


# The folder of the Markdown file being converted, so that a figure written
# relative to it, "../figures/x.svg" from src/ or 2026/, can be expressed
# relative to the project root, which is where lualatex is run from.
DOC_DIR = HERE


def figure_path(src):
    """Turn a figure reference in the Markdown into one the LaTeX can use."""
    resolved = (DOC_DIR / src).resolve()
    try:
        rel = resolved.relative_to(HERE)
    except ValueError:
        rel = Path(src)
    return str(rel.with_suffix(".pdf")).replace("\\", "/")


def figure_to_tex(b):
    caption_blocks = b["c"][1][1]
    body = b["c"][2]
    img = None
    for blk in body:
        if blk["t"] in ("Plain", "Para"):
            for n in blk["c"]:
                if n["t"] == "Image":
                    img = n
    if img is None:
        REPORT.add("figure without an image", "", "")
        return ""
    attr, alt_inls, target = img["c"][0], img["c"][1], img["c"][2]
    src = target[0]
    alt = attr[2]
    # Pandoc hangs the {#fig-c02-04} on the Figure block rather than on the
    # image inside it, so look there first and fall back to the image.
    label = b["c"][0][0] or attr[0]
    if label:
        LABELS.add(label)
    alt_text = ""
    for k, v in alt:
        if k == "alt":
            alt_text = v
    if not alt_text:
        alt_text = plain_string(alt_inls)
    width = None
    for k, v in alt:
        if k == "width":
            width = v
    ctx = plain_string(caption_blocks[0]["c"])[:70] if caption_blocks else src
    caption = (inline_text(strip_figure_number(caption_blocks[0]["c"]), ctx)
               if caption_blocks else "")
    # the figure keeps the folder it is written with, so that the LaTeX
    # compiles from the project root and the Markdown resolves on the web
    pdf = figure_path(src)
    # the .svg width is in pixels at 96 dpi; cap it at the text block
    if width:
        try:
            inches = float(re.sub(r"[^0-9.]", "", width)) / 96.0
            size = "width=%.2fin" % min(inches, 5.6)
        except ValueError:
            size = r"width=0.85\linewidth"
    else:
        size = r"width=0.85\linewidth"
    # \label has to follow \caption: the figure counter is stepped by the
    # caption, and a label before it would record the number of whatever was
    # numbered last.
    return (
        "\\begin{figure}[!ht]\n\\centering\n"
        "\\includegraphics[%s,alt={%s}]{%s}\n"
        "\\figcaption{%s}%s\n\\end{figure}"
        % (size, esc_text(alt_text), pdf, caption,
           ("\n\\label{%s}" % label) if label else ""))


def table_to_tex(b):
    """Emit a longtable.

    The tagging code takes a table's header rows from longtable's own
    \\endhead marker. A plain tabular has no way to say which row is the
    header, so its cells are all tagged /TD and the file fails the check that
    header cells must be /TH. longtable also lets a long table break across
    pages, which several of these do.

    The table carries no rules. Both \\hline and the booktabs rules abort the
    run under the tagging code in TeX Live 2023, so the header is distinguished
    by bold sans type and by the space around it instead. See BUILD.md.
    """
    # pandoc Table: [attr, caption, colspecs, head, bodies, foot]
    _, caption, colspecs, head, bodies, foot = b["c"]
    aligns = []
    for spec in colspecs:
        a = spec[0]["t"]
        aligns.append({"AlignRight": "r", "AlignCenter": "c"}.get(a, "l"))
    # no vertical rules: \hline and the booktabs rules both break the
    # tagging code, so the table is set open, with the header in bold sans
    colfmt = "@{}" + " ".join(a + "@{\\hspace{1.6em}}" for a in aligns[:-1]) \
        + aligns[-1] + "@{}"

    def row_cells(row):
        return [blocks_to_tex(cell[4]).replace("\n", " ").strip()
                for cell in row[1]]

    out = ["\\begin{longtable}{%s}" % colfmt]
    for row in head[1]:
        out.append(" & ".join(r"\theadcell{%s}" % c for c in row_cells(row))
                   + r" \\")
    out.append(r"\endhead")
    # A table's \label goes in its first body cell: longtable has stepped
    # the table counter and set the link target by then, and a body row,
    # unlike the header, is set only once.
    label = b["c"][0][0]
    pending = (r"\label{%s}" % label) if label else ""
    for body in bodies:
        for row in body[3]:
            cells = row_cells(row)
            if pending and cells:
                cells[0] = pending + cells[0]
                pending = ""
            out.append(" & ".join(cells) + r" \\")
    out.append("\\end{longtable}")
    cap_blocks = caption[1]
    # "Table: caption {#tbl-c10-01}" under the table gives it a caption and
    # an identifier, which pandoc hangs on the table itself. The caption is
    # set as a paragraph just above the table rather than as longtable's own
    # \caption, which the tagging code would make a header cell: see
    # \tabcaption in the class.
    if label:
        LABELS.add(label)
    if cap_blocks:
        ctx = plain_string(cap_blocks[0]["c"])[:70]
        out.insert(0, r"\tabcaption{%s}" % inline_text(
            strip_figure_number(cap_blocks[0]["c"]), ctx))
    elif label:
        REPORT.add("table identifier without a caption", label, "")
    return "\n".join(out)


# --------------------------------------------------------------------------
# document
# --------------------------------------------------------------------------


def _site(key, default):
    """A setting from the site block of contents.yaml, or the default."""
    try:
        import contents
        return contents.site(key) or default
    except Exception:                 # no contents.yaml: a lone conversion
        return default


def _latex_class():
    """The document class named in contents.yaml, "notes" if none is."""
    return _site("latex_class", "notes")


PREAMBLE = r"""%% Generated from {src} by md2tex.py on {date}.
%% Generated file: edit the Markdown, not this. Every build overwrites it.
%%
%% pdfversion is stated rather than left to the default. From LaTeX
%% 2025-06-01 a document with tagging switched on defaults to PDF 2.0, while
%% pdfstandard=ua-1 wants PDF 1.7, and tagpdf aborts the run when the version
%% changes under it: "The PDF version has changed after the loading of tagpdf
%% from 2.0 to 1.7." Saying 1.7 here settles it before tagpdf loads.
\DocumentMetadata{{
  lang        = {lang},
  pdfversion  = 1.7,
  pdfstandard = ua-1,
  testphase   = {{phase-III,math,table,firstaid}},
}}
\documentclass{{{latex_class}}}

\docheading{{{docheading}}}
\subtitleline{{{subtitle}}}
\runningfoot{{{runningfoot}}}
\hypersetup{{pdftitle={{{pdftitle}}},pdfsubject={{{description}}}}}

\begin{{document}}
\maketitlepage

"""


def meta_string(meta, key, default=""):
    v = meta.get(key)
    if v is None:
        return default
    if v["t"] == "MetaString":
        return v["c"]
    if v["t"] == "MetaInlines":
        return plain_string(v["c"])
    if v["t"] == "MetaBlocks":
        return plain_string(v["c"][0]["c"]) if v["c"] else default
    return default


def convert(path):
    global DOC_DIR
    src = Path(path).resolve()
    DOC_DIR = src.parent
    text = src.read_text(encoding="utf-8")
    proc = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "json"],
        input=text, capture_output=True, text=True)
    if proc.returncode:
        sys.exit("pandoc failed on %s:\n%s" % (src, proc.stderr))
    doc = json.loads(proc.stdout)
    meta = doc["meta"]

    title = meta_string(meta, "title")
    docheading = meta_string(meta, "docheading") or title.split("\u2014")[0].strip()
    short = _site("short", "")
    runningfoot = (meta_string(meta, "runningfoot")
                   or (short + " \u2014 " + docheading if short else docheading))
    subtitle = meta_string(meta, "subtitle")
    description = meta_string(meta, "description")
    lang = meta_string(meta, "lang", "en")

    global REPORT
    REPORT = Report()
    LABELS.clear()
    REFS.clear()

    body = blocks_to_tex(doc["blocks"])

    # A reference with nothing behind it compiles happily and prints
    # "Figure ??", so it is caught here rather than left in the PDF.
    for target in sorted(REFS - LABELS):
        REPORT.add("cross-reference with no figure, table or equation "
                   "behind it", target, "")

    from datetime import date
    head = PREAMBLE.format(
        latex_class=_latex_class(),
        src=src.name, date=date.today().isoformat(), lang=lang,
        docheading=esc_text(docheading), subtitle=esc_text(subtitle),
        runningfoot=esc_text(runningfoot), pdftitle=esc_text(title),
        description=esc_text(description))
    out = head + body + "\n\n\\end{document}\n"
    # The LaTeX goes beside the Markdown, in src/ for a lecture and in its
    # year folder for a homework set, so that a document's source,
    # its generated LaTeX and its PDF always sit together.
    dest = src.with_suffix(".tex")
    dest.write_text(out, encoding="utf-8")
    try:
        shown = dest.relative_to(HERE)
    except ValueError:
        shown = dest
    print("wrote", shown)
    REPORT.dump(src.stem)
    return dest


def documents():
    """Every document in contents.yaml, held back from the website or not.

    Holding a document back is a publishing decision, not a build one: the
    point of holding it back is to have a PDF to proofread from, so this
    covers the lot.
    """
    import contents
    return [d.file for d in contents.documents()]


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--all":
        targets = documents()
    else:
        targets = [locate(a) for a in args]
    for t in targets:
        convert(t)


def locate(name):
    """A path as given if it exists, else the document contents.yaml names."""
    p = Path(name)
    if p.suffix == ".md" and p.exists():
        return p
    import contents
    doc = contents.find(name)
    if doc is None:
        sys.exit(f"no such document: {name}")
    return doc.file


if __name__ == "__main__":
    main()
