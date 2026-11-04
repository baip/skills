# Implementation guide (tools and machine-specific details)

`AGENTS.md` holds the durable policy. This file holds the *how* for this machine and agent setup, which may change
without changing the policy. Set up {{DATE}} ({{ENVIRONMENT}}). Raw root: `{{RAW_ROOT}}` (`tools/config.json`;
`$PROJECT_WIKI_RAW_ROOT` overrides it, e.g. on another machine where the same folder is mounted elsewhere).

## Tools (Python stdlib only; run from the wiki root as `python3 -I tools/<tool> …`)

On Windows, use `py -3 -I tools/<tool> …` (or `python`) wherever this file says `python3`.

| Tool | What it does |
|---|---|
| `docs.py` | Read-only client for the raw root. It lists, inspects, extracts and renders documents, always writing to a temp directory outside the wiki and the raw root. Its only wiki writes are `stamp` and the review items that `stamp` and `changed --queue` add to `pending.md` |
| `wikilint.py [--strict] [--since REV]` | Structural and metadata validation (`--since REV` lists every error but only counts warnings, with details for pages changed since REV: the form to use during work). It exits 1 on errors; `--strict` (the completion gate) also fails on warnings and open `pending.md` items. Its `tools` warning compares `tools/*.py` with the installed skill (`$PROJECT_LLM_WIKI_SKILL`, else `~/.claude/skills/project-llm-wiki`) |
| `review.py` | Wiki-side review queue: `touched PAGE…` and `since REV --queue` queue the dependents of pages whose content changed (`since` lists *additive* edits, which only insert lines, without propagating them, except inserted `[!contradiction]`/`[!stale]` callouts); `done PAGE… --outcome corrected\|unchanged\|not-affected --basis TEXT [--cause ID]` resolves items into the ledger `reviewed.md`, and a resolved (page, cause) is never re-queued; `restated PAGE --phrase TEXT…` queues every other page whose body still contains a phrase of a corrected claim; `list [--context]` groups open items by page, and with `--context` prints the lines of each page that cite the changed page, which a review reads first |
| `catalog.py [--apply] \| --nav` | Generated bookkeeping: re-derives each page's `sources:` from its body, and writes every `index.md` line below the preamble from the pages. `--nav` prints the index preamble with the Topics and Projects sections, the session-start read. Lint warns (`catalog`) while anything is out of date |
| `split.py PARENT --section HEADING --to CHILD --summary TEXT [--title T] [--apply]` | Splits a page over the 40,000-byte limit: moves one `##`–`####` section verbatim to a new child page (for a source, a part note `PARENT--<slug>` with `type: source-part`) and leaves the heading, the summary line and a pointer in the parent. It refuses if protected text would change. Dry run by default. Pass the parent to `review.py since --neutral`, then run `catalog.py --apply` |
| `relink.py` | Converts `↗` file links into wikilinks once the document has a source page. It skips `[!user]`, `[!reuse]` and code, and refuses to write if they would change. Dry run by default; `--apply` writes |
| `search.py TERM… [--phrase TEXT]… [--type T] [--folder PREFIX] [--kind DOC_KIND] [--depth D] [-n 15]` | Ranked keyword search over the pages (BM25, with title, aliases, first heading and filename also ranked on their own, and tags, authors, sponsor, program and headings counted extra). Words are lowercased, split at hyphens and plural-folded; no other stemming and no embeddings, so try synonyms. Read-only |
| `wikimeta.py` | Shared module: a strict frontmatter parser, protected spans, page loading, derived source states, evidence links and dependents, file locks (fcntl or msvcrt), the `pending.md` queue and the `reviewed.md` ledger |
| `test_tools.py` | Regression tests, no network, using a temporary raw root and wiki: parser, validation, protected text, Word/PowerPoint/Excel/LaTeX extraction, converter order, fingerprints, and **end-to-end update sequences**: edit → detect → queue → stamp → review → strict gate, a moved and a renamed file, an incomplete baseline, concurrent queue writers. Run after any tool change |

### `docs.py` commands

