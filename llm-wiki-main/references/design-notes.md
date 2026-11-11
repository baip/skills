# Design notes

Why the schema in `assets/wiki-template/AGENTS.md` looks the way it does. Section 1 covers what changed when the
design was adapted from the Zotero-backed literature wiki (`llm-wiki-zotero`) to a folder of the user's own documents;
section 3 keeps that skill's lessons, which were measured on a literature wiki and carried over unchanged. Read the
section that matches the question; nothing here is needed for routine work.

## Contents

1. What changed from the Zotero-backed wiki, and why
2. Formats and converters
3. Inherited lessons (review propagation, audits, bookkeeping, schema size, ingest cost)
4. Known limits

## 1. What changed from the Zotero-backed wiki, and why

- **The raw layer is a folder, not a database.** Proposals, reports and slides live in a project tree, often in a
  cloud drive, with drafts, exports and other people's files mixed in. There is no API and no item key, so the tools
  read files directly and the schema replaces "read only through the API" with "read only, never write, never open
  in an app that saves or leaves a lock file".
- **The user names what is ingested.** A literature library is curated before it reaches the wiki; a project tree is
  not. It holds merit reviews the user wrote of other people's proposals (confidential, and sponsors such as NSF
  restrict sharing them with AI tools), other people's proposals shared privately, student records and salary
  details. Hence the hard rule that nothing is swept in, and that confidential material needs the user's explicit
  confirmation per file.
- **Identity is a content hash, paths are locators.** Users reorganize folders and rename files, so `doc_id` is the
  hash of the main file at first ingest and never changes, while `files:` records where the renditions are now.
  A move shows up as MISSING, `locate` finds the file by its stamped hash, and a stamp after fixing `files:` queues
  nothing when the content is the same (the comparison ignores order). Fingerprints hash bytes: a Word file re-saved
  without edits may change, which costs a re-check but never hides a change.
- **One document, several renditions.** A report exists as `.docx` and as the `.pdf` exported for submission; they
  are one source page with both in `files:`, because they are one text. Drafts are separate documents
  (`version_of:`), since they differ in content and only the final one was submitted.
- **Projects are a page type.** Writing a new proposal draws on a funding effort as a whole: what was proposed, what
  the panel said, what the reports showed, what was resubmitted. Zotero collections gave topics; here the project is
  the unit the user thinks in.
- **Claim status.** The main failure specific to proposal material is presenting a plan as a result. Every claim on
  a source page is tagged `[proposed]`, `[preliminary]`, `[reported]` or `[published]`, lint warns about untagged
  ones, and syntheses of what was achieved may cite only the last two. The claim audit has a matching *status*
  finding type.
- **Reuse blocks.** Copyright and drift made the Zotero wiki forbid verbatim text. Here the text is the user's own and
  reusing it is the point, so verbatim passages are allowed, but only in `[!reuse]` blocks on the source page they come
  from (provenance and drift are then checked with that page), protected from rewriting tools like `[!user]`, and
  never for text by others.
- **Long documents.** The Zotero wiki read books over 150 pages by chapter. Here the rule covers theses and books of any length and any other document over 100 pages (solicitations run to about 130, final reports and theses to 100-200): front matter plus chosen chapters, each in full, with the whole chapter map recorded, so unread chapters stay visible. Ported on the user's request while ingesting a 131-page thesis (2026-11-02).
- **Reading modes.** `rendered` (pages viewed as images) stays the default. `source` is new: LaTeX is better read from
  its source than from a rendering, and Word or PowerPoint text plus every embedded image is close to a rendering
  when no converter is available. `abstract` was dropped (documents have no separate abstract) and `supplement`
  (proposal parts are separate documents).

## 2. Formats and converters

