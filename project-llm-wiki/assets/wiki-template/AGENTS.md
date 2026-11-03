# AGENTS.md — Project-document LLM Wiki schema

This file is the operating manual for the agent that maintains this wiki. It instantiates the "LLM wiki" pattern (an
agent compiles sources into a persistent, interlinked Markdown wiki and keeps it current, instead of re-deriving answers
from raw documents on every question) with **the user's own documents as the raw layer**: proposals, reports,
presentations, papers, plans and the reviews they received, in Word, PowerPoint, Excel, LaTeX, PDF and other formats,
kept under the raw root `{{RAW_ROOT}}`. The wiki exists so that future proposals and reports can draw on what was
proposed, done, reported and learned. Read this file at the start of every session and follow it in every interaction.
It states the policy. The mechanics (tool commands, fingerprints, converters, file safety, subagents, git) are in
[tools/README.md](tools/README.md).

---

## 1. Roles and layers

| Layer | Where | Owner | Agent may… |
|---|---|---|---|
| **Raw documents** | files under `{{RAW_ROOT}}` (the raw root, in `tools/config.json`) | User | **read only** |
| **Wiki** | this directory (`sources/`, `projects/`, `concepts/`, `entities/`, `topics/`, `analyses/`, root bookkeeping files) | Agent | create, edit, reorganize |
| **Schema** | `AGENTS.md` (`CLAUDE.md` imports it) and `tools/README.md` | Both | edit only with the user's agreement (§12) |
| **Tools** | `tools/*.py`, copies of the installed project-llm-wiki skill's (`{{SKILL_DIR}}`) | Skill | change in the skill first, then upgrade (§12) |

The **user** chooses which documents enter the wiki, directs emphasis, asks questions and judges what matters. The
**agent** does everything else: reading, summarizing, cross-referencing, filing, tracking what changed and bookkeeping.

## 2. Hard rules (never break these)

1. **The raw root is read only, and the wiki never modifies it.** Read it only through `tools/docs.py` or the agent's
   own file reader. Never write, move, rename, delete or convert a file there, and never open one in an application
   that could save it or leave a lock file (`docs.py` hands Word and PowerPoint a temp copy). Changes the folders need
   (removing a duplicate, adding a PDF export) are *suggested to the user*. A new document the user asks you to write,
   such as a proposal draft, is not a wiki operation: it goes where the user says, as a new file.
2. **The user chooses what is ingested.** Ingest only files or folders the user names, or items the user approves from
   a `docs.py ls` listing. Never ingest material that is confidential to others unless the user names that file and
   confirms it: merit reviews the user wrote of other people's proposals or papers, other people's proposals or
   unpublished work, student records, and personnel or salary details of others. If a named file looks like such
   material, ask before reading it.
3. **No copies of raw content, except marked reuse blocks.** No files, figures, full text or extracted text in the
   wiki. Extracted text goes only to the temp directory. The user's **own** writing may be quoted verbatim only in a
   `> [!reuse] <label> · <locator>` block on the source page it comes from (§6.10). Text by others (co-authors' sections,
   reviewers, solicitations, letters) is paraphrased, with quotations of at most 2 sentences and a locator.
4. **Every source page points back to its files** by `files:` (paths relative to the raw root) and `file://` links.
5. **Every non-trivial claim is attributed, keeps its scope and states its status** (§6.8): what was *proposed* is
   never presented as *done*. Synthesis must name its premises.
6. **Disagreements are tracked, not silently overwritten** (§6.9). Numbers that changed between a proposal, a report
   and a paper are a disagreement until their scope explains them.
7. **Be honest about what was read.** Each source page records `read_depth` (`full` every page or slide · `partial`
   some sections, listed · `metadata-only`) and `read_mode` (`rendered` pages viewed as images · `source` the authoring
   source read, LaTeX or Word/PowerPoint text with every embedded figure viewed · `text-index` extracted text only,
   figures unseen · `mixed`, say which · `none`). Never write a claim from a part you did not read.
8. **Every interaction that changes the wiki** ends with `index.md` and `log.md` updated and `wikilint.py` reporting no
   errors. Warnings are allowed only while work is in progress, and the log entry lists them. An ingest is
   **complete** only when `wikilint.py --strict` passes (no warnings, no open review items).
9. **Dates are absolute** (`YYYY-MM-DD`).
10. **User-authored text is protected.** `> [!user]` callouts and `> [!reuse]` blocks stay verbatim unless the user
    asks otherwise. Every tool that rewrites pages skips protected spans (`[!user]`, `[!reuse]`, fenced and inline
    code) and verifies them afterwards.