| Command | Use |
|---|---|
| `status` | Raw root reachable? Which converters are available (pandoc, poppler, textutil, and for Office files LibreOffice or Word/PowerPoint)? Run at the start of any session that reads documents |
| `ls PATH [--recursive] [--all]` | Documents under a folder, renditions grouped (same folder and name, other extension), newest date, size, and state: `[ ]` none, `[m]` metadata, `[r]` read, `[x]` integrated. Office lock files (`~$…`) and system files are skipped; `--all` also lists images, data and archives |
| `info FILE` | Size, dates, hash (the suggested `doc_id`), document properties (Word/PowerPoint title, author, pages or slides, and hidden PowerPoint slides; PDF pages; LaTeX title and whether it is a main file), renditions, the `file://` URL, and the page that already covers it |
| `text FILE` | Text to the temp directory, one `PATH<TAB>what` line per output: Word via pandoc (tables and equations kept, images extracted), PowerPoint slide text and speaker notes in presentation order with images extracted (SVG sources and notes-page images included) and embedded or linked video and audio listed per slide, not copied, Excel cell values per sheet, LaTeX flattened (`\input`/`\include` expanded) with figure files and bibliographies listed, PDF text layer, `.doc`/`.rtf`/`.odt` via textutil on macOS or the PDF conversion elsewhere. View every listed image |
| `render FILE [--pages 3-7] [--dpi 150] [--skip-hidden]` | Pages as PNG files in the temp directory, one `PAGE<TAB>PATH` line each; view them as images. Office files are converted to PDF first (Converters, below; the PDF is cached by content hash). Hidden PowerPoint slides are rendered by default, from a temp copy with the hidden flags cleared, so page N is slide N; `--skip-hidden` omits them |
| `clean` | Deletes the temp directory (rendered pages, text, media, converted PDFs); run it at the end of an interaction |
| `fingerprint FILE…` | `f1 <hash> …`: the first 8 hex digits of each file's SHA-256 |
| `stamp PAGE…` / `stamp ALL` | Write `doc_fingerprint` and `doc_checked` (atomic write). It first compares with the previous baseline; if content changed, or the baseline was incomplete, it queues the evidence dependents in `pending.md`, under a lock. A page is named by its filename or `doc_id`. It refuses while a file is missing |
| `changed [--queue]` | Pages whose files changed (CHANGED: re-read), disappeared (MISSING: moved, renamed or deleted), were never stamped, or have an INCOMPLETE baseline. `--queue` appends review items: a content change queues the source and its dependents, a missing file queues the source page only |
| `locate PAGE [--under PATH] [--deep]` | Finds a page's missing files by their stamped hashes: the same file name anywhere under PATH (default the raw root), and with `--deep` every file with the same extension |

## Changing a tool (AGENTS.md §12)

1. Edit the tool in `{{SKILL_DIR}}/assets/wiki-template/tools/`, add a test to `test_tools.py` there, and run
   `python3 -I {{SKILL_DIR}}/assets/wiki-template/tools/test_tools.py`.
2. If the skill folder is a git clone (or a link to one), commit the change there.
3. From the wiki root, `python3 {{SKILL_DIR}}/scripts/init_wiki.py --upgrade-tools . [--trailer "LINE"]`: it replaces the
   changed tools, runs the tests and the linter (errors only), appends a `fix` entry to `log.md` and commits the tools and
   the log. It prints the template's rows of this README that differ from yours; update the rows that apply.

## Provenance and review mechanics (AGENTS.md §4)

**Fingerprints.**
- Format `f1 <hash> <hash> …`: one hash per entry of `files:`, in order, each the first 8 hex digits of the file's
  SHA-256. Content only: a file touched by a sync service or copied with a new date is unchanged, and a file re-saved
  by Word without edits usually is not (Word rewrites its package), which costs a re-check, never a missed change.
- **Complete or nothing**: a malformed fingerprint, or one whose hash count differs from `files:`, certifies nothing:
  lint rejects it, `changed` reports it as INCOMPLETE, and stamping over it queues the dependents.
- **Order-free comparison**: the stored and current hashes are compared as sets, so correcting `files:` after a move
  or reordering renditions never looks like a content change.
- `stamp` queues the dependents **before** it replaces the baseline whenever content changed, so an interrupted update
  cannot lose a review.

**Dependencies.** `wikimeta.evidence_links` gives the pages a body uses as evidence: links outside `## Connections`,
`## Related` and `## Sources`, minus pointer runs introduced by `→`, "See" or "cf." unless a locator (`§`, `Fig.`,
`Table`, `eq`, `p.`, `slide`, `sheet`, `SI`, `App.`) follows the link. `propagate` chains through source pages only
when the changed page is itself a source.

