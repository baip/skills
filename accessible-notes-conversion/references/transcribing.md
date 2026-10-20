# Transcribing an original

How to turn one original (a OneNote export, a scan, a typed PDF with
handwritten additions) into a Markdown document that follows the project's
`CONVENTIONS.md`.

## Read the pages as images

Text extraction returns only typed text. In a OneNote export or a scan,
every handwritten line and every sketch is ink, so extraction silently skips
most of the content. Render the pages and read them. This needs an agent
that can view local image files (Claude Code, Codex, or OpenCode with a
model that reads images). If yours cannot, say so and stop rather than
transcribe from extracted text:

```
python3 <skill>/scripts/render_pages.py originals/03.pdf work/03
```

Each page comes as a whole and as top and bottom halves, because a full page
is too small to read subscripts, primes and accents reliably. Zoom into
anything you are unsure of:

```
python3 <skill>/scripts/render_pages.py originals/03.pdf work/03 --zoom 5 0.1 0.2 0.9 0.5
```

Extracted text is still useful as a cross-check on the typed parts (`pdftotext
-layout`), since it catches misreadings of typed words and numbers.

Work a page at a time, in order. Keep your place in your own notes rather
than in the document: page-boundary markers and a note about the
transcription at the top were tried in this workflow and removed by the
author, so do not add them.

## Lectures and homework

A lecture goes in `src/` under its number and name (`src/05_Equilibrium.md`)
and follows the original's structure, with headings added where the
original relies on a visual break.

A homework solution goes in the year folder (`2026/homework03_solution.md`)
and holds the solutions only, under `## Problem N` and
`### Part (a): <what the part finds>`, numbered as the problem set numbers
them. Where a part has no label in the solution but answers two parts of
the problem set at once, say so in the heading ("Parts (c) and (d): the
lowest final temperature"). If the author supplies the problem set, read it
first: it fixes the notation (what a tilde or hat means, which symbol is
the field and which the enthalpy) and tells you what each part asks, so you
can see when a solution leaves part of a question unanswered, which goes in
the closing notes. Do not transcribe the problem statements unless asked.

A note the solver writes to the reader ("use tilde for enthalpy") becomes a
sentence in the text, not a mark.

## OneNote exports in particular

- **Repeated lines at page breaks.** The export often repeats the last line
  of a page at the top of the next. Drop the repeat.
- **Reading order.** OneNote text boxes are exported in creation order, not
  visual order. Follow the page as it reads visually: top to bottom, and a
  side note next to what it annotates.
- **Mixed typed and handwritten.** A typed heading followed by a handwritten
  derivation is one passage. Transcribe both into the same flow.
- **Decorative ink.** Underlining for emphasis becomes bold. Boxes drawn
  round a result become a `::: keep` block or nothing. Arrows pointing from
  a remark to a term are transcribed as the remark, placed next to the term.

## Mathematics

Transcribe what the original writes, typeset properly, following the
notation rules in `CONVENTIONS.md`. The common decisions:

- **Symbols.** Keep the author's symbols, subscripts and accents exactly,
  even where a textbook uses others. Zoom in on every subscript that could be
  one of two letters (i or j, 1 or l, ν or v) and every sign.
- **Annotations.** A struck term becomes `\cancel{…}`. A term with "= 0"
  written under it becomes `\underbrace{…}_{0}`. A reason written over an
  equals sign becomes `\overset{…}{=}`. A step labelled with its
  justification ("by Gibbs–Duhem") gets the words in `\text{…}` or in the
  prose right before it.
- **Spoken form.** Where an equation uses any of those annotations, a matrix,
  or anything else that a screen reader would read as a jumble, wrap it in
  `::: {.eq alt="…"}` with a sentence (see `CONVENTIONS.md`).
- **Evaluation bars and big brackets.** `\Biggl[ … \Biggr]_{P=P_0}` where the
  original draws them, sized to what they enclose.

## When the original seems wrong

Transcribe what is written. If a sign, index or step looks like an error,
keep it as written and record it in the closing notes with what the intent
probably is. The author decides. If the author later corrects it, follow the
author, and note the difference from the original if it is not obvious.

When a reading is uncertain (a smudged character, an ambiguous mark),
choose the reading that makes the mathematics consistent, and list the spot
in the closing notes so the author can check it.

## Tables

Pipe tables with a header row. A column of vertical dots is `$\vdots$` in
each cell. An entry the original leaves blank or unreadable is an em dash,
explained above the table.

## Figures

Every sketch becomes a figure with its own drawing function. Read
`references/figures.md` (in the skill) before drawing. Put the figure's
Markdown where the sketch sits in the reading order, not where it is
convenient, and not directly after a long table.

## Before handing a document over

1. `python3 <skill>/scripts/notation_lint.py <doc>.md` reports no errors,
   and every warning has been looked at against the original.
2. `python3 md2tex.py <name>` and `python3 buildtex.py <name>`. Fix every
   report and every failed check except check 11 on an old TeX Live. Check
   12 fails on any character the fonts lack.
3. The website passes `checkweb.py`. A document marked `checked: false` is
   left out of the site, so build it in a scratch copy of the project with
   the flag set to `true` rather than editing the real `contents.yaml`.
   Only the author marks a document checked.
4. `python3 scripts/figures_audit.py` passes.
5. Render a few pages of the built PDF and look: equations set, figures
   placed near their text, no page overflowing.
6. The closing notes list what the author needs to check, and nothing
   routine.
