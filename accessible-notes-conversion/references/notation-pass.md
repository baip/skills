# Revising documents to real notation

Read this when existing documents need bringing up to the current standard
in one go: typically the author has revised a few by hand and asks for the
rest to match ("convert the math so the display shows the correct notation
with an alt text for the screen reader", "remove the transcription notes and
page markers", "update description and subtitle like I did for 01–04").

Documents first transcribed when mathematics was Unicode running text, or
converted mechanically from it, carry compromises made for screen readers in
that era. The goal now is the reverse: **the displayed version shows the
mathematically correct notation of the original, and where that notation
cannot be followed aloud it carries an alt text.**

## 1. Learn the target from the author's own revision

Find the commit where the author (or an earlier round they approved) revised
a document, and read its diff and message: `git log --stat -- src/04_*.md`,
then `git show <commit> -- <file>`. That diff is the model. Note:

- the frontmatter wording they settled on (description, subtitle);
- what they removed (notes at the top, page markers, closing-note
  boilerplate);
- which constructs they typeset and which they gave an alt.

## 2. Do the mechanical part with a script

Anything that is the same in every file is a script, not a hand edit:
removing a fixed block, deleting marker lines, rewriting a frontmatter
field. Before removing a note at the top of a document, save it to a
scratch folder: it usually lists the compromises that document made
(limits in words, matrices read out, script capitals replaced), which is
the checklist for step 3.

## 3. The per-equation pass

For each document, against the page images of its original:

- **Limits.** Sums, products and integrals get their limits back as the
  original writes them, and the prose that gave them in words goes.
- **Arrays.** Matrices and determinants become `pmatrix`, `bmatrix`,
  `vmatrix`, with an alt; prose that read them row by row goes.
- **Annotations.** Struck terms `\cancel{}`, terms marked zero
  `\underbrace{\cancel{…}}_{0}`, labelled braces, reasons over an equals
  sign `\overset{\text{…}}{=}`, boxed or ringed results `\boxed{}`,
  evaluation bars. Each such equation gets an alt naming the marks, and the
  sentence that described the mark goes unless it says something the
  notation cannot.
- **Symbols.** Script capitals back to `\mathcal{}` everywhere in the file.
  Running indices italic, word labels upright (`\mathrm{}`, `\text{}`), and
  consistently so. Real nested subscripts. Stars and degree signs as
  superscripts (`μ_i^{*}`, `μ^{\circ}`).
- **Broken mechanical conversions.** Look for fractions split across
  tokens (`\frac{Z_N}{N}!` for Z_N/N!, `∂ \ln \frac{Q}{∂T}` for
  ∂ln Q/∂T), linear-text parentheses round bare fractions, and list
  bullets that were really continuation lines starting with + or −.
- **Prose remnants.** Italic letters and function names outside the
  dollars (`*a* $= …$`, `ln $x$`, `e$^{…}$`) become inline mathematics.
- **Silent corrections.** If the earlier transcription quietly corrected
  something in the original, transcribe it as written and add a flag to the
  closing notes. The author decides.
- **Closing notes.** Remove bullets the revision makes untrue, and replace
  them with one bullet: "Where the original strikes a term out, braces a
  group, or …, the equation is typeset with that mark and carries a spoken
  description of it for a screen reader." Keep every flag.

`scripts/notation_lint.py` finds most of the candidates. Its warnings are
prompts to look at the original, not verdicts.

## 4. Splitting the work across parallel helpers

Thirteen documents of 30 to 120 equations each is too much to do carefully
in one context. Hand them out:

- **Two or three documents per helper**, balanced by number of display
  equations. Each helper edits only its own files.
- **One written brief, saved to a file**, that every helper reads first.
  It states the goal in the author's words, points to the model diff and to
  the saved notes, lists the rules above, and says what not to touch: no
  other files, no figures or drawing scripts, no git commands that change
  the repository, and no website build (they share `web/` and `site/`).
- **Each helper builds its own documents**: `md2tex.py`, `buildtex.py`,
  the log's missing-character count, a look at the rendered pages.
- **The report** per document: kinds of change with counts, uncertain
  readings with page numbers, new flags, build result. Short.

Helpers can be cut off (by a usage limit, for example). Their edits stay on
disk, so a resumed helper should re-read its files as they are and finish
the brief rather than start over.

**Without parallel helpers** (an agent that has no subagents), do the same
work in order. Write the brief anyway. Take one or two documents at a time,
build and report on each before starting the next, and begin each from the
brief and the files as they are on disk rather than from memory of the
previous ones. A long batch can span several sessions this way, with the
brief and the per-document reports as the hand-off, and git as the record
of which documents are done.

## 5. Verify the whole batch yourself

- Rebuild every document: all checks except check 11 must pass, no missing
  characters, and compare any too-wide warnings with a build of the
  previous version (a table that already overflowed is worth reporting,
  but it is not a regression).
- Run `notation_lint.py` over the batch.
- Build the website in a scratch copy with every document set to
  `checked: true`, and run `checkweb.py`. It fails on any formula MathJax
  renders as an error, which the PDF build cannot see (for example `\tag`
  in an equation Sphinx wraps in `split`; `mkweb.py` already handles that
  case).
- Render a sample of pages with the most complex changes (matrices,
  braces, long aligned equations) and look at them.

## 6. Report to the author

One paragraph of what changed across the batch, then the list that needs
their eyes: every new flag in the closing notes (the original as written,
what it probably means), every uncertain reading with its page, and any
pre-existing problem noticed on the way (a table running off the page).
Commit the batch as one commit, after the mechanical-only commit if there
was one, with the author's identity.