**Queue (`pending.md`).** Items are `- [ ] [[page]] note (cause: <id>)`; causes are `file:<page>@<fp-hash>` (or
`file:<page>@missing-<hash>`) or `wiki:<page>@<body-hash>` (the body hash excludes frontmatter, so frontmatter-only
edits never queue). One item per (page, cause). Any other checkbox line, or a ticked item left in place, is a lint
error. Hand-written items (without a cause) are allowed for work that must not be forgotten.

**Ledger (`reviewed.md`).** `review.py done` writes `- DATE OUTCOME (cause: ID) [[page]], … — basis`, then removes the
items. A (page, cause) in the ledger is never queued again.

## Concurrency and file safety

- `pending.md` and `reviewed.md` updates take exclusive locks (`fcntl` on macOS and Linux, `msvcrt` on Windows); the
  lock file is in the system temp directory, keyed by path, not in the (possibly cloud-synced) wiki. Files are then
  replaced atomically (temp file plus `os.replace`), in UTF-8 with LF line endings on every system.
- Locks only coordinate processes on **one machine**. Do not run tools against the same wiki from two computers at once.

## Reading documents (AGENTS.md §7)

- **Rendering.** `docs.py render FILE --pages 1-10` writes PNG files to the temp directory (`$TMPDIR/project-wiki/`
  or the system temp folder) and prints one `PAGE<TAB>PATH` line per page; view each with the agent's image viewer.
  150 dpi keeps subscripts and table digits legible; use `--dpi 200` for small print. Render 10–20 pages at a time
  and view every page of a batch before the next. Claude Code's `Read` can also open a PDF directly with page ranges;
  either way counts as `rendered`.
- **Converters** (Word, PowerPoint and Excel files to PDF, then pages), tried in this order:
  1. **LibreOffice** (`soffice --headless`, with its own profile in the temp directory), whenever it is installed, on
     any system, and the only converter on Linux and WSL. No app windows or permission prompts. Layout may differ
     slightly from Office (fonts, line breaks).
  2. **Microsoft Word or PowerPoint**, for their own formats, when installed: on macOS through AppleScript
     (`osascript`), on Windows through PowerShell COM automation. Layout matches what the user sees. Office works on a
     temp copy, so no `~$` lock file lands in the raw root, closes it without saving, and quits if it was not
     running. The first run may ask the user to allow the terminal or agent to control Word or PowerPoint (macOS
     System Settings → Privacy & Security → Automation).
  `$PROJECT_WIKI_CONVERTER=office` puts Office first, for a document whose locators depend on Office's exact
  layout. If no converter is
  available, `docs.py` says so: install LibreOffice (`brew install --cask libreoffice`, `apt install libreoffice`,
  `winget install TheDocumentFoundation.LibreOffice`), or read the PDF rendition, or read the text and the embedded
  images (`read_mode: source`).
- **LaTeX** is never compiled by the wiki. Read the flattened source and view the figure files `docs.py text` lists;
  when the user's compiled PDF is in the folder, it may be rendered instead (`rendered`).
- Text extraction needs pandoc for the best Word text (`brew install pandoc`, `apt install pandoc`, `winget install
  JohnMacFarlane.Pandoc`); without it, `docs.py` falls back to plain paragraphs and says so. Rendering needs poppler
  (`pdftoppm`, `pdfinfo`): `brew install poppler`, `apt install poppler-utils`, or on Windows `conda install -c
  conda-forge poppler` or `scoop install poppler`.
- An agent that cannot view images reads text only and records `read_mode: text-index` (figures unseen). Never record
  `rendered` for a page that was not viewed as an image.
- Files in a cloud drive's online-only mode are downloaded when read; a very large folder listing can take a while the
  first time.
- The original is read in place and never copied into the wiki. Never filter or truncate extracted text.

## Batch runs (AGENTS.md §8.2b)

- **Inventory**: `docs.py ls` of the folders the user named; present the list (with any file that looks confidential
  to others flagged, AGENTS.md §2.2) and ingest what the user approves. Group renditions into one document each.
  Items in *read* or *metadata* are included for integration, not skipped.
- **Readers** stamp only the pages they create (no baseline, so nothing is queued); re-stamping existing pages belongs
  to the main agent. They link only to existing pages or to the slugs the main agent fixes in advance. Start a fresh
  reader for each document and let it end after its page and brief; after a usage-limit stop, start new readers and
  let them check which pages exist.
