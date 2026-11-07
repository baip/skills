---
name: project-llm-wiki
description: Set up and run an LLM-maintained wiki of a researcher's own project documents (proposals, reports, presentations, papers, reviews received) kept in Word, PowerPoint, Excel, LaTeX, PDF and other formats in a local or cloud-synced folder, read-only, so that future proposals and reports can reuse what was proposed, done, reported and learned. Obsidian-style pages for documents, projects, topics, concepts and entities, with content fingerprints that detect edited or moved files, claim status (proposed vs reported vs published), verbatim reuse blocks of the user's own text, a review queue, lint and claim audits. Use whenever someone wants to turn a folder of their grant proposals, progress reports or slides into a knowledge base, a "second brain" for proposal writing, a Karpathy-style LLM wiki or Obsidian vault of their own work, or wants help drafting a proposal or report from past ones kept in such a wiki, or to upgrade the tools of an existing one.
compatibility: Python 3.9+ (standard library only) on macOS, Linux or Windows; poppler (pdftoppm, pdfinfo) to view pages; pandoc recommended for Word text; to render Word/PowerPoint files, LibreOffice (any system, preferred) or Microsoft Word/PowerPoint (macOS or Windows); git and Obsidian optional. Works with Claude Code, Codex, OpenCode and other agents that read AGENTS.md and can view local images.
---

# Project-document LLM wiki

The user keeps their own documents (proposals, annual and final reports, talks, papers, reviews and panel summaries
they received, plans, budgets) in a folder tree, the **raw root**. The agent reads the documents the user names and
writes a wiki that compiles them into linked Markdown pages: one page per document, one per project (a funding effort
with its proposals, award, reports and reviews), and pages for research topics, concepts and entities (sponsors,
programs, facilities, codes). The wiki then supports writing: what was proposed and what was achieved, what reviewers
said, and reusable passages of the user's own text with their provenance. The raw root stays the single source of
truth and is never modified.

This skill does two things:

1. **Instantiate** a new wiki: a short interview, then `scripts/init_wiki.py` writes the schema (`AGENTS.md`), the
   tools, the bookkeeping files and the folder layout, and checks them.
2. **Hand over** to the wiki's own `AGENTS.md`, which governs every later session (ingest, query and writing support,
   lint, audit). After setup the skill stays the home of the tools: a tool is changed in the skill's template first
   and copied into the wiki with `init_wiki.py --upgrade-tools DEST`. The design is explained in
   `references/design-notes.md`.

## Before you start

Check, and fix with the user, what setup depends on:

- **Python 3.9+** (`python3`, or `py -3` on Windows).
- **Viewing pages.** The reading rule is to look at pages as laid out, not only extracted text. `docs.py render`
  turns pages into PNG files with poppler (`pdftoppm`, `pdfinfo`), and the agent views them as images. Word,
  PowerPoint and Excel files are first converted to PDF by **LibreOffice** when installed (any system, the only option
  on Linux), else by **Microsoft Word or PowerPoint** (macOS by AppleScript, Windows by PowerShell, always on a temp
  copy). Suggest installing LibreOffice if it is absent; Office alone still works. pandoc gives the best Word
  text. After setup, `python3 -I tools/docs.py status` in the wiki lists what was found. Without a converter, a Word
  or PowerPoint file can still be read as text plus its embedded images (`read_mode: source`).
- **This skill is installed**, not run from a temporary copy: at `~/.claude/skills/project-llm-wiki` (a symlink to a
  clone works), or in any folder named by `PROJECT_LLM_WIKI_SKILL` (set it in the shell profile; on Windows, where
  links need Developer Mode, use the variable). For Codex and OpenCode link `~/.agents/skills/project-llm-wiki` (older Codex: `~/.codex/skills/`) to the same folder.
  `init_wiki.py` refuses to run from anywhere else.
- **The agent may do what the wiki needs**: read the raw root, write in the wiki folder, the temp directory, the batch
  cache `~/.cache/llm-wiki`, the git directory and this skill's folder, and run `python3`, `git`, poppler, pandoc and a
  converter. The new wiki's `tools/README.md` ("Running under other coding agents and systems") gives the settings for
  Codex, OpenCode and others.

## Setup interview

Ask only what you cannot infer, in one short round; if you cannot ask, infer and state each assumption:

| Question | Why it matters | Where it goes |
|---|---|---|
| Where should the wiki live? | A new or empty folder, outside the raw root. Obsidian is optional. | `DEST` |
| Which folder holds the documents? | The raw root, read only; every source page records paths relative to it. | `--raw-root` |
| Who reads it, in one sentence? (field, role, sponsors they write for) | The writing-style rule. | `--audience` |
| Is the wiki folder synced (Google Drive, Dropbox, OneDrive, iCloud)? Should it be a branch of an existing repository? | Sync services corrupt `.git` folders. | `--git separate[:PATH]`, `worktree:REPO[:BRANCH]`, `inside` or `none` |
| Which documents come first? | The first ingest. The user chooses what is ingested; never sweep a folder unasked. | the `next:` line |

Then run, from the installed skill's folder:

```
python3 scripts/init_wiki.py DEST --audience "SENTENCE" --raw-root PATH
                             --git inside|separate[:PATH]|worktree:REPO[:BRANCH]|none [--trailer "LINE"]
```

If your host asks for attribution lines on commits (for example a `Co-Authored-By:` line), pass each as `--trailer`.
The script checks every input before writing anything, refuses a non-empty `DEST` or one inside the raw root, fills
the templates, writes `tools/config.json` (the raw root), runs the bundled tool tests and the strict linter on the
empty wiki, and makes the initial commit. If setup fails partway, it removes what it wrote (including a new worktree
and branch). Report what it printed.

**If the user asked only for setup**, stop here: report the location, the raw root, the git arrangement, the
converters `docs.py status` found, and the next step (name a project folder or a few documents for a guided ingest).

## First session in the new wiki

Read the new `AGENTS.md` in full: from here on it is the operating manual. Then, with the user:

1. `python3 -I tools/docs.py ls "<folder the user named>"` to list its documents (renditions grouped, states shown).
   Flag anything that looks confidential to others (reviews the user wrote of others' work, others' proposals,
   student records): it is not ingested unless the user names it and confirms (AGENTS.md §2.2).
2. **Ask the user to pick the first document**, offering three to five from the listing with one line each on why
   (a funded proposal with its reports, a recent report, a proposal with its panel summary). Pick one yourself only if
   the user has left the choice to you.
3. **Ingest it in guided mode** (AGENTS.md §8.2): read every page, give 3–6 takeaways and what looks reusable, ask
   what to emphasize, then write the source page, stamp it, and create its project page. In delegated mode, skip the
   discussion and say so under `## User notes`.
4. Finish: `catalog.py --apply`, append to `log.md`, `wikilint.py --strict`, and one commit of the paths you changed.

Suggest what comes next (the rest of that project's documents, then other projects, possibly as a batch per §8.2b),
and mention that a claim audit (§8.5) is the only check that tests the knowledge rather than the structure.

## Changing tools and upgrading a wiki

Tools are never edited inside a wiki. To fix or extend one, edit it in this skill's `assets/wiki-template/tools/`, add a
test to `test_tools.py` there and run `python3 -I assets/wiki-template/tools/test_tools.py`; commit in the skill's
repository. Then `python3 scripts/init_wiki.py --upgrade-tools DEST` replaces only the Python tools in a wiki, runs the
tests and the linter there (errors only), appends a `fix` entry to `log.md` and commits the tools and the log. It never
touches pages, `AGENTS.md` or `tools/README.md`, but prints the template's README rows for the tools that changed:
show those to the user. Before upgrading, run `git status`: uncommitted changes of unknown authorship are the user's
to resolve first.

## What not to do

- Do not write, move, rename or delete anything under the raw root, and do not open its files in an application
  that could save them (the tools give Office a temp copy).
- Do not ingest documents the user did not name or approve, and never material confidential to others without the
  user's explicit confirmation for that file.
- Do not copy files, figures or extracted text into the wiki. Only the user's own text, in `[!reuse]` blocks.
- Do not present proposed work as done, in the wiki or in a draft written from it.
- Do not instantiate into a folder that already has content, and do not overwrite an existing wiki's schema.

## Files

- `scripts/init_wiki.py`: create a wiki, or upgrade its tools.
- `assets/wiki-template/`: the schema, bookkeeping files and tools that a new wiki starts from. `{{…}}` placeholders
  are filled by the script.
- `references/design-notes.md`: why the schema looks the way it does, and how it differs from the Zotero-backed wiki
  it was adapted from. Read it when the user asks why a rule exists or wants to change one.