11. **Every interaction that changes the wiki ends with one commit** ({{GIT_LOCATION}}).
    - At session start run `git status`. Uncommitted changes are **pre-existing changes** of unknown authorship (hand
      edits, interrupted agent work, cloud sync): preserve them, tell the user, and commit them separately only once the
      user confirms.
    - At the end, stage **only the paths you changed** (never `git add -A`) and commit with the log entry's subject.
    - Push to a remote only when the user asks.

## 3. Directory layout

```
<this folder>/
├── AGENTS.md  CLAUDE.md   # this schema, and the file that makes Claude Code load it
├── index.md      # content catalog, generated (§9)
├── log.md        # append-only chronological record (§10)
├── pending.md    # open review items (§4)
├── reviewed.md   # append-only ledger of resolved review items (§4)
├── sources/      # one page per document: <slug>.md, plus part notes <slug>--<part>.md of long ones
├── projects/     # one page per funding effort: proposals, award, reports and reviews over time
├── concepts/     # ideas, methods, approaches, recurring arguments
├── entities/     # named things: sponsors and programs, facilities, codes, datasets, recurring collaborators
├── topics/       # research themes that run across projects
├── analyses/     # filed answers, comparisons, writing-support notes, audits; assets/ holds charts the agent made
└── tools/        # docs.py, review.py, catalog.py, wikilint.py, relink.py, search.py, split.py, wikimeta.py,
                  # test_tools.py, README.md, reader-brief.md, integrator-brief.md, config.json (the raw root)
```

- No other top-level folders without a schema change. Flat folders, page names unique across folders.
- **A project** is one effort to fund one body of work from one sponsor program: its proposals (including
  resubmissions and renewals), the award or decline, the reviews and panel summaries, and the reports that followed.
  Each document is a source page. The project page tells the story and links them.
- **Topics** are research themes (a method family, a materials class, an application) that span projects. They weigh
  all their sources equally and are revised as evidence accumulates.
- **Concept vs entity:** an entity has a proper name (a sponsor, a program, a facility, a code, a dataset, an
  instrument, a person or group recurring in ≥ 3 sources); a concept is a general idea, method or argument.

## 4. Identity and provenance

- **A source is one document**, identified by `doc_id`: 8 hex digits, the content hash of its main file when first
  ingested (`docs.py info` prints it), never changed afterwards. Its `files:` list every rendition of the same text
  (`Report.docx` and the `Report.pdf` exported from it), main file first, as paths relative to the raw root. A draft
  and the final version are different documents: ingest the final one, and a draft only when the user asks, with
  `version_of:` naming the final page. Filenames are lowercase kebab-case slugs that start with the year,
  `<year>-<sponsor-or-project>-<kind>[-<detail>]`, e.g. `2024-nsf-career-annual-report-y3`. Other pages: lowercase
  kebab-case, singular, no dates. Abbreviations go in `aliases`.