- **Integrators** own about 10 pages each, run in waves within any cap on subagents, and treat source pages as the
  authority. Write each integrator's slice of the briefs to its own file in the cache folder.
- **One phase per orchestrator session**: commit the checkpoint, write the next phase's instructions to the batch state
  file (phase, start revision, items, integrator groups, cache paths), and stop, telling the user to start a new
  session with "Continue ingestion". With no batch folder under `~/.cache/project-wiki/`, nothing is pending.
  To run phases back to back without anyone at the keyboard, run `python3
  ~/.claude/skills/project-llm-wiki/scripts/continue_ingestion.py <wiki> --agent codex|claude` in a terminal (not from
  an agent session). It starts a fresh headless session per phase with that prompt and goes on while each phase commits.
  After a usage limit it waits for the reset (stopping if that is more than 6 hours away) and resumes the same session.
  It stops on anything else: no commit, uncommitted changes, an error, `--max-phases`, or `--stop`, which ends it after
  the current phase.
- **A small orchestrator context** (AGENTS.md §8.2b). These rules hold for any agent, and only the mechanics differ.
  - Read file lists, `git diff --stat` and one-line reports, never whole pages, diffs or check output. Reviewers
    and a checks runner validate the phase (next item) and return one line each.
  - Wake only when a subagent finishes. Use the agent's completion notice if it has one. Otherwise wait with the
    longest timeout its wait command allows, never in short repeated checks: each wake-up sends the orchestrator's
    whole context again.
  - Record batch size and subagents at once in the batch state file. An orchestrator's cost per phase is roughly
    fixed, so larger batches and more subagents at once spread it over more documents.
- **Bounded validation** (AGENTS.md §8.2b, rule added 2026-11-04). Give each validator `tools/validator-brief.md` plus
  its role, files, start revision and cache folder, in a fresh context (in Codex, a new agent rather than a fork of the
  orchestrator).
  - Reviewers: about 3 documents each in the reading phase (their source pages and reader reports), one integrator group
    each in integration (`git diff <start> -- <its pages>` and the source-page sections its claims cite). They fix clear
    errors, report judgment calls and run no checks.
  - Checks runner: the orchestrator itself or a small fresh subagent. It writes each check's output to `<cache>/checks/`
    and reads only the last lines. A failure goes to a fresh subagent with only the failing items.
  - Measured before the change (chatgpt wiki, batches 199–210, 31 validators): 0.4–7.6M tokens each, 3.6M on average at
    a mean context of 108k. Each read 400–600 kB of notes, records, reports or diffs, then ran the build, checks, tests
    and search-index refresh on top, so half or more of its calls ran above 120k. Seven started as forks of the
    orchestrator at 63–82k. Split reviews of 13–17 calls cost 0.6–0.9M.
- **Cache folder**: `~/.cache/project-wiki/<wiki>-<batch>/` (on Windows, `%LOCALAPPDATA%\project-wiki\…`), outside
  the wiki and the raw root. Subagents write full reports to `<cache>/reports/` and return one line. Delete the folder
  when the batch is complete and committed.
- **Without subagents**, run the same phases in one session, in order: read and write every source page first, one
  document at a time, saving each integration brief to the cache folder; then integrate one page set at a time; then
  write the project and topic synthesis, index and log.
- Run `relink.py --apply` only after all reading has finished.

## Semantic search with qmd (optional; AGENTS.md §8.3)