- PDF renders directly with poppler. Word, PowerPoint and Excel are converted to PDF first, by LibreOffice when it
  is installed (any system) and else by Microsoft Office (exact layout; macOS by AppleScript, Windows by PowerShell
  COM). Office was tried first until 2026-11-03, because layout differences (fonts, line breaks, slide scaling) can
  move figure and table content across pages, which matters for locators. The user then asked for LibreOffice by
  default (headless, no app windows or Automation prompts); `PROJECT_WIKI_CONVERTER=office` restores Office first. On macOS with Office installed, conversion of a temp copy ran
  without dialogs (2026-11-02; about 17 s for Word and 25 s for PowerPoint including app launch). The first run may
  trigger the system's Automation permission prompt.
- Office always gets a temp copy because opening a document leaves a `~$` lock file next to it, which would land in
  the synced raw root. The script closes without saving and quits the app only if it was not already running.
- Text extraction: pandoc for Word (tables and equations survive, images are extracted), the standard library for
  PowerPoint (slides in presentation order, speaker notes, images) and Excel (cell values), a flattener for LaTeX
  (`\input`/`\include`), poppler for PDF text, and textutil or the PDF conversion for `.doc`/`.rtf`/`.odt`.
- Keynote and Pages files need the user to export a PDF.

## 3. Inherited lessons

These were developed on a 140-page literature wiki (and then one of about 4,000 source pages) through six external
reviews and four claim audits, and apply unchanged.

### Review propagation

When a page changes, pages that cite it as evidence may be stale. What worked, after measurement:

- A full transitive closure queued a median of 136 of 140 pages for any one change: useless.
- Citation links as evidence, but not navigation pointers (`→ [[x]]`, "See [[x]]"); source chains followed only when a
  source page changed (a source quoting another source restates its results); synthesis pages propagate only when a
  review actually changes them. Median 15 pages per source change, 5 per synthesis-page change.
- Claim-neutral edits (locators, typos) are named and not propagated.
- Every resolution is recorded with an outcome (*corrected*, *unchanged*, *not-affected*) and a basis in an append-only
  ledger, so a finished review is never redone and a clearance can be checked. A keyword search may choose what to read,
  but it is not a basis.
- Citation links miss restatements: a conclusion written on two pages from the same sources is linked to the sources,
  not to the other page. Audit 3 found five corrected claims that survived elsewhere this way, hence
  `review.py restated PAGE --phrase …`, which searches for the old wording.

### Claim audits

Lint checks structure; only an audit checks knowledge. An audit samples about ten claims, traces each to the rendered
page it cites, and records typed findings (transcription, scope, attribution, inference, locator) and a verdict.

Four audits on the development wiki found the same thing each time:

- **Numbers were copied correctly** (0 transcription errors in 42 claims).
- **Conclusions were the weak point**, and errors grew with how much a page concluded: topic headings and verdicts worst,
  concept-page callouts next, entity facts best.
