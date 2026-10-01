# {{SHORT}} accessible notes — conventions

Working record for the project that converts the {{SHORT}} notes into
accessible form: a tagged PDF (PDF/UA-1) and a website (WCAG 2.1 AA) built from
one Markdown source per document. `BUILD.md` says how to run the builds. This
file says how the source is written and why. Add to it as the project makes
decisions of its own.

## Where things live

```
./
  md2tex.py, buildtex.py            the PDF build
  mkweb.py, checkweb.py             the website build
  package.py                        the archive
  contents.py           reads contents.yaml for every build script
  contents.yaml         the table of contents and the site settings
  {{CLASS}}.cls         the LaTeX class
  src/                  the lectures (*.md, the source of truth), each with
                        its generated *.tex and *.pdf beside it
  2026/                 one offering's homework solutions and exams, the
                        same arrangement
  figures/              *.svg, drawn by the scripts below, and the *.pdf that
                        cairosvg makes from them for LaTeX
  scripts/
    figures_audit.py    figures on disk, referenced and drawn all agree
    figures/
      make_figures_*.py one drawing script per document
      figlib.py         shared drawing helpers
  originals/            the originals (OneNote exports, scans), untracked
  work/                 page images rendered from them, untracked
  web/ site/            the website staging and build, generated
```

Only the Markdown, the class file, `figures/*.svg`, the scripts and
`contents.yaml` are sources. Every `*.tex`, `*.pdf`, `*.aux` and `*.log` in
`src/` or a year folder, everything in `web/` and `site/`, and every
`figures/*.pdf` is generated and can be deleted at any time.

The build scripts that are run day to day stay at the top of the project,
so every command starts from there. Other code lives in `scripts/`.

A lecture is the same every year, so it lives in `src/`. Homework and exams
belong to one offering, so they live in a folder named for the year, under
names that carry no year of their own (`homework01_solution.md`). Every
document keeps its `.tex`, scratch files and `.pdf` beside its Markdown, so
a year's material moves as a unit. The figures of every document go in the
shared `figures/`.

## The table of contents

`contents.yaml` lists every document once, grouped into the parts the website
sidebar shows. Each entry carries one flag:

```yaml
  - path: src/03_Second_Law.md
    checked: false
```

`checked: false` keeps a document off the website altogether: it is not
staged, no page is built and nothing links to it. Everything else still
covers it. Its PDF is built and checked, its figures are audited and it goes
in the archive, because the reason to hold a document back is to have
something to proofread from. Publishing it is one word. Set `checked: true`
only when the author says the document has been read against the original.

The `site:` block holds the settings for the whole project (title, author,
the LaTeX class name, the archive name, `show_source`). These are the only
place the course name is written. `python3 contents.py` prints the list and
what each build will do with it.

On the website the `src/` folder is dropped from the address, so
`src/03_Second_Law.md` is published as `03_Second_Law.html` and
`2026/homework01_solution.md` as `2026/homework01_solution.html`.

## Pipeline

```
                     ┌─ mkweb.py   → Sphinx + MyST + MathJax → site/
Markdown (*.md) ─────┤
                     └─ md2tex.py  → {{CLASS}}.cls → lualatex → *.pdf beside the *.md
```

`md2tex.py` is a build step, not a migration. The `.tex` is overwritten on
every build, so a correction always goes in the `.md`.

## Markdown conventions

### Frontmatter

```yaml
---
title: "<Full title> — {{TITLE}}"
docheading: "<Short title>"
lang: en
runningfoot: "{{SHORT}} — <Short title>"
description: "{{SHORT}} <Topic> lecture notes: <topic list>."
subtitle: "{{TITLE}}."
---
```

For a homework set: `docheading: "Homework 3 Solutions"`, and a description
that names each problem in a few words.

There is no note about the transcription at the top of a document and no
marker at the original's page boundaries. Both were tried and both were
removed by the author: what a reader needs to know about the conversion is
in the closing notes, and the page structure of a OneNote export carries no
meaning.