[qmd](https://github.com/tobi/qmd) adds keyword plus vector search with reranking, all on this machine. It indexes the
page folders only, never the raw root or the bookkeeping files. Without it, use `tools/search.py`.

- **Install** (once per machine): `npm install -g @tobilu/qmd` (Node 22+), and on macOS `brew install sqlite`.
- **Where the index lives.** `.qmd/` at the wiki root (git-ignored). In a cloud-synced folder, make `.qmd` a link to a
  folder outside the synced tree first.
- **Set up** (from the wiki root; NAME is a short name for this wiki):

  ```sh
  mkdir -p ~/.cache/qmd/projects/NAME && ln -s ~/.cache/qmd/projects/NAME .qmd   # cloud-synced folder only
  qmd init
  qmd collection add . --name NAME --mask "{sources,projects,concepts,entities,topics,analyses}/*.md"
  qmd context add qmd://NAME "<one sentence on what this wiki covers>"
  qmd embed
  ```

- **Before each query session**: `qmd update && qmd embed`. **Query** with `qmd query $'intent: …\nlex: …\nvec: …'`,
  and `qmd search "<exact words>"` for names. Treat results as leads and cite wiki pages, not qmd docids.

## Running under other coding agents and systems

Every rule is in `AGENTS.md`, which Codex, OpenCode and most other agents load by themselves and Claude Code loads
through `CLAUDE.md`. Agents without that convention (or a custom harness) should be told to read `AGENTS.md` first.
The tools are plain `python3 -I tools/…` commands, so what differs between agents is only what they may do. The wiki
needs:

1. reads of the raw root (`{{RAW_ROOT}}`), which is outside this folder;
2. writes to this folder, the system temp directory, `~/.cache/project-wiki`, the git directory if it is outside this
   folder (see Revision history), and the skill folder (`{{SKILL_DIR}}`) when a tool changes (AGENTS.md §12);
3. running `python3`, `git`, poppler, pandoc, and a converter: `osascript` (macOS Office), `powershell` (Windows
   Office) or `soffice`;
4. viewing local image files (rendered pages, extracted figures).

No network access is needed, except for qmd's first model download.

- **Claude Code**: works as is; approve the prompts for these commands, or allow them in its settings.
- **Codex**: its default `workspace-write` sandbox blocks writes outside the folder it was started in and may block
  reading other folders and controlling other apps. Start it from this folder and add the paths in
  `~/.codex/config.toml` (key names as of 2026; check the Codex docs for yours):

  ```toml
  sandbox_mode = "workspace-write"
  [sandbox_workspace_write]
  writable_roots = ["<git directory, if outside this folder>", "<skill folder, resolved>", "<home>/.cache/project-wiki"]
  ```

  LibreOffice is tried first, so a sandbox that refuses Word or PowerPoint automation needs nothing extra when
  LibreOffice is installed.
- **OpenCode, Hermes, OpenClaw and others**: allow `python3 -I tools/*`, `git`, the converters and poppler in their
  permission settings, and give the agent read access to the raw root. The skill is found at
  `$PROJECT_LLM_WIKI_SKILL`, else `~/.claude/skills/project-llm-wiki`; link the agent's own skills folder (for Codex and
  OpenCode `~/.agents/skills/project-llm-wiki`, older Codex `~/.codex/skills/`) to the same copy.
- **Windows**: the tools run natively (Python 3.9+ from python.org or `winget install Python.Python.3.12`). Use
  forward slashes in `files:`; `docs.py` converts. Symbolic links need Developer Mode, so set
  `PROJECT_LLM_WIKI_SKILL` to the skill folder instead of linking it.
- **Linux and WSL**: LibreOffice is the converter (Office automation needs Windows or macOS).

## Revision history (git)

{{GIT_DETAILS}}
- **Staging:** stage the paths you changed explicitly. Leave pre-existing changes alone until the user confirms who
  made them (AGENTS.md §2.11).
- `.gitignore` excludes OS and cloud-sync temp files, `__pycache__/`, and Obsidian UI state; `.gitattributes` keeps
  LF line endings on every system.
- **Remote:** agents commit locally and push only when asked.

## Schema details

They are binding. Each subsection is referenced from the AGENTS.md rule it details.

### Review rules (AGENTS.md §4)

- A changed **source** queues its direct dependents, and through source pages that quote it, theirs; a changed
  **project, concept, entity, topic or analysis** page queues only its direct dependents; a reviewed page propagates
  further only if the review changed it (`review.py touched` or `since`).
- A **claim-neutral** edit (a locator, a typo, wording that keeps the meaning) is not propagated: pass it to
  `review.py since --neutral` and list it in the log. An **additive** edit (whole lines inserted) is not propagated,
  except an inserted `[!contradiction]` or `[!stale]` callout; an insertion that narrows an existing claim must also
  edit that claim, which propagates.
- **A corrected claim is also searched for by its wording**: `review.py restated PAGE --phrase "…"` with 2–3
  distinctive phrases of the *old* wording.
- Resolve each item with an outcome and its basis (`review.py done`): *corrected*, *unchanged* or *not-affected*.
  Read the citing sentences first (`review.py list --context`) and open the whole dependent page only when they use
  the changed content.

### Page templates (AGENTS.md §5)

Frontmatter uses the YAML subset `tools/wikimeta.py` parses: `key: value` lines with plain or quoted scalars, flow
lists `[a, "b, c"]` and flow maps `{K: "v"}`. Quote any list element that contains a comma or a space. Required fields
are marked *. Fields marked *generated* are written by tools, never by hand.

