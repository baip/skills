---
name: accessible-notes-conversion
description: Convert handwritten, typed or OneNote-exported course notes, homework solutions and exams into accessible Markdown that builds both a tagged PDF (PDF/UA-1) and a website (WCAG 2.1 AA), with every figure redrawn as described SVG and every equation typeset in real notation with a spoken form. Bundles the build scripts, LaTeX class, checks, a notation lint and a project scaffold. Use this whenever someone uploads or points to lecture notes, scanned or OneNote PDFs, homework solutions or teaching material and mentions accessibility, ADA Title II, WCAG, PDF/UA, screen readers, alt text, or transcription, and also for any later review round on such a project (fixing figures, labels, math notation, captions, glyphs missing from a PDF, reorganizing the repository), even if they do not say "accessible".
compatibility: Python 3.10+, pandoc 3, TeX Live 2024+ with lualatex, cairosvg, pypdf, pyyaml, Pillow, poppler (pdftoppm); for the website Sphinx, myst-parser, furo, MathJax 3 (npm) and Playwright.
---

# Accessible course notes from handwritten and typed originals

The deliverable is one Markdown file per document plus one figure-drawing
script per document. A tagged PDF and a website are generated from them by
the toolkit bundled here. The Markdown is the only source: fixes go in the
`.md`, never in the generated `.tex` or HTML.

```
                     ┌─ mkweb.py   → Sphinx + MyST + MathJax → site/
Markdown (*.md) ─────┤
                     └─ md2tex.py  → <class>.cls → lualatex  → PDF beside the .md
```

A project looks like this:

```
md2tex.py buildtex.py mkweb.py checkweb.py package.py contents.py   build scripts, run from the root
<class>.cls  contents.yaml  CONVENTIONS.md  BUILD.md  AGENTS.md  CLAUDE.md
src/                 lectures: NN_Name.md, with NN_Name.tex and .pdf beside each
2026/                one offering's homework and exams, same arrangement
figures/             fig_<doc>_<NN>_<name>.svg, and the PDFs made from them
scripts/figures_audit.py
scripts/figures/     figlib.py, make_figures_<doc>.py, data helpers
originals/  work/    the originals and page images, untracked
```

## What is bundled

| Path | Use |
|---|---|
| `scripts/init_project.py` | scaffold a new project, or `--update-toolkit` in an existing one |
| `scripts/render_pages.py` | render an original's pages (and zoomed crops) to read them |
| `scripts/contact_sheet.py` | render changed SVG figures onto one PNG, each beside its original, to inspect and send |
| `scripts/notation_lint.py` | flag notation compromises: limits in words, described annotations, flattened subscripts, letters outside the maths, bad alt blocks, glyphs the PDF font lacks |
| `assets/toolkit/` | the build scripts and `notes.cls`, placed into a project by `init_project.py` |
| `assets/templates/` | `contents.yaml`, an example lecture and drawing script, `.gitignore`, `package.json`, and the project's `AGENTS.md` and `CLAUDE.md` (instructions for coding agents) |
| `references/transcribing.md` | reading originals, OneNote quirks, lectures and homework, pre-handover checks |
| `references/figures.md` | how to draw figures that survive review |
| `references/notation-pass.md` | revising existing documents to real notation, alone or with parallel helpers |
| `references/review-and-delivery.md` | review rounds, git, working through a file bridge, publishing |
| `references/conventions.md`, `references/building.md` | become the project's `CONVENTIONS.md` and `BUILD.md` |

## 0. Set up or find the project

1. **Look for an existing project**: `contents.yaml`, `md2tex.py`, a `*.cls`,
   `CONVENTIONS.md`, `BUILD.md`. If it is there, **read its `AGENTS.md`,
   `CONVENTIONS.md` and `BUILD.md` first and follow them where they differ
   from this skill**, since they record decisions the author has made. If it
   has no `AGENTS.md`, offer to add one from
   `assets/templates/AGENTS.template.md`, with `CLAUDE.template.md` as its
   `CLAUDE.md`, so that any coding agent opening the project finds the
   rules. Check the project's own recent commits too: the author often
   revises documents by hand, and those revisions are the current house
   style (frontmatter wording, what the closing notes keep).