- **Provenance.** `docs.py stamp` records `doc_fingerprint` (a content hash per file, in the order of `files:`) and
  `doc_checked`. `docs.py changed` compares them with the files:
  - **CHANGED** (a file's content changed): re-read what changed, update the page, then stamp;
  - **MISSING** (a file was moved, renamed or deleted): `docs.py locate PAGE` finds it by its hash; correct `files:`
    and stamp, which queues nothing when the content is the same. A deleted file is recorded in the Reading history.

  A fingerprint certifies nothing unless it is complete; the rules are in tools/README.md.
- **Evidence dependencies.** A page depends on another when it cites it as evidence: in its body, outside the
  link-list sections (`## Connections`, `## Related`, `## Sources`), and not as a navigation pointer (`→ [[x]]`,
  "See [[x]]", unless a locator follows). Put related-work and "read more" links in those forms; cite with a locator
  what a claim rests on.
- **Review.** When a page's content changes, its evidence dependents are queued in `pending.md`, each with a cause. A
  changed source also reaches the dependents of source pages that quote it. Claim-neutral edits (`review.py since
  --neutral`) and additive edits (lines only inserted, except new `[!contradiction]` or `[!stale]` callouts) do not
  propagate. A corrected claim is also searched for by its old wording (`review.py restated`). Resolve each item with
  `review.py done`, an outcome (*corrected*, *unchanged* or *not-affected*) and a basis naming what was checked,
  reading the citing sentences first (`review.py list --context`). Resolutions go to `reviewed.md` and are never
  re-queued. `--strict` lint fails while items are open. Full rules: tools/README.md, section "Schema details".

## 5. Page types and templates

Every page has frontmatter in the YAML subset `tools/wikimeta.py` parses, including a one-line `summary:` (its index
entry, §9). Fields marked *generated* are written by tools, never by hand. The full templates and field lists are in
tools/README.md, section "Schema details".

### 5.1 Source page — `sources/<slug>.md`

- Frontmatter: `title`, `authors` (as credited), `year` and `date`, `doc_kind` (proposal · proposal-section ·
  pre-proposal · white-paper · report · presentation · paper · thesis · review · solicitation · correspondence · plan ·
  other), `my_role`, `project`, `doc_id`, `files`, `read_file`, the generated `doc_fingerprint` and `doc_checked`,
  `read_depth`, `read_mode`, `ingested` and `updated`.
- Body, in order: a heading with a **TL;DR**; `## Files` (a `file://` link per rendition and a section→page or
  section→slide map); `## Context` (sponsor, program, call, audience, page limits, date, team, outcome if known);
  `## Key content` (aims, thrusts, tasks, outcomes, as the document frames them); `## Claims and results` (one bullet
  per claim, each starting with its status `[proposed]`, `[preliminary]`, `[reported]` or `[published]`, with scope and
  locator); `## Reviewer feedback` (for a review or panel summary: strengths and weaknesses, attributed);
  `## Reusable material` (`[!reuse]` blocks and pointers to reusable figures and tables, §6.10); `## Limitations and
  caveats`; `## Connections` (not evidence); `## User notes` ending with a Reading history.
- Keep `authors` in credited order. Never guess an author or a year: use `authors: []` or `year: undated` with the
  reason in the Reading history.
- A source page over 40,000 bytes is split into part notes (`type: source-part`, `part_of:`), the same document's
  notes, never a second identity. Citing a part counts as citing the source.

### 5.2 Project page — `projects/<slug>.md`

Frontmatter: `sponsor`, `program`, `solicitation`, `status` (idea · in-preparation · submitted · pending · awarded ·
declined · withdrawn · active · completed · unknown), `submitted`, `decision`, `period`, `award_number`, `my_role`,
`team`, `budget`, `folders`, generated `sources`. Body: `## Overview`; `## Aims and thrusts` (as proposed, then as
carried out); `## Timeline` (submissions, decisions, reports, each linked); `## Outcomes` (results reported or
published, with status); `## Reviewer feedback and lessons` (what reviewers praised and criticized, across
submissions, attributed); `## Reusable material` (links to `[!reuse]` blocks and figures in its sources);
`## Related`.

### 5.3–5.6 Other pages

Concept, entity, topic and analysis pages follow their templates in tools/README.md, section "Schema details". Their
`sources:` is exactly the source pages the body cites, derived by `catalog.py --apply`.

### 5.7 When a page earns its own file

Only if it answers a recurring question, supports a comparison across documents, or has substantial content of its own
(≥ 2 sources with distinct claims, or one central source). Otherwise keep it as a section until it outgrows it.

## 6. Linking, citation and evidence

1. **Links**: Obsidian wikilinks by filename, with display text when helpful (`[[2024-nsf-career-annual-report-y3|CAREER
   report Y3]]`); escape the pipe inside tables (`[[a\|b]]`).
2. **Attribution**: the source link and a locator follow the claim: `… 40 % fewer simulations ([[2024-…-y3|Y3 report]]
   p. 4, Fig. 2).` Locators: `p.`, `§`, `Fig.`, `Table`, `slide`, `sheet`.
3. **Documents not yet ingested**: `[NSF CAREER proposal 2021 ↗](file:///…)` (the URL that `docs.py info` prints);
   `relink.py` converts them once the document has a page. A file not read is never evidence for a synthesis claim.
4. **Papers and other outside works** cited by a document: plain text with a DOI where printed; never guess a DOI and
   never fetch them.
5. **Callouts**: `[!synthesis]` (inference across sources, premises cited) · `[!contradiction|STATUS]` (§6.9) ·
   `[!question]` · `[!user]` (protected) · `[!reuse]` (protected, §6.10) · `[!stale]` (likely superseded, pending a
   re-check).
6. **Equations**: from LaTeX source or a rendered page, with its number; otherwise tag `(eq. unverified)`.
7. **Navigation vs evidence**: `→ [[x]]` and "See [[x]]" are pointers; a citation carries a locator (§4).
8. **Evidence scope and status.**
   - **Status**: *proposed* (a plan, aim, hypothesis or expected outcome) · *preliminary* (results shown as
     preliminary data in a proposal) · *reported* (results stated in a report, presentation or thesis, not
     peer-reviewed) · *published* (peer-reviewed, with the citation). A synthesis about what was achieved cites only
     reported or published claims; a later report supersedes the plan it carries out, and a plan that was dropped
     stays recorded as proposed.
   - Quantitative claims keep system, method, metric, conditions and the document's date ("as of the Y3 report").
   - Generalizations say how many documents and projects they rest on.
   - Reviewers' comments are opinions of that panel on that submission; attribute them ("panel, 2022 CBET review").
   - **Headings, verdicts and callout titles carry their scope too.** A conclusion may not be broader than the
     qualified evidence beneath it.
9. **Disagreement lifecycle.** `> [!contradiction|STATUS] question`, STATUS one of: `open` (unresolved); `scope`
   (different systems, conditions, dates, definitions or metrics; both hold, and the callout states the scopes);
   `superseded` (a later document settles it; keep a one-line pointer); `corrected` (the wiki was wrong; fix it and log
   a `fix`). Revisit `open` callouts when new documents arrive.
10. **Reuse blocks.** `> [!reuse] <label> · <locator>` followed by `>` lines holding the user's own text verbatim,
    on the source page it comes from: one reusable unit (a facilities paragraph, a broader-impacts activity, a
    mentoring plan element, a preliminary-results paragraph), up to about 300 words. Longer material stays in the
    file, with a pointer. A block never mixes in text by others, and its label says what it is for. Figures and tables
    are not copied: point to them (file, page or slide, caption). Projects and topics link to the block
    (`[[source#Reusable material]]`). When a source changes, its blocks are re-checked against the file with the page.

## 7. Document access

- All access goes through `tools/docs.py`, read-only (§2.1). Paths may be given relative to the raw root. If the raw
  root is unreachable (an unmounted cloud drive), stop and tell the user.
- **Reading a document means viewing it as laid out**: `docs.py render` for a PDF, and for Word, PowerPoint or Excel a
  PDF made by LibreOffice when installed, else by Microsoft Office (macOS or Windows) (tools/README.md). When a
  PDF rendition was submitted, read that one. **LaTeX** is read from its source (`docs.py text` flattens `\input`s),
  viewing each figure, which is `read_mode: source`. Word or PowerPoint text read with `docs.py text` plus every
  embedded image viewed is also `source`; text without the images is `text-index`. Extracted text is for search and
  exact quotes; never filter or truncate it.
- `docs.py ls PATH` lists the documents in a folder with their state; `docs.py info FILE` gives metadata, renditions
  and the suggested `doc_id`.

## 8. Workflows

### 8.0 Route every message

**ingest** (8.2), **query** (8.3, including help with writing), **lint** (8.4), **audit** (8.5), **schema** (8.6)
or **meta** (answer; log only if files changed). When in doubt, a query. Mixed requests: in order, each logged.

### 8.1 Session start

`git status` (§2.11); read `pending.md`, the output of `catalog.py --nav` (the index preamble, Topics and Projects)
and the last five log headers (`grep '^## \[' log.md | tail -5`); `docs.py status` if documents are needed. Never
read `index.md`, `log.md` or `reviewed.md` whole: they grow with the wiki, and tools write them (§9, §10). Find every
other page by search (§8.3). During work, run `wikilint.py --since <start revision>`.

### 8.2 Ingest

**States** (derived, never asserted): *none* (no page) · *metadata* (metadata-only) · *read* (full or partial, but no
project, concept, entity or topic page cites it in its text) · *integrated* (cited in such text).

**Complete** when every item is integrated or metadata with a reason, the project and topic pages reflect the new
evidence, `index.md` and `log.md` are updated, and strict lint passes. Otherwise the log calls the ingest *incomplete*.

**Every document is read on its own terms.** Write its page from the document alone, as if it were the first one
ingested, and only then integrate it (step 6). Comparison with the wiki belongs in integration and in `[!synthesis]`
and `[!contradiction]` callouts, not in a source page's TL;DR or key content.

**Modes.** *Guided* (default for one or a few documents): discuss (step 4) before writing (step 5). *Delegated* (a
batch, or "proceed"): skip step 4 and record under `## User notes` that there was no discussion, the date, and what
the page stresses and why; use §8.2b for more than about 5 documents.

1. **Identify** the document (`docs.py info`), its renditions, the project it belongs to, and its state; an existing
   page means a re-ingest. Check §2.2 before reading anything.
2. **Gather** the renditions, and any related files the user named (the panel summary of a proposal, its budget
   justification).
3. **Read** it in full: every page or slide, and every figure and table with its caption (§7). Less than that is
   `partial`, with what was skipped and why. Record the section→page (or slide) map. Targeted reading to answer a
   question belongs to a query (§8.3) and is never presented as a completed ingest.
   **Long documents** (theses and books of any length, and any other document over 100 pages, such as a funding
   solicitation or a final report) are read in part by default: the front matter (title page, abstract or executive
   summary, table of contents) and chosen chapters or sections, each read in full with its figures and tables. The
   user chooses them (in guided mode, or in the request); otherwise choose those relevant to the project or topic
   the document was named for, and list them in the log. Record the whole document's chapter→page map, and each
   chapter not read with the reason "long document, read in part". `read_depth` is `partial`. (Rule ported
   2026-11-02 from the Zotero-backed wiki's book rule, which the user asked for when ingesting a 131-page thesis.)
4. *(Guided)* **Discuss**: 3–6 takeaways, what looks reusable, pages to touch, tensions with the wiki. Ask what to
   emphasize and record it under `## User notes`.
5. **Write the source page**, then `docs.py stamp`.
6. **Integrate**: create or update the project page, and the topic, concept and entity pages the document bears on,
   keeping scope and status; create pages only by §5.7; check disagreements for scope; run `relink.py --apply`.
7. **Propagate and check**: `review.py since <start revision> --queue`; review and resolve; repeat until nothing new.
   Then `catalog.py --apply`, append to `log.md`, and lint.
8. **Report** what changed in the wiki's understanding, what became reusable, the disagreements found, and 1–3 next
   ingests. Run `docs.py clean`, and after a batch delete its cache folder (§8.2b).

### 8.2b Batch ingest

For more than about 5 documents: inventory them (`docs.py ls`, with the user's approval of the list, §2.2);
**reader** subagents do steps 1–5 and write only their own source pages, returning an integration brief per document;
after all readers finish, **integrator** subagents each own a disjoint set of pages; the main agent alone writes the
topic synthesis, index and log. An agent without subagents runs the same phases in order in one session. Details in
tools/README.md.

**Context per agent.** Everything an agent reads stays in its context and is sent again with every later call:
- A reader takes exactly one document and ends after writing its page and brief. Never hand it a second one: an earlier
  document in its context could shape the next page.
- An integrator owns at most about 10 pages. Split a larger page set across more integrators; never merge groups.
- A limit on subagents is a limit on how many run at once. Run the groups in waves within it.
- The main agent works one phase per session (reading, integration, synthesis). At each boundary it commits the
  checkpoint, writes the next phase's instructions to the batch state file and stops, telling the user to start a new
  session with "Continue ingestion". That phrase is the whole prompt: find the batch state file in the cache folder and
  run its next phase. The state file therefore names the phase, the start revision, the items and the cache paths.
  Subagents write their full reports to the cache folder and return one line.
- The main agent's own context grows with every call too, so it holds only file lists, `--stat` summaries and
  subagents' one-line reports, never whole pages, diffs or check output. A fresh subagent (or session) runs validation
  and reviews the diff of hand-written pages. The main agent wakes only when a subagent finishes: on a completion
  notice where the agent gets one, otherwise after the longest wait available, never in short repeated checks. Batch
  size and the number of subagents at once go in the batch state file, so any agent that continues the batch uses
  them (rule added 2026-11-02).
- Integrators read the briefs and the pages they own, not the documents or the index.

**Bounded reads**: readers read `tools/reader-brief.md` and their document, and skip §8.1; integrators read
`tools/integrator-brief.md`. Link candidates come from a search (about the top 15). Command output is bounded (`grep
-l`, `| head`, `tools/search.py`). Batch queues, briefs and state live in a cache folder outside the wiki, deleted by
the session that completes the batch. In a batch, the validation subagent reviews the diff of hand-written pages.
Check generated files with `git diff --stat`.

### 8.3 Query, and help with writing

Find pages by search: `qmd` where it is set up, otherwise `tools/search.py`, with several phrasings. Search results are
leads: read the pages themselves before answering. Use `catalog.py --nav` for orientation. Go back to the documents
only when the wiki lacks the detail, and then improve the wiki. Answer with citations down to source pages, keeping
scope and status; say what the wiki does not cover and which documents would.

**Writing support** (a new proposal, report, biosketch, response to reviewers): gather the relevant project, topic and
source pages, the `[!reuse]` blocks, the reviewer feedback and lessons, and the latest reported or published results.
Draft or outline with a citation to the source page behind each reused passage or result, so the user can trace and
update it. Say which reused text is older than the latest report on the same work. Never turn a proposed aim into an
accomplishment. The draft itself goes where the user says (§2.1), not into the wiki. Offer to file what was learned
(a comparison of past aims, the lessons from reviews) in `analyses/`. Log the query.

### 8.4 Lint

1. `wikilint.py` (its header lists the errors and warnings it checks).
2. `docs.py changed --queue`; handle each change by kind; work through `pending.md`. Tool changes go through the skill
   (§12), never straight into `tools/`.
3. `docs.py ls <folder> --recursive` for each project or topic with `folders:`, to see what is not yet ingested (and
   offer it to the user, §2.2).
4. **Read for**: claims that lost their scope or status; proposed work presented as done; `open` contradictions newer
   documents may resolve; superseded claims and stale reuse blocks; concepts on ≥ 2 pages without a home; projects
   whose status or timeline lags the documents.
5. Fix mechanical issues, present judgment calls, log the pass with counts.

### 8.5 Claim audit

Lint checks structure; only an audit checks the knowledge. Run one after a substantial ingest, before the user relies
on the wiki for an important proposal, or when asked. Sample about 10 claims (favoring numbers, verdicts, reuse
blocks and status labels) and record how they were drawn, trace each to the rendered page or source it cites, record
typed findings and a verdict per claim, then fix and propagate (§4) and save the audit as
`analyses/<date>-claim-audit.md`. Finding types and verdicts: tools/README.md, section "Schema details".

### 8.6 Schema change

Propose the edit, apply it after the user agrees, migrate existing pages, add a lint check where the rule is
checkable, and log it as `schema`. Prefer an automated check to another prose rule. Once the first few ingests and an
audit have run, propose **freezing the schema**: from then on, change it only when an actual ingest, sync or audit
fails, and name that failure in the log entry.

## 9. `index.md`

`catalog.py --apply` generates every line of `index.md` below its editorial preamble, from each page's `summary:`
and heading. Never edit index lines by hand. Agents read the index only through `catalog.py --nav` (§8.1) and find
pages by search (§8.3). Line format: tools/README.md, section "Schema details".

## 10. `log.md`

Append-only, newest at the bottom; never rewrite past entries (append a `fix`). Headers: `## [YYYY-MM-DD] <op> |
<subject>`, op ∈ `setup | ingest | reingest | query | file | lint | schema | fix`. Body: 2–10 bullets with doc_ids,
pages created (`+`) and updated (`~`), disagreements and their resolution, open findings, claim-neutral edits not
propagated, and `next:` lines. Append an entry without reading the file, and find past entries by searching it.

## 11. Writing style

- Write for the user: {{AUDIENCE}} Be precise; skip textbook padding.
- Paraphrase. Numbers with units, systems and conditions. Math in LaTeX with the document's notation.
- Spell out an acronym at its first use on a page. Avoid semicolons that join independent clauses and em dashes that
  introduce parenthetical remarks in new prose. Label your own inferences and speculation.
- Keep pages focused; split pages that cover two ideas and merge near-duplicates.
- **Size limit**: every page stays under 40,000 bytes, because integrations, reviews and audits read whole pages.
  Split oversized pages with `split.py`. Historical analyses marked `frozen: true` are exempt.
- Synthesis is the point of the wiki. Mark it `> [!synthesis]` when it goes beyond any one source, and cite its premises.

## 12. Co-evolution and open decisions

- **Revision history**: {{GIT_LOCATION}}; push on request (tools/README.md).
- **Tools are maintained in the installed skill** (`{{SKILL_DIR}}`): change them there first, test, then upgrade
  this wiki (tools/README.md, section "Schema details").
- **YAML parsing**: a strict, tested parser for the frontmatter subset, so the tools stay dependency-free.
- **Search tools**: `qmd` (optional, local keyword plus vector search) and `tools/search.py` (BM25, standard library).
- **Ingest cost** stays bounded per document: one document per reader context, a short brief, orientation from
  `catalog.py --nav`, pages found by search, tool-written append-only files, additive edits that do not propagate,
  and pages under 40,000 bytes (§8.2b, §11).
- **People and groups as entities**: only if they recur in ≥ 3 sources.
- **One raw root**: files elsewhere are out of scope until the user moves them under it or a schema change adds a
  second root.
