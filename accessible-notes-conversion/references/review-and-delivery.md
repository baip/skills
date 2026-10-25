# Review rounds and delivery

After the first conversion, most of the work is rounds of review: the author
reads the PDF or the website against the original and sends a list of
changes ("Figure 5: the labels overlap", "the dots do not show in the PDF",
"use the original's notation here"). This file is how to handle a round.

## Handling a round

1. **Start from the author's current file.** The author may have edited the
   Markdown, rebased, or committed since the last round. Re-read the file
   (or pull the latest commit) before changing anything, and build on it.
   Never overwrite their edits with an older copy.
2. **Cross-check the original** for every item that concerns content:
   zoom into the page the item refers to. The author's note is usually a
   pointer to a mismatch with the original.
3. **Do what each item says, and only that.** Keep a list, and address every
   item. If an item is ambiguous or seems self-contradictory (the same
   direction written twice, say), pick the reading that matches the
   original and say which you chose.
4. **Answer questions directly.** A round often mixes requests with
   questions ("what is `\,` for?", "should captions be justified?"). Answer
   briefly and, where there is a choice to make, recommend one and wait for
   the author's decision before applying it across the project.
5. **Look at the result.** Every changed figure goes on a contact sheet
   (`scripts/contact_sheet.py`) beside its original (`--original`), and you
   compare the two. Every change affecting the
   PDF (a glyph, a table, float placement, captions) is checked in the built
   PDF, by rendering the page, unless the author has said not to build.
6. **Report briefly.** One line per item: what changed. Give the author
   the contact sheet, as a file if you can send one, otherwise its path. Mention anything you could not do, anything you chose on the
   author's behalf, and anything you noticed that is outside the round but
   worth their attention. Do not recap the whole document.

## When the author says "do not build"

Honour it for their machine and their folder: do not write `.tex`, `.pdf`
or `site/` there. You can still verify in a scratch copy elsewhere if you have
one (a cloud workspace, a temporary clone), and say that you did.

## When the author has revised documents themselves

An author working through the notes often revises a few documents by hand
and then asks for the rest to match. Their commits are the specification:
read the diff of each and copy what they did, including what they removed
(and what they kept). `references/notation-pass.md` describes doing that
across many documents at once.

The author may also have edits in progress that are not committed. Check
`git status` before touching a file, and never fold their uncommitted
changes into your commit. If your change has to move or rewrite such a
file (a reorganization, say), back the file up, stash it, apply your
commit, pop the stash, and confirm their edits survived.

## Reorganizing the repository

When the author asks for a new layout, move with `git mv` so history
follows the files, update every path the scripts compute, the figure links
in the moved Markdown, `contents.yaml`, `.gitignore` and the notes, and
prove nothing changed in the output: regenerate the LaTeX of every document
before and after and compare (only the header line should differ), rebuild
the website and compare its pages, and rerun every drawing script to check
the SVGs come out byte for byte. Keep published web addresses stable.

## Fixes that apply to the whole project

Some corrections are about a convention, not a single spot (caption
alignment, a glyph missing from the font, a notation rule). Fix the
convention in the toolkit or class, apply it to every document, and add a
line to the project's `CONVENTIONS.md` so the next document gets it right
the first time.

## Version control

If the project is a git repository:

- Commit each round as one commit, or one per document, with a message that
  lists the items addressed. Use the author's identity for authorship, and
  add any attribution lines your environment requires.
- **Do not push unless the author asks.** Many authors review and push
  themselves. If a hook or reminder asks you to push, report the number of
  unpushed commits instead.
- Do not rewrite history the author has pushed.

## Working on the author's computer through a bridge

When the project folder is on the author's computer and you reach it
through a remote bridge or sync tool:

- Edit text files in place on that machine where you can. Moving files back
  and forth creates two copies that drift.
- Regenerate SVG figures by running the drawing script on the author's
  machine, rather than copying SVGs across. Some transfer tools rewrite
  files they carry (for instance by adding provenance metadata to images),
  which makes the committed figure differ from what the script draws.
  Compare checksums if you do copy.
- Git lock files left by an interrupted command (`.git/index.lock`,
  `.git/HEAD.lock`) block the next commit. Removing them may need an explicit
  permission from the author.
- To keep a working clone of your own in step with theirs, bundle their new
  commits (`git bundle create sync.bundle <your-head>..HEAD` on their
  machine), copy the bundle across and fetch from it. The reverse works the
  same way for delivering your commits.
- The link can drop in the middle of a round. Commit what you have in your
  own clone and hand the author a bundle they can pull
  (`git pull <file>.bundle main`), and check on your next turn whether they
  already have.

## Publishing

When the author marks a document `checked: true`:

1. `python3 mkweb.py && python3 checkweb.py`
2. Copy `site/` to the host.
3. `python3 package.py` for an archive of the whole project, if wanted.

Before the first public release, recommend an independent check: PAC 2024 on
a sample of PDFs and a WCAG audit (axe, WAVE, or a screen-reader pass) on the
site. The scripted checks are necessary, not sufficient.