`docheading` becomes the only level-1 heading. Body headings therefore start
at `##` and must run h1 → h2 → h3 with no skipped levels. Both builds check
this. Where the original relies on a visual break rather than a heading, add
a heading.

A homework solution is the solutions only, under `## Problem N` and
`### Part (a): <what the part finds>`. The problem statements are not
transcribed: the author keeps the problem set separately.

### Mathematics

Mathematics is LaTeX between dollar signs: `$P\tilde{V} = RT$` inline, `$$…$$`
for a display equation. MathJax typesets it on the web and adds a MathML copy
for screen readers. `md2tex.py` passes it through to LaTeX.

Transcribe the notation the original uses, correctly typeset:

- Sums, products and integrals with their limits, as the original writes
  them (`\sum_{i=1}^{N}`, `\int_{0}^{\infty}`), never limits given in
  words. Matrices and determinants as arrays (`pmatrix`, `vmatrix`), never
  read out row by row in prose.
- Real nested subscripts, `x_{j}` and `\mu_{i}^{\alpha}`, never a spaced
  imitation such as `x\, j`. Running indices italic (`x_{i}`), labels that
  are words or abbreviations upright (`S_{\text{gen}}`, `T_{\mathrm{c}}`).
- Words inside mathematics in `\text{…}`, so "Gibbs–Duhem" does not come out
  as a subtraction of two italic variables.
- Script letters with `\mathcal{L}`, `\mathcal{H}`. Upright `\mathrm{d}` for a
  differential. `\vec{F}` for vectors, `\tilde{V}` per mole, `\hat{V}` per
  mass, `\dot{m}` rates, `\bar{V}` partial molar, or whatever the original's
  own marks mean. An underline that is notation (`\underline{V}`) stays.
- Delimiters as the original draws them. No `\left( … \right)` round a plain
  fraction unless the original has the brackets. `\Biggl[ … \Biggr]` and an
  evaluation bar `\Biggr|_{P=P_0}` where it does.
- Hand annotations are typeset, not described: `\cancel{…}` for a struck
  term, `\underbrace{…}_{0}` for a term marked zero, a labelled
  `\underbrace{…}_{\text{…}}`, `\overset{…}{=}` for a reason written over
  an equals sign, `\boxed{…}` for a boxed or ringed result. Put `{}` after
  an `\underbrace` that is followed by a binary operator, or the spacing
  collapses.
- No mathematics outside the dollars: `$a = …$`, not `*a* $= …$`; `$\ln x$`,
  not `ln $x$`.
- `\,` (a thin space) only where it belongs: after a comma in a subscript
  list (`x_{i,\,j}`), between two adjacent fractions, and before a
  differential (`f(x)\,\mathrm{d}x`). Nowhere else.
- An exponent that would carry its own superscripts or a fraction is written
  `\exp(…)` rather than raised.
- LaTeX commands (`\xi`, `\partial`) rather than pasted Unicode inside
  mathematics in a new project. Both render; if the project's documents
  already use Unicode Greek, stay consistent with them.

### Equations with a spoken form

Most equations are best left to the automatic tagging, because MathJax's
MathML lets a reader walk through an expression term by term. Where the
notation is right on the page but unfollowable aloud (a matrix, a struck
term, an underbrace, an integral over a named region) give it a sentence:

```
::: {.eq alt="d U equals delta Q plus delta W, where the enthalpy term is struck out and marked zero."}
$$\mathrm{d}U = δQ + δW + \underbrace{\cancel{\tilde{H}\,\mathrm{d}n}}_{0}$$
:::
```

The block holds exactly one display equation (an `aligned` environment
counts as one), and the sentence contains no LaTeX and no double quote. In the PDF it becomes a `/Formula` structure element with
the sentence as `/Alt`, which replaces the subtree for a screen reader. On
the web it becomes `role="math"` with the sentence as `aria-label`, the
rendered mathematics marked `aria-hidden`. Write the sentence the way a
lecturer would read the equation out, naming the struck or braced parts.