- The recurring failure is a conclusion that states the *kind* of evidence rather than its *count and scope*:
  "in three controlled comparisons" (one was controlled), "every model is short-ranged" (one was not), "four cases" (one
  was the agent's own inference). Words to check first: *every, all, only, controlled, needed, n cases*.
- Hence the rule that headings, verdicts and callout titles carry their scope, like any other claim.

### Generated bookkeeping

`sources:` lists and index counts were maintained by hand and drifted (two counts were wrong when first generated).
`catalog.py` now derives them; lint warns when they are stale. Index summaries stay editorial.

### Keeping the schema small

The schema grew to 5,300 words in one day of reviews, with machinery added before any real Zotero change had gone
through it. Two lessons: move mechanics (formats, algorithms) to `tools/README.md` and keep policy in `AGENTS.md`; and
once the first ingests and an audit have run, freeze the schema and change it only when an actual ingest, sync or audit
fails, naming that failure in the log. The restatement rule is an example of a change that passed that test.

### Ingest cost grows with the wiki (2026-11-01)

At about 4,000 source pages, ingest cost per paper had risen roughly 4-fold: Codex logs showed mean input per call in
wiki sessions rising from about 60k to about 240k tokens while tokens per 1 % of the weekly quota stayed flat, so the
cause was the wiki, not the plan. Three things loaded unbounded text into every step: readers that read many papers in
one context (rendered pages are re-sent on every later call), an `index.md` of 1.6 MB that session start told agents to
read and hand edits required them to open, and summary pages of 50–90 KB that every integration and review read whole,
with each edit queueing hundreds of dependents. The fixes keep each step's load bounded: one paper per reader context,
a generated index read through `catalog.py --nav` with summaries in frontmatter, append-only files written by tools,
additive edits exempt from propagation (dependents rest on existing sentences, which an insertion leaves intact), and a
40,000-byte limit on summary pages with `split.py` moving sections verbatim.

The same day the goal was sharpened to *ingest cost independent of wiki size*, checking every ingest step for
reads that grow with the wiki: orientation became the Topics list only; readers take link candidates from a search
and get a short brief instead of the full schema (with one paper per context the bootstrap is paid per paper);
reviews read the sentences that cite the changed page before opening a dependent; lint with `--since` details only
changed pages; generated files are checked by `git diff --stat`; batch queues and orchestrator state live outside the
wiki; and the size limit covers source pages (split into `source-part` notes tied to one identity) and analyses
(historical ones frozen). What still grows is the number of review items after a correction to a heavily cited
page, and search and lint run time.

### Integration dominates a batch (2026-11-02)

The first batch under these rules (51 papers, Claude Code transcripts weighted by API price ratios) showed that
bounding page size and reads was not enough. With one paper per reader the mean context per call fell from about 120k
to 80k tokens, but each paper cost about 0.40M input-equivalent tokens against 0.34M when readers took 2–3 papers,
because every fresh reader pays its startup again. Integration cost more than all the reading: a user cap of 4
subagents had been met by merging 9 page groups into 4, so each integrator held 25–40 pages, plus whole-brief grep
output, in one context (mean 200–258k tokens per call, 13.4M of the run's 25.5M). The orchestrator also kept one
session through all phases (300k tokens per call). The rules now bound what one context holds, not only what one file
holds: integrators own at most about 10 pages, a cap on subagents means waves rather than merged groups, each
integrator gets its own slice of the briefs, command output is bounded, subagents report through files, and the
orchestrator works one phase per session. Integration cost is roughly the number of target pages times the pages per
integrator, so this should cut it about 3-fold (an estimate, not yet measured). Bundling short papers per reader was
adopted and reverted the same day: it saves about 15 % of reading, but an earlier paper in the context could shape
the next page, which must be written from its own paper alone. One paper per reader is the price of that
independence.

### The orchestrator becomes the cost (2026-11-02)

Once readers and integrators were bounded, the orchestrator was the largest consumer. In two 8-paper batches of a
Zotero-backed wiki it used 46 % and 64 % of the tokens: 95–163 calls per phase at a mean context of 95–151k tokens,
against 56–71k for readers and integrators. Most calls were checks on running subagents, each resending the whole
context, and whole diffs or files it read to review the work. An orchestrator's cost per phase is roughly fixed, so
it weighs most on small batches. The rules now keep its context small: it reads only file lists, `--stat` summaries
and one-line reports, a fresh validation subagent runs the checks and the diff review, and it wakes only when a
subagent finishes. The rules are stated for any agent. The same wiki may be run by different agents, which notify,
poll or block in different ways, so only the goal is fixed.

Measured over the next ten 8-paper batches of that wiki (batches 200–209, 2026-11-03 to 2026-11-04), the orchestrator
used 7–12M tokens per batch (21–28 %) against 24–36M (46–62 %) before, in 112–174 calls per batch against 237–255, at a
mean context of 51–93k per phase against 97–152k. A batch fell from 52–57M to 32–51M tokens (mean 39M, about 28 % less)
and, on the one account whose weekly quota could be read, from about 23 to about 17 weekly percentage points. About two
fifths of the orchestrator's saving went to the validation subagents that took over the checks and diff reviews: 6–13M
tokens per batch, at a mean context of 108k, more than a reader's 76k. They are the next candidate for bounding. The
baseline is only two batches and the papers differ, so the total saving is less certain than the orchestrator's, whose
ranges do not overlap.

### Validation becomes the cost (2026-11-04)

With the orchestrator bounded, the validation subagents that took over its checks and diff reviews cost as much as it
did: 6–13M tokens per batch in ten batches of the Zotero-backed zotero-chatgpt wiki. Each held a whole batch's notes,
records and reports, or every integrator's diff, then ran the build, checks, tests and search-index refresh on top of
that load, so most of its calls ran above 120k tokens, and seven started as forks of the orchestrator's context.
Validation is now split like integration: reviewers of about 3 papers or documents or one integrator group each, in
fresh contexts from a short brief, and checks in a context that holds no page content. The review standard is unchanged:
every new or changed hand-written page is still reviewed in full, against its reader report or the source page it cites.
A reviewer no longer sees other groups' diffs, but each still checks claims against the source pages, where a conflict
between groups shows up as a mismatch. Expected saving, not yet measured: about half of validation, some 5M tokens per
batch.

Measured over the next 29 batches of the zotero-chatgpt wiki (batches 211–239, 2026-11-04 to 2026-11-06, mostly headless
runs of `continue_ingestion.py`): validation fell from 9.8M to 4.6M tokens per batch (2.2–6.7M against 6.2–13.3M), with
reviewers at mean contexts of 31–56k. The orchestrator rose from 9.7M to 13.2M (36 % of a batch), because it now
launches and waits on about 30 subagents per batch instead of about 20, at about 72k tokens per call (176 calls per
batch against 140). A batch used 37.0M against 39.3M, a difference within the batch-to-batch spread (24.9–54.9M), and
readers and integrators were unchanged at about 19M. About half of the orchestrator's tokens are its startup reading:
its context grows from a median of 23k tokens at the first call to 62k by the tenth, and that load is resent on each of
about 85 calls per phase.

The zotero-chatgpt wiki then gave its orchestrator a short brief (`docs/orchestrator-brief.md`) in place of the session
protocol and the skill's references. Over the next five phases (2026-11-07) its context at the tenth call was 32–39k
tokens against 56–70k, at the same 73–84 calls per phase, and it used 3.1–4.3M tokens per phase against 4.9–10.1M, about
7M per batch against 13.2M. It was ported here the same day as `tools/orchestrator-brief.md`. This skill's AGENTS.md is
the full schema, which both agents load on their own, so the brief cannot replace it, but the zotero wiki's first batch
under the current rules (39 papers, 2026-11-07) showed what else the orchestrator loaded: SKILL.md, a workspace-memory
search, the whole state file and part of `tools/README.md`, about 150,000 characters, for mean contexts of 82–109k
tokens per phase. The brief names only the state file's scalar fields and itself. Its effect here is not yet measured.
The same runs added one rule: every phase commits, even one that changed nothing, because the headless loop reads a
phase without a commit as stuck.

In the zotero wiki the brief roughly halved the orchestrator's startup load in reading and integration (context at the
tenth call 36–41k tokens against 68–78k), but not in synthesis. Propagating a claim audit's corrections there took 12 %
of a batch, 239 review items of which 180 were not-affected. Both templates therefore gained the same day a screener
(`review.py screen`, then one `review.py resolve`) ahead of resolvers, and a propagation phase after synthesis in its
own session. Details in the llm-wiki-zotero skill's design notes. Neither effect is measured here yet.

## 4. Known limits

- One raw root per wiki. Files elsewhere must be moved under it, or the schema extended.
- Windows and Linux code paths (PowerShell COM automation, `msvcrt` locks, LibreOffice-only rendering) are written but
  were not yet run on those systems.
- Locks coordinate processes on one machine only. Do not run the tools on one wiki from two machines at once.
- Wikis in a cloud-synced folder need the git directory outside it (`--git separate` or `worktree`).
- A fingerprint hashes bytes, so a document re-saved without edits is reported as changed.
- Which figure supported which claim is recorded only in prose Reading histories.