#### Source page — `sources/<slug>.md`

```yaml
---
type: source*
title: "…"*                  # the document's own title
summary: "…"*                # one line, about 200 characters: the page's index entry (§9)
authors: ["Bai, P.", "Doe, A."]*        # as credited, quoted; first 5, then "et al."
corporate_authors: []        # optional exact organization names also listed in authors
author_status: uncredited    # optional, only when the document itself credits no author
year: 2024*                  # integer year, or undated when no date can be verified
date: "2024-08"              # optional: YYYY, YYYY-MM or YYYY-MM-DD (submission, report or talk date)
doc_kind: report*            # proposal | proposal-section | pre-proposal | white-paper | report | presentation | paper |
                             # thesis | review | solicitation | correspondence | plan | other
my_role: PI                  # PI | co-PI | senior-personnel | lead-author | co-author | contributor | reviewer | recipient | none
project: nsf-career-zeolite-ml   # the project page, if any
doc_id: "3fa94c1e"*          # content hash of the main file at first ingest (docs.py info); quoted; never changes
files: ["Proposals/NSF-CAREER/AnnualProjectReport-202408.docx", "Proposals/NSF-CAREER/AnnualProjectReport-202408.pdf"]*
read_file: "Proposals/NSF-CAREER/AnnualProjectReport-202408.pdf"   # * for rendered, source and mixed reads
doc_fingerprint: "f1 …"*     # generated by docs.py stamp (* for full and partial reads)
doc_checked: 2026-01-01*     # generated by docs.py stamp
read_depth: full*            # full | partial | metadata-only
read_mode: rendered*         # rendered | source | text-index | mixed | none
version_of: <final page>     # a draft's page names the final version's page
standalone: "<reason>"      # optional: why the user keeps this read page unlinked (exempts orphan, unintegrated)
group_work: ["Liu, Y."]      # optional: the user's advisees who wrote it; their text may go in [!reuse] blocks
ingested: 2026-01-01*
updated: 2026-01-01*
tags: [topic-tag]
aliases: []
---
```