### Block classes

Pandoc fenced divs. `mkweb.py` maps each onto a MyST directive.

- `::: note`: a boxed aside.
- `::: eq`: display equations, one per paragraph inside the div.
  `::: {.eq alt="…"}` holds one equation with a spoken form.
- `::: problem`: a problem statement quoted from the original.
- `::: keep`: content that must not break across a page in print.
- `::: flush`: a float barrier, written empty on its own:

  ```
  ::: flush
  :::
  ```

  `\FloatBarrier` in the PDF, nothing on the website. There is no "put this
  figure exactly here". The `float` package's `[H]` is not compatible with
  the tagging code, so figures are `[!ht]` floats.
- `::: quote`: quoted passages.

A list inside `::: eq` is moved outside the equation block by `md2tex.py`,
and a list item that begins with a display equation gets a `\leavevmode`,
because a list that never enters horizontal mode aborts the tagged run with
"The number of automatic begin and end text-unit para hooks differ".

### Inline conventions

- Text the original underlines for emphasis is bold, since an underline
  reads as a link.
- Numbered states in the original, often circled digits, are "state 1" in
  prose and a drawn circle in a figure. The circled-digit characters are
  missing from the PDF fonts.

### Characters the PDF font lacks

Running text, captions and table cells are set in Latin Modern, which lacks
some symbols (⋮, ①–④, π, ′, ≪, ≫). A missing character is dropped from the
PDF with nothing but a `Missing character` line in the `.log`. Write such
symbols as mathematics, where the math font has them: `$\vdots$`, `$\pi$`,
`$\ll$`. The build's twelfth check reads the log and fails on any.

### Tables

**Pipe tables, always.** MyST reads only pipe tables. Pandoc's other table
syntaxes are parsed as paragraphs on the website, so the cells arrive run
together while the page still builds and passes every check. `mkweb.py`
reports any table that is not a pipe table and exits non-zero.

Pipe tables carry a header row. `md2tex.py` emits them as `longtable` with
`\endhead`, which is what makes the tagging code mark header cells `/TH`.
They carry no rules, since `\hline` and booktabs rules abort the tagged run.
Mark an indeterminate entry with an em dash and say so above the table.

A figure placed directly after a long table can be pushed off the page. Put
the figure before the table. A table with many columns can run off the right
edge; `buildtex.py` warns about anything more than 10 pt too wide, and such a
table wants shorter headers, units moved to the header, or splitting.

Where a printed plot is drawn from a data table beside it, compute the figure
from the transcribed table rather than tracing the plot. Keep such data in a
helper module listed under `support:` in `contents.yaml`.

## Figures

Every sketch is redrawn as SVG by the document's drawing script, built on
`figlib.py`. Curves are computed from their equations, so each bends the way
its own equation makes it bend.

Naming: `fig_<doc>_<NN>_<name>.svg`, where `<doc>` is a short prefix unique
to the document (`c03` for lecture 3, `hw02` for homework set 2; a second series of
lectures gets its own letter). Each document has exactly one drawing script named to match, in
`scripts/figures/` (`make_figures_03.py`, `make_figures_hw02.py`), and it
writes only its own prefix into the root `figures/`. The Markdown references
a figure relative to itself, `../figures/fig_…svg`, from `src/` and from a
year folder alike, so it also renders in any Markdown viewer. `md2tex.py`
and `mkweb.py` resolve it for their builds.

The description lives in the Markdown, not in the script, so a figure can be
redrawn without touching its description:

```
![**Short title.** Long prose description of everything in the
figure.](../figures/fig_c03_02_name.svg){#fig-c03-02 width=360 alt="Short alternative text."}
```

