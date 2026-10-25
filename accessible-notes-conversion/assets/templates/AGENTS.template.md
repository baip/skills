# Instructions for coding agents

This project turns the {{SHORT}} course notes into accessible form. Each
document is one Markdown file that builds a tagged PDF and a page of the
website. Codex and OpenCode read this file by themselves, and Claude Code
reads it through `CLAUDE.md`.

## Read first

1. `CONVENTIONS.md`: how the source is written and why. Where it differs
   from the skill, it wins.
2. `BUILD.md`: the installs, the builds, the checks and what each check
   means. Its section "Running under other coding agents" lists what your
   agent must be allowed to do.
3. The `accessible-notes-conversion` skill's `SKILL.md`, and the reference
   it names for the task at hand: `references/transcribing.md` before
   transcribing, `references/figures.md` before drawing or changing a
   figure, `references/review-and-delivery.md` for a round of review, and
   `references/notation-pass.md` for one revision across many documents.
   The skill is wherever your agent installed it. `<skill>` below and in
   the skill means that folder.
4. The recent commits. The author often revises documents by hand, and
   those diffs are the current house style.

## Standing rules

- The Markdown is the only source. Never edit a generated `.tex`, `.pdf`,
  `web/` or `site/`.
- The build scripts at the top of the project, `scripts/figures_audit.py`
  and `scripts/figures/figlib.py` come from the skill and are not edited
  here. Fix them in the skill, then run
  `python3 <skill>/scripts/init_project.py . --update-toolkit`.
- Read the originals as page images (`<skill>/scripts/render_pages.py`),
  zooming into anything small. Extracted text leaves out every handwritten
  line. If you cannot view image files, say so and stop rather than
  transcribe from extracted text.
- Transcribe errors in the original as written and flag them in the closing
  notes. Correct one only when the author says to.
- Add a new document to `contents.yaml` with `checked: false`. Only the
  author sets it to `true`.
- Run `python3 <skill>/scripts/notation_lint.py <doc>.md` before building.
  Fix its errors, and check its warnings against the original.
- Look at the output: a contact sheet of every changed figure, each beside
  its original (`<skill>/scripts/contact_sheet.py --original`), and the
  rendered PDF pages that hold changed equations, tables and figures. Give
  the author the contact sheet, as a file if your interface can send one,
  otherwise its path.
- Run `git status` before editing. Never fold the author's uncommitted
  changes into your commit, and stage the paths you changed by name.
- Commit with the author's identity and a message listing the items. Never
  push unless the author asks.
- Instructions the author gives in one round ("do not build", "I will
  push") hold for later rounds until lifted.