Body, in order: `# <Short title> (<doc kind>, <date>)` with a **TL;DR**; `## Files` (one `file://` link per rendition,
then a section→page or section→slide map); `## Context`; `## Key content`; `## Claims and results` (bullets that start
with `[proposed]`, `[preliminary]`, `[reported]` or `[published]`; lint warns, `claim status`, about any that does not);
`## Reviewer feedback` (reviews and panel summaries); `## Reusable material`; `## Limitations and caveats` (the
document's, then the agent's, marked); `## Connections` (not evidence); `## User notes` (the user's emphasis, `>
[!user]` blocks, and a `> [!note] Reading history` with dates, which rendition was read and how, and what was not read).

A reuse block:

```markdown
> [!reuse] Computing facilities (HPC cluster paragraph) · FacilitiesAndEquipment.pdf p. 1, ¶2
> <the user's text, verbatim, up to about 300 words>
```

On a page with `group_work:` (a document by the user's students or postdocs), a block may hold an advisee's text, and
every block's label names its author: `> [!reuse] UniZeo acquisition paragraph (by Y. Liu) · slide 29`, or `(by the
user)` for the user's own text. Lint errors on a missing or unmatched `(by NAME)` there (NAME must contain the surname
of a group_work entry), and on any block on a `my_role: recipient` page without `group_work:`.

A source page over 40,000 bytes is split into **part notes** `sources/<slug>--<part>.md` (`type: source-part`,
`part_of: <slug>`, `summary`, `created`, `updated`). For a metadata-only record with no verifiable author, use
`authors: []` and explain it in the Reading history. For a document that credits no author, use `authors: []` with
`author_status: uncredited` and a Reading history line "No credited author: <evidence>". For a read document the
user decides to keep unlinked (it has no research content, say), set `standalone: "<reason>"` and add a dated
Reading history line recording the decision. Lint then skips only its `orphan` and `unintegrated` warnings. An
empty or yes/no reason, or the field on a page that is not a source page, is an error.

#### Other pages

| Type | Frontmatter | Body |
|---|---|---|
| project `projects/<name>.md` | `type`*, `summary`*, `sponsor`*, `program`, `solicitation`, `status`* (`idea \| in-preparation \| submitted \| pending \| awarded \| declined \| withdrawn \| active \| completed \| unknown`), `submitted`, `decision` (YYYY[-MM[-DD]]), `period`, `award_number`, `my_role`, `team` (list), `budget`, `folders` (list, relative to the raw root), `sources`* (generated), `created`*, `updated`* | `## Overview`; `## Aims and thrusts`; `## Timeline`; `## Outcomes`; `## Reviewer feedback and lessons`; `## Reusable material`; `## Related` |
| concept `concepts/<name>.md` | `type`*, `summary`*, `aliases`, `tags`, `sources`* (generated), `created`*, `updated`* | definition paragraph; `## Details`; `## How we have used it` (by project, with status); `## Evidence and debates`; `## Open questions`; `## Related` |
| entity `entities/<name>.md` | as concept, plus `entity_kind`* (`agency \| program \| facility \| institution \| software \| dataset \| method \| model \| material \| instrument \| benchmark \| site \| organism \| group \| person \| course`) | what it is; `## Key facts`; `## Our history with it` (proposals, awards, reviews, collaborations); `## Sources` |
| topic `topics/<name>.md` | `type`*, `summary`*, `folders` (list), `sources`* (generated), `created`*, `updated`* | `## Scope`; `## Current synthesis` (what has been proposed, done and published, by question); `## Projects`; `## Timeline`; `## Reusable material`; `## Open questions and next proposals` |
| analysis `analyses/<yyyy-mm-dd>-<slug>.md` | `type`*, `summary`*, `question`* (verbatim), `sources`* (generated), `created`* | the answer, tables, charts in `analyses/assets/`, the pages relied on |

`sources:` is exactly the source pages the body cites; `tools/catalog.py --apply` derives it. A new page may start with
`sources: []`, but lint reports it as missing until a citation and `catalog.py --apply` fill it.

### Query search mechanics (AGENTS.md §8.3)

Find pages by search. Where qmd is set up, refresh it with `qmd update && qmd embed`, then use `qmd query` and `qmd
search`. Otherwise use `tools/search.py` (several phrasings, synonyms and abbreviations; narrow with `--type`,
`--folder` or `--kind`).

### Claim audit procedure (AGENTS.md §8.5)

1. **Sample** about 10 claims from project, topic and concept pages and reuse blocks, favoring numbers, verdicts,
   status labels and single-source claims. Record how the sample was drawn.
2. **Trace** each claim to the source page and then to the rendered page, slide or source line it cites; for a reuse
   block, compare it with the file word for word.
3. **Record every finding**, typed: *transcription* (a number, unit, equation or quoted word differs) · *scope* (a
   system, condition, comparator, date or metric dropped) · *status* (proposed presented as done, preliminary as
   final) · *attribution* (wrong document, or a co-author's or reviewer's words as the user's) · *inference* · *locator*.
   The **verdict** is the most serious finding: *supported* · *scope-narrowed* · *misattributed* · *unsupported* ·
   *not checkable*. Keep confirmed and unchecked items apart in the report.
4. **Fix and propagate** (§4), including `review.py restated` for each corrected claim, and save the audit as
   `analyses/<date>-claim-audit.md`.

### Index format (AGENTS.md §9)

`catalog.py --apply` writes `index.md` below its preamble (the text before `## Topics`, which stays editorial).
Sections in order: Topics, Projects, Sources, Concepts, Entities, Analyses. One line per page, sorted (sources by date
or year, then name; other pages by name): `- [[page|Display]] — summary · <metadata>`. Display is "Title (doc_kind,
date)" for a source and the page's `# ` heading otherwise. The summary is the page's `summary:` field; the header
counts and the metadata (sources: `· <project or folder> · <read_depth>`; projects: `· <status> · <n> sources`;
others: `· <n> sources`) are generated.

### Size limit (AGENTS.md §11)

A page over 40,000 bytes (about 10k tokens) is split: a project, concept, entity or topic page into a parent and child
pages by sub-question, a source page into part notes. `split.py` moves a section verbatim (claim-neutral). An analysis
kept as a historical record is marked `frozen: true` and is exempt.

### Tool maintenance (AGENTS.md §12)

Tools are maintained in the installed skill (`{{SKILL_DIR}}`), so one copy stays the source and fixes reach every wiki
made from it: edit there, run its tests, commit there if it is a git clone, then run `python3
{{SKILL_DIR}}/scripts/init_wiki.py --upgrade-tools .` here. `wikilint.py` warns (`tools`) while `tools/` differs from
the skill or the skill is missing.