The caption is the long description, visible to everyone. The `alt` is one
sentence. `width` is in CSS pixels, and the PDF caps a figure at 5.6 in.

### Numbering and cross-references

**No figure number is written by hand.** The identifier is the file name cut
to its first three parts (`fig_c03_02_…` → `#fig-c03-02`), and a reference is
a link with no text: `[](#fig-c03-02)`. It comes out as "Figure 2" in both
builds and as a live link on the web. `mkweb.py` renumbers each page from 1,
because Sphinx otherwise numbers continuously across the site. A number that
refers to the printed original ("Figure 7.2 of the text") stays plain text.

Captions are flush left, ragged right, in both builds. The image is centred.

A figure that is not in the original is allowed only where it draws
something the original states in words, and is called an addition in the
closing notes.

### Colour and labels

`INK = #1a1a1a` (15.3:1 on white). `FAINT = #5a5a5a` (7.0:1, hatching and
fills only). Label syntax inside `txt()`: `*x*` italic, `~x~` subscript,
`^x^` superscript, nesting allowed. `txt()` measures the label in DejaVu Sans
and always emits `text-anchor="start"`, because cairosvg, which makes the
figure PDFs, misplaces every run after the first of an anchored `<text>`.

Combining marks do not compose in either renderer, so `x⃗`, `G̃`, `V̄` come
out with a dotted-circle placeholder. Precomposed characters (Ã, Ṽ, Ĥ, ṁ) are
fine. Q̇, V̂ and H̃ have no precomposed form. Draw those with
`figlib.label(x, y, [("*Q*", "dot"), ("~in~", None)])`, and a dotted capital
standing alone with `figlib.dotted(x, y, "W")`, since the precomposed Ẇ's dot
is faint and off-centre.

## Checks

Twelve on each PDF, from `buildtex.py`: language, tagged, structure tree,
title in metadata, title in window bar, PDF/UA identifier, headings start at
level 1, no skipped levels, alt text on every figure, table headers tagged,
formula alternative text not raw LaTeX, and no character missing from the
fonts. Check 11 depends on the TeX Live in use (see `BUILD.md`). Lines and
tables too wide for the page are a warning.

Nine on each web page, from `checkweb.py`, in a real browser because the
mathematics exists only after MathJax has run: language, one level-1
heading, no skipped levels, alt text, every formula typeset, every formula
carrying MathML, no MathJax errors, no vague link text, a page title.

Before either, `notation_lint.py` from the skill reads the Markdown for the
notation compromises above.

Passing either set is necessary, not sufficient. Run PAC 2024 on the PDFs
and a WCAG audit on the site before publishing.

## Closing section

A document ends with `## Notes on changes made for accessibility` when there
is something in it. Keep it to what the author needs to act on or judge:

- apparent errors or inconsistencies in the original, transcribed as written,
  with what the likely intent is (including any an earlier transcription had
  silently corrected);
- places where the reading was uncertain (a smudged subscript, an ambiguous
  sign) and what was chosen;
- figures added that are not in the original;
- anything reordered from the original's layout;
- one line saying that struck, braced or boxed terms are typeset with their
  marks and carry a spoken description, where the document has them.

Leave out routine housekeeping that every document shares (page artifacts
removed, glyphs dropped, headings added). The point is to put the reader in a
position to judge, not to rewrite the author's notes quietly or to bury the
one real question under boilerplate.

## Packaging and git

`package.py` builds `{{ARCHIVE}}.zip` from `contents.yaml`, the support
files it names, and the figures each document references. It never globs
the folder, and it refuses to run while `scripts/figures_audit.py` fails. The archive
mirrors the project, so unzipping it gives a working copy.

`.gitignore` tracks the sources and nothing generated. `figures/*.svg` is
tracked, since it is what the documents reference. `originals/` and `work/`
are left out by default. Delete the `/originals/` line before the first
commit to keep the originals in the repository instead, because removing
them later means rewriting history.
