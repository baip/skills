#!/usr/bin/env python3
"""
Build the notes into a website with Sphinx.

Usage:
    python3 mkweb.py            # build into site/
    python3 mkweb.py --serve    # build, then serve it on http://localhost:8000
    python3 mkweb.py --serve 8080   # the same, on another port

The Markdown sources are shared with the PDF build and are not edited here.
Sphinx reads them through MyST-Parser, which is close to pandoc's Markdown but
not identical, so this script stages a copy into web/ and makes three small
changes on the way:

  1. a pandoc fenced div, "::: note", becomes a MyST directive, ":::{note}";
  2. an image written as a paragraph becomes a MyST figure with its alt text,
     because MyST does not carry an alt attribute through the shorthand form;
  3. the YAML metadata that the PDF build uses is rewritten as the page title
     and a short subtitle, since Sphinx takes a page's title from its first
     heading.

Mathematics needs no conversion at all. It is already $...$ and $$...$$, and
MyST's dollarmath extension hands it to MathJax, which is what makes the
equations readable by a screen reader on the web: MathJax emits MathML and
speech text, so a reader can have a formula spoken and can walk through it term
by term. That is a better outcome for mathematics than tagged PDF manages, and
it is the reason the website is worth having beside the PDFs rather than
instead of them.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

import contents

HERE = Path(__file__).resolve().parent
FIGDIR = HERE / "figures"      # the SVG sources
WEB = HERE / "web"             # staging: a MyST copy of the Markdown
SITE = HERE / "site"           # the built website

# What the website publishes, and in what order, comes from contents.yaml.
# A document with checked: false is not staged, so no page is built for it and
# nothing links to it. A lecture is staged at the top of web/,
# without its src/ folder, so its page keeps the address it has always had
# (03_2nd_Law.html). Course-year material keeps its folder (2026/…). Either
# way the figure links are rewritten to point at the staged figures/.

# How each fenced div maps onto a MyST directive.
DIV_MAP = {
    # A div whose title is None takes its title from the first heading inside
    # it, and that heading is then removed so it does not appear twice.
    "note": ("admonition", None),
    "problem": ("admonition", "Problem"),
    "quote": ("epigraph", None),
    "keep": (None, None),      # a page-break hint: meaningless on the web
    "flush": (None, None),     # a float barrier: the web has no floats
    "eq": (None, None),        # display maths needs no wrapper here
}

FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
# The caption sits on one line, because the Markdown is written with
# --wrap=none. Matching without DOTALL keeps one figure from swallowing the
# next, and the caption may itself contain brackets, so ] is only a terminator
# when a ( follows it. A cross-reference in the caption, [](#fig-c07-03), has
# its ]( too, and is taken whole, or the line would not match at all and the
# figure, with every reference to it, would drop out of the page.
IMG = re.compile(r'^!\[((?:[^\]\n]|\]\(#[\w-]+\)|\](?!\())*)\]\(([^)\s]+)\)'
                 r'\{([^}]*)\}\s*$', re.M)
ATTR = re.compile(r'(\w+)="([^"]*)"')


def read_front(text):
    m = FRONT.match(text)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]


FENCE = re.compile(r"^(:{3,})\s*(.*?)\s*$")
KV = re.compile(r'([\w-]+)="([^"]*)"')


def parse_spec(spec):
    """Read a fence's spec: a bare class name, or pandoc's {.cls key="v"}."""
    if not spec:
        return None, {}
    if spec.startswith("{"):
        body = spec.strip("{}")
        cls = re.findall(r"\.([\w-]+)", body)
        return (cls[0] if cls else None), dict(KV.findall(body))
    return spec.lstrip("."), {}


def convert_divs(text, alts):
    """Rewrite pandoc fenced divs as MyST directives.

    An equation div carrying alt= becomes a plain container with a numbered
    class, and its alt text is appended to `alts`. The build then puts the
    two together in the HTML, because neither MyST nor MathJax has a way to
    label a formula from the Markdown.
    """
    lines = text.split("\n")
    out, stack = [], []
    for idx, line in enumerate(lines):
        m = FENCE.match(line)
        if m and m.group(2):
            name, kv = parse_spec(m.group(2))
            if name == "eq" and kv.get("alt"):
                stack.append("container")
                out.append(":::{container} eqalt-%d" % len(alts))
                alts.append(kv["alt"])
                continue
            directive, title = DIV_MAP.get(name, ("admonition", name))
            if directive is None:
                stack.append(None)
                continue
            if title is None:
                # borrow the first heading inside the block as the title
                for peek in lines[idx + 1:idx + 4]:
                    hm = re.match(r"^#{2,6}\s+(.*)$", peek)
                    if hm:
                        title = hm.group(1).strip()
                        break
            stack.append(directive)
            out.append(":::{%s}%s" % (directive, (" " + title) if title else ""))
            continue
        if stack and stack[-1] is not None and re.match(r"^#{2,6}\s+", line) \
                and not any(l.strip() for l in out[len(out) - 1:len(out)]
                            if l.strip() and not l.startswith(":::")):
            # the heading that became the block's title
            continue
        if m and not m.group(2):
            if stack:
                opened = stack.pop()
                if opened is None:
                    continue
            out.append(":::")
            continue
        out.append(line)
    return "\n".join(out)


HEADING_ATTR = re.compile(r"^(#{1,6}\s+.*?)\s*\{([^}]*)\}\s*$", re.M)


def convert_headings(text):
    """Move a heading's attributes onto their own line above it.

    Pandoc writes them after the heading text, as in

        ## Zeroth Law of Thermodynamics {#zeroth-law .flag}

    MyST reads the braces as literal text there and prints them. Its
    attrs_block extension takes the same attributes from the line before the
    block instead, so the pair is simply swapped round.
    """
    def repl(m):
        return "{%s}\n%s" % (m.group(2).strip(), m.group(1).rstrip())
    return HEADING_ATTR.sub(repl, text)


FIG_ID = re.compile(r"#([\w-]+)")


def convert_images(text, labels):
    """Turn each image paragraph into a MyST figure carrying its alt text.

    The {#fig-c02-04} of the Markdown becomes the figure's :name:, which is
    what makes numfig number it and what a [](#fig-c02-04) link resolves
    against. Each one seen is added to `labels`, so a reference that points
    at nothing can be reported.
    """
    def repl(m):
        caption, src, attrs = m.group(1), m.group(2), m.group(3)
        kv = dict(ATTR.findall(attrs))
        alt = kv.get("alt", "")
        width = kv.get("width")
        ident = FIG_ID.search(attrs)
        lines = [":::{figure} %s" % src]
        if ident:
            lines.append(":name: %s" % ident.group(1))
            labels.add(ident.group(1))
        lines.append(":alt: %s" % alt.replace("\n", " "))
        if width:
            lines.append(":width: %spx" % width)
        lines.append("")
        lines.append(caption.replace("\n", " "))
        lines.append(":::")
        return "\n".join(lines)
    return IMG.sub(repl, text)


# A dashed rule with gaps opens a pandoc simple or multiline table; a "+---+"
# corner opens a grid table. MyST reads none of the three.
NOT_MYST_TABLE = re.compile(r"^\s*(?:-{3,}(?:\s+-{3,})+|\+-{3,}\+)\s*$", re.M)


def check_tables(stem, body):
    """Warn about a table MyST will print as running text.

    Pandoc has four table syntaxes and MyST reads only the pipe one. The
    others are not rejected, they are parsed as paragraphs, so the cells come
    out run together in a block of prose and the page still builds and still
    passes every check. That is how the generalized-work table sat broken on
    the website without anything saying so.
    """
    n = len(NOT_MYST_TABLE.findall(body))
    if n:
        print("%s: %d table(s) are not pipe tables and will render as "
              "paragraphs" % (stem, n), file=sys.stderr)
    return n


TABLE_CAPTION = re.compile(r"^Table:\s+(.*?)\s*(?:\{#(tbl-[\w-]+)\})?\s*$")


def convert_tables(text, labels):
    """Give a captioned pipe table the MyST table directive.

    The Markdown writes a caption as pandoc does, a paragraph beginning
    "Table:" just after the table, and ends it with the table's identifier:
    "Table: Data for chloroform … {#tbl-c10-02}". MyST reads that as an
    ordinary paragraph, so the table and its caption are wrapped together in
    a table directive here. The caption becomes the directive's title and
    the identifier its :name:, which is what numfig numbers and what a
    [](#tbl-c10-02) link resolves against. A table without a caption is left
    alone and is not numbered.
    """
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        if not lines[i].startswith("|") or (out and out[-1].startswith("|")):
            out.append(lines[i])
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].startswith("|"):
            j += 1
        table = lines[i:j]
        k = j
        while k < len(lines) and not lines[k].strip():
            k += 1
        m = TABLE_CAPTION.match(lines[k]) if k < len(lines) else None
        if not m:
            out += table
            i = j
            continue
        caption, ident = m.group(1), m.group(2)
        out.append(":::{table} %s" % caption)
        if ident:
            out.append(":name: %s" % ident)
            labels.add(ident)
        out += [""] + table + [":::"]
        i = k + 1
    return "\n".join(out)


EQ_LABEL = re.compile(r"^(.*\$\$)\s*\{#(eq-[\w-]+)\}\s*$")


def convert_equation_labels(text, labels):
    """Number a display equation that carries an identifier.

    "$$ … $$ {#eq-c10-03}" in the Markdown is the pandoc-style way of
    writing it, and md2tex.py makes it a numbered equation. MyST's own form
    is "$$ … $$ (eq-c10-03)", which numbers it on the page and lets the eq
    role, which [](#eq-c10-03) is rewritten into, refer to it.
    """
    out = []
    for line in text.split("\n"):
        m = EQ_LABEL.match(line)
        if m:
            labels.add(m.group(2))
            line = "%s (%s)" % (m.group(1), m.group(2))
        out.append(line)
    return "\n".join(out)


MD_LINK = re.compile(r"\[[^\]]*\]\(#([\w-]+)\)")


NUMREF = re.compile(r"\[\]\(#([\w-]+)\)")


def convert_refs(text):
    """Turn an empty-text link to a figure, table or equation into a numbered
    reference.

    [](#fig-c02-04) is the plain-Markdown form the sources use, and MyST does
    resolve it, but it resolves it to the figure's whole caption, which here
    is a paragraph of description. The numref role is what gives "Figure 4"
    and "Table 2", so the link is rewritten into it on the way in. An
    equation takes the eq role instead, which math_eqref_format in conf.py
    prints as "Equation (3)". A link written with its own text,
    [the two-step figure](#fig-c02-04), is left alone.
    """
    def repl(m):
        target = m.group(1)
        role = "eq" if target.startswith("eq-") else "numref"
        return "{%s}`%s`" % (role, target)
    return NUMREF.sub(repl, text)


def check_refs(stem, body, labels):
    """Report a cross-reference with no figure, table or equation behind it.

    Sphinx warns about an unresolved target but still builds the page, and
    the warning is easy to miss among the others, so the count is returned
    and the build ends non-zero.
    """
    missing = sorted({m.group(1) for m in MD_LINK.finditer(body)} - labels)
    for target in missing:
        print("%s: cross-reference to #%s, which is not a figure, table or "
              "equation here" % (stem, target), file=sys.stderr)
    return len(missing)


FIG_LINK = re.compile(r"\]\(([^)\s]+\.svg)\)")


def rebase_figures(body, src_dir, dest_dir):
    """Rewrite each figure link for the staged copy's own folder.

    The Markdown writes a figure relative to itself, "../figures/x.svg" from
    src/ or 2026/. The staged copy of a lecture sits one folder higher than
    its source, so the same link has to become "figures/x.svg" there.
    """
    def repl(m):
        target = (src_dir / m.group(1)).resolve()
        try:
            staged = WEB / target.relative_to(HERE)
        except ValueError:
            return m.group(0)
        rel = os.path.relpath(staged, dest_dir).replace("\\", "/")
        return "](%s)" % rel
    return FIG_LINK.sub(repl, body)


DISPLAY_ANY = re.compile(r"^\$\$(.*)\$\$\s*$", re.S)
DISPLAY_END = re.compile(r"\$\$\s*(?:\(eq-[\w-]+\))?\s*$")


def unsplit_tagged(body):
    r"""Keep Sphinx from wrapping a tagged, multi-line equation in split.

    Sphinx hands every display equation to MathJax inside
    \begin{split}...\end{split} once it contains a line break (\\), which
    an aligned block or a \substack under-brace does. MathJax refuses \tag
    inside split, so such an equation printed an error instead of its
    number. Those few equations become a math directive with :nowrap:,
    wrapped in equation* by hand, where \tag is allowed. Everything else
    is left to MyST.
    """
    out, lines, i = [], body.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("$$"):
            out.append(line)
            i += 1
            continue
        # a display equation, on one line or spread over several
        j = i
        while not (DISPLAY_END.search(lines[j])
                   and (j > i or len(lines[j].strip()) > 2)):
            j += 1
            if j == len(lines):
                j = i
                break
        text = "\n".join(lines[i:j + 1])
        m = DISPLAY_ANY.match(text)
        if m and "\\tag{" in m.group(1) and "\\\\" in m.group(1):
            out += ["```{math}", ":nowrap:", "",
                    "\\begin{equation*}%s\\end{equation*}" % m.group(1),
                    "```"]
        else:
            out += lines[i:j + 1]
        i = j + 1
    return "\n".join(out)


def stage(eq_alts):
    WEB.mkdir(exist_ok=True)
    for old in list(WEB.glob("*.md")) + [p for p in WEB.glob("*/*.md")
                                         if p.parent.name != "_static"]:
        old.unlink()
    # Drop any figure the project no longer has. Without this the staging
    # directory keeps a renamed figure's old file for ever, and Sphinx copies
    # it into the built site, where it is invisible until someone wonders why
    # the archive has more images than the documents reference.
    webfigs = WEB / "figures"
    webfigs.mkdir(exist_ok=True)
    current = {p.name for p in FIGDIR.glob("*.svg")}
    stale = [p for p in webfigs.glob("*.svg") if p.name not in current]
    for p in stale:
        p.unlink()
    if stale:
        print("removed %d stale figure(s) from the staging directory"
              % len(stale))
    titles, bad_tables, bad_refs = {}, 0, 0
    published = contents.documents(published_only=True)
    held = [d for d in contents.documents() if not d.checked]
    for doc in published:
        stem, src = doc.web, doc.file
        if not src.exists():
            print("missing:", doc.path, file=sys.stderr)
            continue
        meta, body = read_front(src.read_text(encoding="utf-8"))
        title = meta.get("docheading") or \
            str(meta.get("title", stem)).split("—")[0].strip()
        titles[stem] = title
        bad_tables += check_tables(stem, body)
        alts, labels = [], set()
        body = rebase_figures(body, src.parent, (WEB / stem).parent)
        body = convert_equation_labels(body, labels)
        body = unsplit_tagged(body)
        body = convert_divs(body, alts)
        body = convert_headings(body)
        body = convert_images(body, labels)
        body = convert_tables(body, labels)
        bad_refs += check_refs(stem, body, labels)
        body = convert_refs(body)
        if alts:
            eq_alts[stem] = alts
        head = ["# " + title, ""]
        if meta.get("subtitle"):
            head += ["*%s*" % meta["subtitle"], ""]
        dest = WEB / (stem + ".md")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(head) + body, encoding="utf-8")
    # Every figure goes into web/figures/, which is where rebase_figures()
    # pointed each staged document's links.
    for svg in FIGDIR.glob("*.svg"):
        shutil.copy(svg, WEB / "figures" / svg.name)
    stage_mathjax()
    if bad_refs:
        globals()["BAD_REFS"] = bad_refs
    if bad_tables:
        print("\n%d table(s) will not render: rewrite them as pipe tables"
              % bad_tables, file=sys.stderr)
        globals()["BAD_TABLES"] = bad_tables
    if held:
        print("held back from the website (checked: false in contents.yaml): "
              "%d of %d" % (len(held), len(held) + len(published)))
        for d in held:
            print("    " + d.path)
    return titles


def find_mathjax():
    """Locate a MathJax 3 installation, local to the project or global.

    A global install is the common case on a machine where node packages are
    managed by Homebrew, so the project directory is checked first and then
    npm's own global root, whatever prefix that machine uses. NOTES_MATHJAX
    overrides both and should point at the directory holding es5/.
    """
    cands = []
    override = os.environ.get("NOTES_MATHJAX")
    if override:
        cands.append(Path(override))
    cands.append(HERE / "node_modules" / "mathjax")
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True,
                              text=True, timeout=30)
        if root.returncode == 0 and root.stdout.strip():
            cands.append(Path(root.stdout.strip()) / "mathjax")
    except (OSError, subprocess.SubprocessError):
        pass
    for c in cands:
        if (c / "es5" / "tex-mml-chtml.js").exists():
            return c / "es5"
    return None


def stage_mathjax():
    """Copy the MathJax runtime into the site's static files."""
    dest = WEB / "_static" / "mathjax"
    # Sphinx warns about a missing html_static_path whether or not MathJax is
    # found, so the directory exists either way.
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = find_mathjax()
    if src is None:
        print("MathJax 3 not found: install it with  npm install mathjax@3\n"
              "  (a global  npm install -g mathjax@3  is found too, and\n"
              "   NOTES_MATHJAX=/path/to/mathjax overrides the search)",
              file=sys.stderr)
        return
    if src.parent != HERE / "node_modules" / "mathjax":
        print("MathJax:", src.parent)
    # A staged copy is reused, but only if it is complete. The check is not
    # academic: when input/ was added to the list below, every existing copy
    # went on without it, MathJax could not autoload \\cancel, and it stopped
    # typesetting that page altogether rather than skipping the one macro.
    if dest.exists():
        if (dest / "input" / "tex" / "extensions").exists():
            return
        shutil.rmtree(dest)
        print("MathJax copy was incomplete: staging it again")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # only the pieces the page actually loads
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(
        "*.map", "a11y", "sre", "input", "adaptors", "ui",
        "tex-*", "mml-*", "output"))
    shutil.copy(src / "tex-mml-chtml.js", dest / "tex-mml-chtml.js")
    shutil.copytree(src / "output", dest / "output", dirs_exist_ok=True)
    shutil.copytree(src / "a11y", dest / "a11y", dirs_exist_ok=True)
    shutil.copytree(src / "sre", dest / "sre", dirs_exist_ok=True)
    # input/tex/extensions holds the packages MathJax fetches on demand. The
    # bundle knows the names but not the code, so without this directory a
    # \\cancel silently renders as nothing at all.
    shutil.copytree(src / "input", dest / "input", dirs_exist_ok=True)


EQ_DIV = re.compile(
    r'(<div class="eqalt-(\d+) docutils container">)(.*?)(</div>)', re.S)
EQNO = re.compile(r'<span class="eqno">(\(\d+\))')
MATH_DIV = re.compile(r'<div class="math notranslate nohighlight"((?: id="[^"]*")?)>')


def label_equations(eq_alts):
    """Give each flagged equation a spoken label in the built HTML.

    MathJax writes a MathML copy of every formula, which a screen reader can
    read term by term, and for most of these notes that is the best available
    answer. It is not the answer for a matrix, a cancelled term or an integral
    whose limits are stacked, where the reading is correct but unfollowable.
    Those equations carry alt= in the Markdown, and here the container the
    staging step wrapped them in becomes

        <div role="math" aria-label="the sentence"> … aria-hidden math … </div>

    so the reader hears the sentence and not the symbols. The rendered
    mathematics is untouched and still on the page for everyone else.

    This is done to the built HTML rather than in the Markdown because Sphinx
    marks its whole body mathjax_ignore and typesets only its own math nodes,
    so mathematics written inside raw HTML is never rendered at all.
    """
    total = 0
    for stem, alts in sorted(eq_alts.items()):
        page = SITE / (stem + ".html")
        if not page.exists():
            print("no built page for", stem, file=sys.stderr)
            continue
        html = page.read_text(encoding="utf-8")

        def repl(m):
            nonlocal total
            idx = int(m.group(2))
            if idx >= len(alts):
                return m.group(0)
            label = (alts[idx].replace("&", "&amp;").replace('"', "&quot;")
                     .replace("<", "&lt;").replace(">", "&gt;"))
            # The sentence replaces the formula for a screen reader, number
            # and all, so a numbered equation's number is added to it.
            num = EQNO.search(m.group(3))
            if num:
                label += " Equation %s." % num.group(1)
            inner = MATH_DIV.sub(
                r'<div aria-hidden="true" class="math notranslate nohighlight"\1>',
                m.group(3))
            total += 1
            return ('<div class="eqalt docutils container" role="math" '
                    'aria-label="%s">%s%s' % (label, inner, m.group(4)))

        new = EQ_DIV.sub(repl, html)
        if new != html:
            page.write_text(new, encoding="utf-8")
    if total:
        print("labelled %d equation(s) with a spoken alternative" % total)
    missing = sum(len(a) for a in eq_alts.values()) - total
    if missing:
        print("%d equation label(s) could not be placed" % missing,
              file=sys.stderr)


FIGURE_TAG = re.compile(r'<figure[^>]*\bid="([^"]+)"[^>]*>(.*?)</figure>', re.S)
TABLE_TAG = re.compile(r'<table[^>]*\bid="([^"]+)"[^>]*>(.*?)</table>', re.S)
CAPTION_NUMBER = re.compile(r'(<span class="caption-number">)([^<]*)(</span>)')
REF_LINK = re.compile(
    r'(<a class="reference internal" href="#((?:fig|tbl)-[\w-]+)"[^>]*>)(.*?)(</a>)',
    re.S)
NUMBERED_WORD = re.compile(r"\b(Figure|Table)\s+\d+\b")


def renumber_figures(stems):
    """Number each page's figures, and its tables, from 1, as its PDF does.

    Sphinx numbers figures continuously across the whole project, so the
    first figure of the First Law notes came out as Figure 4 on the website
    and Figure 1 in its PDF. The two builds are meant to say the same thing
    about the same figure, and there is no Sphinx setting for per-page
    numbering that does not also number every section heading, so the
    numbers are corrected here, in the built HTML.

    The mapping is taken from the figures themselves, in the order they
    appear, and applied to both the captions and the references, which are
    keyed by the anchor in the href rather than by the text they carry.
    Tables are numbered the same way and for the same reason. Equations need
    none of this: with math_numfig off, Sphinx numbers them page by page.
    """
    fixed = 0
    for stem in stems:
        page = SITE / (stem + ".html")
        if not page.exists():
            continue
        html = page.read_text(encoding="utf-8")
        number, word = {}, {}
        for tag, name in ((FIGURE_TAG, "Figure"), (TABLE_TAG, "Table")):
            order = [m.group(1) for m in tag.finditer(html)
                     if CAPTION_NUMBER.search(m.group(2))]
            for i, ident in enumerate(order):
                number[ident], word[ident] = i + 1, name
        if not number:
            continue

        def fix_caption(m):
            if m.group(1) not in number:
                return m.group(0)
            label = "%s %d " % (word[m.group(1)], number[m.group(1)])
            body = CAPTION_NUMBER.sub(
                lambda c: c.group(1) + label + c.group(3), m.group(2), count=1)
            return m.group(0).replace(m.group(2), body, 1)

        html = FIGURE_TAG.sub(fix_caption, html)
        html = TABLE_TAG.sub(fix_caption, html)

        def fix_link(m):
            if m.group(2) not in number:
                return m.group(0)
            label = "%s %d" % (word[m.group(2)], number[m.group(2)])
            return (m.group(1) + NUMBERED_WORD.sub(label, m.group(3))
                    + m.group(4))

        html = REF_LINK.sub(fix_link, html)
        page.write_text(html, encoding="utf-8")
        fixed += len(number)
    if fixed:
        print("numbered %d figure(s) and table(s) from 1 on each page"
              % fixed)


CSS = """/* Generated by mkweb.py. Edit that script rather than this file. */

/* A heading the original singled out, matching the red used in the PDF. */
.flag > h1, .flag > h2, .flag > h3, .flag > h4 { color: #8C1017; }
@media (prefers-color-scheme: dark) {
  body:not([data-theme="light"]) .flag > h1,
  body:not([data-theme="light"]) .flag > h2,
  body:not([data-theme="light"]) .flag > h3,
  body:not([data-theme="light"]) .flag > h4 { color: #F2A0A4; }
}
body[data-theme="dark"] .flag > h1,
body[data-theme="dark"] .flag > h2,
body[data-theme="dark"] .flag > h3,
body[data-theme="dark"] .flag > h4 { color: #F2A0A4; }

/* Captions flush left, as in the PDF. Sphinx centres a figure's contents,
   caption included; the image stays centred and only the caption changes.
   Left-aligned text reads more easily than centred or justified text. */
figure figcaption, figure figcaption p { text-align: start; }
table caption, table caption p { text-align: start; }
"""


INDEX = """# {title}

{intro}

{toctrees}"""

TOCTREE = """```{{toctree}}
:maxdepth: 2
:caption: {caption}

{entries}
```
"""

CONF = '''# Generated by mkweb.py. Edit that script rather than this file.
project = @PROJECT@
author = @AUTHOR@
copyright = @COPYRIGHT@

extensions = ["myst_parser"]
myst_enable_extensions = ["dollarmath", "amsmath", "attrs_inline",
                          "attrs_block", "colon_fence", "deflist"]
myst_heading_anchors = 3

# Figures are numbered by Sphinx rather than by hand, so that a figure added
# in the middle renumbers everything after it and every reference follows.
# numfig_secnum_depth = 0 numbers them 1, 2, 3 through the page rather than
# by section, which is what the PDF does too.
numfig = True
numfig_format = {"figure": "Figure %s", "table": "Table %s"}
numfig_secnum_depth = 0
# Equations with an identifier are numbered (1), (2), … on each page, as in
# the PDF, rather than through the whole site, and a reference to one reads
# "Equation (3)".
math_numfig = False
math_eqref_format = "Equation ({number})"

source_suffix = {".md": "markdown"}
exclude_patterns = ["_build"]

html_theme = "furo"
html_title = @TITLE@
html_static_path = ["_static"]
html_css_files = ["site.css"]
# Set from contents.yaml. html_copy_source goes with it: without that, the
# link disappears but _sources/ is still written into the built site.
html_show_sourcelink = @SHOW_SOURCE@
html_copy_source = @SHOW_SOURCE@

# MathJax is served from the site itself rather than from a content delivery
# network, so the notes keep working on a network that blocks the CDN and do
# not depend on a third party staying up. It renders the mathematics and, with
# it, supplies the MathML and the speech text a screen reader needs:
# assistive-mml is what puts a hidden MathML copy of every formula in the page.
mathjax_path = "mathjax/tex-mml-chtml.js"
mathjax3_config = {
    "options": {
        "menuOptions": {"settings": {"assistiveMml": True}},
    },
}
# The TeX delimiters are deliberately left alone. Sphinx has already turned the
# $...$ of the Markdown into MathJax's own \\( ... \\), and overriding
# inlineMath here would stop it recognising them.

# Language matters for screen readers and is required by WCAG.
language = @LANGUAGE@
'''


def write_project(titles):
    # One toctree per part of contents.yaml, holding only its published
    # documents. A part with nothing published is left out, rather than
    # printing an empty heading in the sidebar.
    trees = []
    for part in contents.parts():
        pub = part.published()
        if not pub:
            continue
        trees.append(TOCTREE.format(
            caption=part.title,
            entries="\n".join(d.web for d in pub)))
    (WEB / "index.md").write_text(
        INDEX.format(title=contents.site("title"),
                     intro=contents.site("intro"),
                     toctrees="\n".join(trees)),
        encoding="utf-8")
    show_source = bool(contents.site("show_source"))
    conf = CONF.replace("@SHOW_SOURCE@", "True" if show_source else "False")
    for key in ("project", "author", "copyright", "title", "language"):
        conf = conf.replace("@%s@" % key.upper(), repr(str(contents.site(key))))
    (WEB / "conf.py").write_text(conf, encoding="utf-8")
    static = WEB / "_static"
    static.mkdir(parents=True, exist_ok=True)
    (static / "site.css").write_text(CSS, encoding="utf-8")


def build(stems):
    # Sphinx copies images into _images and never removes one, so the built
    # site is emptied of them first. It is equally happy to leave behind the
    # page of a document that has been renamed, so those go too.
    images = SITE / "_images"
    if images.exists():
        shutil.rmtree(images)
    # Sphinx writes _sources/ when html_copy_source is on and leaves it in
    # place when it is turned off, so the Markdown would stay on the site
    # after the link to it had gone.
    sources = SITE / "_sources"
    if sources.exists() and not contents.site("show_source", True):
        shutil.rmtree(sources)
    keep = {s + ".html" for s in stems} | {"index.html", "genindex.html",
                                           "search.html"}
    if SITE.exists():
        for p in SITE.rglob("*.html"):
            if "_static" in p.parts:
                continue
            if str(p.relative_to(SITE)).replace("\\", "/") not in keep:
                p.unlink()
        # a year folder whose every page has been held back leaves an empty
        # directory behind, which looks like a broken build
        for d in sorted(SITE.glob("*"), reverse=True):
            if d.is_dir() and d.name != "_static" and not any(d.iterdir()):
                d.rmdir()
    proc = subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "html", "-q",
         str(WEB), str(SITE)],
        capture_output=True, text=True)
    sys.stderr.write(proc.stderr)
    if proc.returncode:
        sys.exit("sphinx-build failed")
    # Sphinx makes _sources/ whether or not it fills it, and a year folder
    # whose pages are all held back leaves an empty directory too.
    for d in sorted(SITE.glob("*"), reverse=True):
        if d.is_dir() and d.name != "_static" and not any(d.iterdir()):
            d.rmdir()
    print("built", SITE)


def main():
    # read the port first, so a mistyped one stops before the build
    port = serve_port() if "--serve" in sys.argv else None
    eq_alts = {}
    titles = stage(eq_alts)
    write_project(titles)
    build([d.web for d in contents.documents(published_only=True)])
    label_equations(eq_alts)
    renumber_figures([d.web for d in contents.documents(published_only=True)])
    if globals().get("BAD_REFS"):
        sys.exit("%d cross-reference(s) point at no figure" % BAD_REFS)
    if globals().get("BAD_TABLES"):
        # the site is still built, but the shell hears about it
        sys.exit("%d table(s) did not render" % BAD_TABLES)
    if port:
        subprocess.run([sys.executable, "-m", "http.server", "-d", str(SITE),
                        port])


def serve_port():
    """The port given after --serve, or 8000 when none is."""
    rest = sys.argv[sys.argv.index("--serve") + 1:]
    if rest and not rest[0].startswith("-"):
        if not rest[0].isdigit() or not 0 < int(rest[0]) < 65536:
            sys.exit("--serve takes a port number, not %r" % rest[0])
        return rest[0]
    return "8000"


if __name__ == "__main__":
    main()