2. **Otherwise scaffold one:**

   ```
   python3 <skill>/scripts/init_project.py <folder> \
       --title "CHEM 101 — General Chemistry" --short "CHEM 101" \
       --class chem101 --author "…" --copyright "…"
   ```

   Build the example lecture once to confirm the machine is set up
   (`BUILD.md` lists the installs), then remove it from `contents.yaml`,
   `src/`, `scripts/figures/` and `figures/`.
3. **Ask what you cannot infer, in one round**: course name and short code,
   which documents come first, where the originals and the project live
   (uploads, a folder on the author's computer, a git repository), whether
   to build the PDF and website in each round, and who pushes. Unless told
   otherwise, commit locally and never push.
4. **Standing instructions hold** for every later round until lifted ("do
   not build", "I will push myself").

## 1. Read the originals

Text extraction returns only typed text. Handwriting and sketches are ink,
so render the pages and read them as images, zooming into anything small.
This needs an agent that can view local image files. If yours cannot, say
so and stop: a transcription from extracted text misses the handwriting.

```
python3 <skill>/scripts/render_pages.py originals/03.pdf work/03
python3 <skill>/scripts/render_pages.py originals/03.pdf work/03 --zoom 5 0.1 0.2 0.9 0.5
```

Read `references/transcribing.md` before the first document.

## 2. Transcribe

Follow the project's `CONVENTIONS.md`. The rules that matter most:

- **Where it goes.** A lecture is `src/NN_Name.md`; homework and exams go in
  the year folder (`2026/homework03_solution.md`). Add each to
  `contents.yaml` with `checked: false`. Only the author sets it `true`,
  which publishes it to the website.
- **Frontmatter.** `title`, `docheading` (the only h1), `lang`,
  `runningfoot`, `description` ("<SHORT> <Topic> lecture notes: <topics>."),
  `subtitle` ("<course title>."). Body headings start at `##` and never skip
  a level. No "About this transcription" note and no page-boundary markers:
  the author removes them, so do not add them.
- **Homework solutions.** Transcribe the solutions only, under
  `## Problem N` and `### Part (a): <what it finds>`. When the author
  supplies the problem set (as .tex or .pdf), use it to understand the
  solutions and for the notation, not as text to convert.
- **Mathematics: the notation of the original, correctly typeset.** LaTeX
  in `$…$`, and `$$…$$` inside `::: eq`. Sums, products and integrals carry
  their limits; matrices and determinants are typeset; script letters are
  `\mathcal{}`; running indices italic, labels upright; real nested
  subscripts (`x_{j}`, never `x\, j`); words in `\text{}`; no `\left(\right)`
  round a bare fraction unless drawn; `\,` only after a comma in a subscript
  list, between adjacent fractions and before a differential; `{}` after an
  `\underbrace` followed by an operator; `\exp(…)` for an exponent carrying
  a fraction.
- **Hand annotations become notation** (`\cancel`, `\underbrace{…}_{0}`,
  labelled braces, `\overset{…}{=}`, `\boxed`, evaluation bars), and such an
  equation gets a spoken form: `::: {.eq alt="…"}` holding exactly one
  display equation, with a plain sentence naming the marks (no LaTeX, no
  double quotes). Ordinary equations get no alt: MathJax's MathML lets a
  reader walk through them.
- **The PDF text font lacks some symbols** (⋮, ①, π, ′, ≪, ≫). Write them as
  mathematics (`$\vdots$`), and "state 1" for circled numbers. The build
  fails on any missing character.
- **Tables**: pipe tables only, with a header row, no rules. Put a figure
  before a long table, never straight after it. Keep tables narrow enough
  for the page (the build warns when one is too wide).
- **Blocks**: `::: eq`, `::: problem`, `::: keep`, `::: flush`, `::: quote`,
  `::: note`. There is no `[H]`.
- **Errors in the original** are transcribed as written and flagged in the
  closing notes with the evidence, never silently corrected. When the author
  says to fix one, fix it.
- **Closing notes** (`## Notes on changes made for accessibility`) hold only
  what the author needs to check or decide: possible errors, uncertain
  readings, additions. No boilerplate.

Run `python3 <skill>/scripts/notation_lint.py <doc>.md` before building:
its errors must be fixed, its warnings looked at against the original.

## 3. Redraw every figure

Every sketch becomes an SVG drawn by `scripts/figures/make_figures_<doc>.py`
on `figlib.py`, named `fig_<doc>_<NN>_<name>.svg`, referenced from the
Markdown relative to itself as
`![**Title.** Long description.](../figures/fig_….svg){#fig-<doc>-<NN> width=NNN alt="…"}`
and cited as `[](#fig-<doc>-<NN>)`. Never write a figure number by hand.
**Read `references/figures.md` before drawing.** In short: list what the
original shows in a file before drawing (counts, directions, what is open,
where labels sit), compute curves from equations, centre them in the plot, start and end arrows on the
objects, keep labels close to and clear of lines (`place_label` in dense
plots), draw accents and circled numbers rather than typing them, size the
viewBox to the drawing, check the render beside the original, and update
the caption whenever the drawing changes.

## 4. Build and verify

```
python3 scripts/figures/make_figures_<NN>.py
python3 md2tex.py <name>                  # e.g. 09_Mixtures or homework03_solution
python3 buildtex.py <name>                # 12 checks, plus a too-wide warning
python3 mkweb.py && python3 checkweb.py   # 9 checks per page, MathJax errors included
python3 scripts/figures_audit.py
python3 <skill>/scripts/contact_sheet.py work/sheet.png \
    --original originals/<doc>.pdf PAGE X0 Y0 X1 Y1 figures/fig_<doc>_<NN>_*.svg
```

- **Look at the output.** View the contact sheet of every changed figure,
  each beside its original (`--original`, before the figure it goes with), and
  render the PDF pages holding changed equations, tables and figures. Give
  the author the sheet, as a file if you can send one, otherwise its path.
- A document held back with `checked: false` is not on the website. To test
  its page, build the site in a scratch copy with it set to `true`.
- Check 11 ("formula alternative text is not raw LaTeX") fails on TeX Live
  older than tagpdf 1.0. If it fails on the machine that makes the
  published PDFs, say so rather than hiding it.
- If the author said not to build, do not write build output into their
  folder. A scratch copy elsewhere is fine for checking a risky change.
- The checks are necessary, not sufficient. Recommend PAC 2024 on the PDFs
  and a WCAG audit of the site before publishing.

## 5. Review rounds and batch revisions

Read `references/review-and-delivery.md`. In short: sync to the author's
current files first, make one task per bullet plus a verification task,
cross-check each point against the original, answer questions separately
from edits (change nothing for a question until the author decides), fix
project-wide conventions in the toolkit and in `CONVENTIONS.md`, and report
in one line per item.

When the author asks for the same revision across many documents (for
example "make 05–10 match what I did to 01–04"), read
`references/notation-pass.md`: study the author's own revision as the
model, do the mechanical parts with a script, and hand the per-equation work
to parallel helpers, two or three documents each, with a written brief.
Without helpers, work through the documents one or two at a time from the
same brief.

## 6. Delivery

- Edit on the author's machine when the project lives there. Regenerate
  SVGs by running the drawing script there rather than copying them, since
  file bridges can rewrite images in transit. Confirm by checksum when you
  copy.
- Commit with the author's own identity and a message listing the items.
  Never push unless asked, and decline hooks that ask you to.
- If the link to the author's computer drops, commit in your own clone and
  hand over a git bundle (`git bundle create x.bundle <their-head>..main`)
  that they can pull, or apply it when the link returns.
- `python3 package.py` builds an archive of the whole project from
  `contents.yaml`, and refuses while `scripts/figures_audit.py` fails.
- To give a project a newer toolkit:
  `python3 <skill>/scripts/init_project.py <folder> --update-toolkit`.
