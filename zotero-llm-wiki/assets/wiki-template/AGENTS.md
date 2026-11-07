# AGENTS.md — Zotero-backed LLM Wiki schema

This file is the operating manual for the agent that maintains this wiki. It instantiates the "LLM wiki" pattern (an
agent compiles sources into a persistent, interlinked Markdown wiki and keeps it current, instead of re-deriving answers
from raw documents on every question) with **Zotero as the raw layer**. Read it at the start of every session and follow
it in every interaction. It states the policy; the mechanics (tool commands, fingerprint and queue details, file safety, page
rendering, subagents, git) are in [tools/README.md](tools/README.md).

---

## 1. Roles and layers

| Layer | Where | Owner | Agent may… |
|---|---|---|---|
| **Raw sources** | Zotero library (items, PDFs, the user's notes and annotations) | User | **read only** |
| **Wiki** | this directory (`sources/`, `concepts/`, `entities/`, `topics/`, `analyses/`, root bookkeeping files) | Agent | create, edit, reorganize |
| **Schema** | `AGENTS.md` (`CLAUDE.md` imports it) and `tools/README.md` | Both | edit only with the user's agreement (§12) |
| **Tools** | `tools/*.py`, copies of the installed zotero-llm-wiki skill's (`{{SKILL_DIR}}`) | Skill | change in the skill first, then upgrade (§12) |

The **user** curates sources, directs emphasis, asks questions and judges what matters. The **agent** does everything
else: reading, summarizing, cross-referencing, filing, tracking disagreements and bookkeeping.

## 2. Hard rules (never break these)

1. **Zotero is the single source of truth, and the wiki never modifies it.** Read it only through `tools/zot.py`
   (GET requests and read-only Better BibTeX lookups). Never open, copy or query `zotero.sqlite`, and never touch the
   Zotero data directory or linked-attachment folders. Changes the library needs (attaching a PDF, merging duplicates)
   are *suggested to the user*.
2. **No duplication of raw content.** No PDFs, figures, full text, verbatim abstracts or Zotero notes in the wiki.
   Extracted text goes only to a temp directory outside it. Allowed: quotations of ≤ 2 sentences with a locator,
   equations rewritten in LaTeX, numbers and tables summarized in your own words.
3. **Every source page points back to Zotero** by `library`, `zotero_key` and a `zotero://select` link.
4. **Every non-trivial claim is attributed and keeps its scope** (§6.8). Synthesis must name its premises.
5. **Disagreements are tracked, not silently overwritten** (§6.9).
6. **Be honest about what was read.** Each source page records `read_depth` (`full` every body page · `partial` some
   sections, listed · `abstract` · `metadata-only`) and `read_mode` (`rendered` pages viewed as images · `text-index`
   extracted text only, figures unseen and equations unverified · `mixed`, say which · `none`), plus
   `supplement` (`read` · `skimmed` · `not-read`: it exists but was not read, or is not attached in Zotero · `none`: the
   work has no supplement), required for `full` and `partial` reads; `not-read` needs a line "Supplement not read:
   <reason>" in the Reading history (§8.2 step 3). Never write a claim from a part you did not read.
7. **Every interaction that changes the wiki** ends with `index.md` and `log.md` updated and `wikilint.py` reporting no
   errors. Warnings are allowed only while work is in progress, and the log entry lists them. An ingest is
   **complete** only when `wikilint.py --strict` passes (no warnings, no open review items).
8. **Dates are absolute** (`YYYY-MM-DD`).
9. **User-authored text is protected.** `> [!user]` callouts stay verbatim unless the user asks otherwise. Every tool
   or script that rewrites pages skips protected spans (`[!user]`, fenced and inline code) and verifies them afterwards.
10. **Every interaction that changes the wiki ends with one commit** ({{GIT_LOCATION}}).
    - At session start run `git status`. Uncommitted changes are **pre-existing changes** of unknown authorship (hand
      edits, interrupted agent work, cloud sync): preserve them, tell the user, and commit them separately only once the
      user confirms.
    - At the end, stage **only the paths you changed** (never `git add -A`) and commit with the log entry's subject.
    - Push to a remote only when the user asks.

## 3. Directory layout

```
<this folder>/
├── AGENTS.md  CLAUDE.md   # this schema, and the file that makes Claude Code load it
├── index.md      # content catalog: read first on every query (§9)
├── log.md        # append-only chronological record (§10)
├── pending.md    # open review items (§4)
├── reviewed.md   # append-only ledger of resolved review items (§4)
├── sources/      # one page per Zotero item: <citekey>.md, plus part notes <citekey>--<part>.md of long ones
├── concepts/     # general ideas, methods, phenomena
├── entities/     # named things: models, codes, datasets, benchmarks
├── topics/       # synthesis hubs, usually mirroring a Zotero collection
├── analyses/     # filed answers, comparisons, audits; assets/ holds charts the agent made
└── tools/        # zot.py, review.py, catalog.py, wikilint.py, relink.py, search.py, split.py, wikimeta.py, test_tools.py, README.md,
                  # reader-brief.md, integrator-brief.md, validator-brief.md
```

- No other top-level folders without a schema change. Flat folders; page names unique across folders.
- **Concept vs entity:** an entity has a proper name (a named model, method, dataset, instrument, code, organism, site or
  benchmark); a concept is a general idea, phenomenon or method class.
- **Topics** are synthesis pages that weigh all their sources equally and are revised as evidence accumulates, each
  listing the Zotero collection(s) it mirrors.
- **New collections** become new topics in this wiki rather than separate wikis, unless the user decides otherwise.
  Identity is library-qualified (§4), so merging wikis later stays cheap.

## 4. Identity and provenance

- **A source is identified by (`library`, `zotero_key`)**, e.g. `{{LIBRARY}}` + `ABCD1234`. Keys are unique only within
  a library. The filename is the item's citation key (Zotero 7's native field or Better BibTeX; `zot.py item` generates an
  `authorTitleWordsYear` key when there is none and says so); if the citekey changes, keep the filename and add the new
  key to `aliases`. Other pages: lowercase kebab-case, singular, no dates. Put abbreviations in `aliases`.
- **Provenance.** `zot.py stamp` records `zotero_fingerprint` (content hashes of biblio, abstract, PDFs, notes and
  annotations) and `zotero_checked`. `zot.py changed` compares them with Zotero:
  - a **metadata refresh** (only bibliographic fields changed): update the frontmatter and stamp;
  - a **scientific re-read** (abstract, PDF, notes or annotations changed): re-read, update the page, then stamp.

  A fingerprint certifies nothing unless it is complete and consistent; the rules that guarantee this are in tools/README.md.
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
- **Versions of one work** (preprint and published) keep separate pages. The earlier page sets `version_of:` and
  records only what differs; cite the later one. **Count works, not pages** (§6.8), and suggest merging in Zotero.

## 5. Page types and templates

Every page has frontmatter in the YAML subset `tools/wikimeta.py` parses, including a one-line `summary:` (its index
entry, §9). Fields marked *generated* are written by tools, never by hand. The full templates, field lists and
conventions are in tools/README.md, section "Schema details".

### 5.1 Source page — `sources/<citekey>.md`

- Frontmatter: the bibliographic fields, `library`, `zotero_key`, `citekey`, `zotero_uri`, the generated
  `zotero_fingerprint` and `zotero_checked`, `collections`, `read_depth`, `read_mode`, `supplement` (§2.6),
  `ingested` and `updated`.
- Body, in order: a heading with a **TL;DR**, `## Open in Zotero` (with a section map of PDF page links),
  `## Key contributions`, `## Methods / setup`, `## Results and claims` (each with scope and locator),
  `## Limitations and caveats`, `## Connections` (not evidence) and `## User notes` ending with a Reading history.
- Keep `authors` in credited order. Never guess an author or a year: use `authors: []` or `year: undated` with the
  reason in the Reading history.
- A source page over 40,000 bytes is split into part notes (`type: source-part`, `part_of:`), the same work's notes,
  never a second identity. Citing a part counts as citing the source.

### 5.2–5.5 Other pages

Concept, entity, topic and analysis pages follow their templates in tools/README.md, section "Schema details". Their `sources:` is exactly the
source pages the body cites, derived by `catalog.py --apply`.

### 5.6 When a page earns its own file

Only if it answers a recurring question, supports a comparison across sources, or has substantial content of its own
(≥ 2 sources with distinct claims, or one central source). Otherwise keep it as a section until it outgrows it.

## 6. Linking, citation and evidence

1. **Links**: Obsidian wikilinks by filename, with display text when helpful (`[[smithExampleStudyTitle2021|Smith 2021]]`); escape the
   pipe inside tables (`[[a\|b]]`).
2. **Attribution**: the source link and a locator follow the claim: `… within 3 % ([[smith…2021|Smith 2021]] §3.1).`
3. **Zotero items not yet ingested**: `[Doe 2024 ↗](zotero://select/library/items/IJKL9012)`; `relink.py` converts
   them once the item has a page. A not-yet-ingested item's Zotero abstract may motivate a `[!question]` or a
   reading-queue entry, labelled "abstract only, not ingested", but is never evidence for a synthesis claim.
4. **Papers not in Zotero**: plain text with a DOI, and a reading-queue entry "not in Zotero, suggest adding". If the DOI is
   not printed and cannot be confirmed, give the full reference and write "DOI not found"; never guess one. Never fetch
   such papers and store them.
5. **Callouts**: `[!synthesis]` (inference across sources, premises cited) · `[!contradiction|STATUS]` (§6.9) ·
   `[!question]` · `[!user]` (protected) · `[!stale]` (likely superseded, pending a re-check).
6. **Equations**: cite the equation number and transcribe from the rendered page; otherwise tag `(eq. unverified)`.
7. **Navigation vs evidence**: `→ [[x]]` and "See [[x]]" are pointers; a citation carries a locator (§4).
8. **Evidence scope.**
   - Quantitative claims keep system, reference method, metric and conditions ("error 36 units on system S against
     reference R with method M, Smith 2021 Table 1", not "method M reaches 36").
   - Generalizations say how many works and systems they rest on; a claim from one source or system says so.
   - Reviews are secondary evidence: "(X, via [[review]])", or ingest X.
   - **Headings, verdicts and callout titles carry their scope too.** "Long-range cost ranges from ~26 % to ~5× in the
     schemes compared", not "long range is no longer expensive". A conclusion may not be broader than the qualified
     evidence beneath it.
9. **Disagreement lifecycle.** `> [!contradiction|STATUS] question`, STATUS one of: `open` (unresolved); `scope`
   (different systems, conditions, definitions or metrics; both hold, and the callout states the scopes); `superseded`
   (newer evidence settles it; keep a one-line pointer, move detail to the log); `corrected` (the wiki was wrong; fix it
   and log a `fix`). First check whether the claims concern the same system, conditions, definitions and metric.
   Revisit `open` callouts when new sources arrive.

## 7. Zotero access

- All access goes through `tools/zot.py`, read-only (§2.1). If Zotero is not running, ask the user to start it.
- The user's notes and annotations are high-signal: always read them during ingest.
- **Reading a paper means viewing its rendered PDF pages** (`zot.py render`, then view each page image; tools/README.md).
  The text index is for searching and exact quotes only; never filter or truncate it. If a PDF cannot be rendered, read
  the text index and record `read_mode: text-index`. Without a PDF, record `abstract` or `metadata-only`. Never copy a
  PDF.

## 8. Workflows

### 8.0 Route every message

**ingest** (8.2), **query** (8.3), **lint** (8.4), **audit** (8.5), **schema** (8.6) or **meta** (answer; log only if
files changed). When in doubt, a query. Mixed requests: in order, each logged.

### 8.1 Session start

`git status` (§2.10); read `pending.md`, the output of `catalog.py --nav` (the index preamble and Topics) and
the last five log headers (`grep '^## \[' log.md | tail -5`); `zot.py status` if Zotero is needed. Never read
`index.md`, `log.md` or `reviewed.md` whole: they grow with the wiki, and tools write them (§9, §10). Find every other
page by search (§8.3). During work, run `wikilint.py --since <start revision>`, which lists every error but details
warnings only for the pages you changed.

### 8.2 Ingest

**States** (derived, never asserted): *none* (no page) · *metadata* (abstract or metadata-only) · *read* (full or
partial, but no concept, entity or topic page cites it in its text) · *integrated* (cited in such text). *Integrated* is
a structural proxy; the semantic check is integration itself and the claim audit.

**Complete** when every item is integrated or metadata with a reason, the topic synthesis reflects the new evidence,
`index.md` and `log.md` are updated, and strict lint passes. Otherwise the log calls the ingest *incomplete*.

**Every source is read on its own terms.** Write its page from the paper alone (its questions, methods, findings and
limitations) as if it were the first item ingested, and only then integrate it (step 6). Order of ingestion confers no
authority: an earlier page is not a thesis for later papers to confirm or refute, a later paper need not relate to
existing pages, and one that fits no existing page gets new pages by §5.6 rather than being bent to fit. Comparison
with the wiki belongs in integration and in `[!synthesis]` and `[!contradiction]` callouts, not in a source page's
TL;DR or key contributions.

**Modes.** *Guided* (default for one or a few items): discuss (step 4) before writing (step 5). *Delegated* (a batch, or
"proceed"): skip step 4 and record under `## User notes` that there was no discussion, the date, whether Zotero has notes
or annotations, and what the page stresses and why; use §8.2b for more than about 5 items.

1. **Identify** the item (`zot.py item`) and **check its state**; an existing page means a re-ingest or resume.
2. **Gather** metadata, the user's notes and annotations, and the PDF.
3. **Read** the rendered pages. The default is complete: every body page, and every figure and table with its caption.
   Read the supplement where the main text relies on it (methods, parameters, data or results it defers there);
   otherwise record `supplement: not-read` and a line "Supplement not read: <reason>" in the Reading history. Less
   than the full main text is `partial`, with what was skipped and why (missing from Zotero, unreadable, the user's
   choice). Targeted reading to answer a question belongs to a query (§8.3) and is never presented as a completed
   ingest. Record the section→page map, transcribe equations, note what was not read.
   **Books over 150 PDF pages** (`item_type: book`) are read in part by default: the front matter (title, contents,
   preface) and chosen chapters, each read in full. In guided mode the user chooses the chapters; otherwise choose those
   relevant to the item's Zotero collection and list them in the log. Record the whole book's chapter→page map, and the
   chapters not read with the reason "book read in part".
4. *(Guided)* **Discuss**: 3–6 takeaways, pages to touch, tensions with the wiki. Ask what to emphasize and record it
   under `## User notes`.
5. **Write the source page**, then `zot.py stamp`.
6. **Integrate**: update the pages the source bears on, keeping scope; create pages only by §5.6; check disagreements
   for scope; `zot.py search` cited works and link those in Zotero with `↗`; run `relink.py --apply`.
7. **Propagate and check**: `review.py since <start revision> --queue`; review and resolve; repeat until nothing new.
   Then `catalog.py --apply` (it writes `index.md` from the pages' `summary:` fields), append to `log.md`, and lint.
8. **Report** what changed in the wiki's understanding, the disagreements found, and 1–3 next ingests. Clean up temp files and, after a batch, its cache folder (§8.2b).

### 8.2b Batch ingest

For more than about 5 items: inventory the items and their states; **reader** subagents do steps 1–5 and write only
their own source pages, returning an integration brief per paper (claims per target page with locators and scope,
tensions, evidence on open questions, reading-queue candidates); after all readers finish, **integrator** subagents
each own a disjoint set of pages; the main agent alone writes the topic synthesis, index and log. An agent without
subagents runs the same phases in order in one session. Details in tools/README.md.

**Context per agent.** Everything an agent reads stays in its context and is sent again with every later call, so
each reader, integrator and phase gets a fresh context with a bounded load (rules added 2026-11-01, and 2026-11-02 after
integrators holding 25–40 pages each used half of a run's tokens):
- A reader takes exactly one paper and ends after writing its page and brief. Never hand it a second paper, even a
  short one: an earlier paper in its context could shape the next page, which must be written from its own paper
  alone (§8.2).
- An integrator owns at most about 10 pages, fewer when they are long. Split a larger page set across more integrators;
  never merge groups to have fewer.
- A limit on subagents (the user's, or the agent's) is a limit on how many run at once. Run the groups in waves within
  it.
- The main agent works one phase per session (reading, integration, synthesis). At each boundary it commits the
  checkpoint, writes the next phase's instructions to the batch state file and stops, telling the user to start a new
  session with "Continue ingestion". That phrase is the whole prompt: find the batch state file in the cache folder and
  run its next phase. The state file therefore names the phase, the start revision, the items and the cache paths (rule
  added 2026-11-02). In a headless run (the skill's `scripts/continue_ingestion.py`, which starts each session with that
  phrase) nobody answers questions: decide by the state file and this schema, or end the phase with the question in the
  final message and nothing left uncommitted (added 2026-11-04). Every phase ends with a commit, also one that changed
  nothing (an integration with nothing to integrate): its log entry says so, because the loop reads a phase without a
  commit as stuck and stops (added 2026-11-07, after an empty phase stopped the loop in the sibling chatgpt wiki).
  Subagents write their full reports to the cache folder and return one line.
- The main agent's own context grows with every call too, so it holds only what coordinating needs: file lists, `--stat`
  summaries and subagents' one-line reports, never whole pages, diffs or check output. Validation runs outside it (next
  item). The main agent wakes only when a subagent finishes: it relies on a completion notice where the agent gets one,
  and otherwise waits with the longest timeout available, never with short repeated checks. Batch size and the number of
  subagents at once go in the batch state file, so any agent that continues the batch uses them (rule added 2026-11-02,
  after the orchestrator used half to two thirds of two batches' tokens in the sibling chatgpt wiki).
- Validation is bounded like integration (rule added 2026-11-04, after validation subagents in the sibling chatgpt wiki
  used 6–13M tokens per batch, as much as the orchestrator, mostly at contexts over 120k: each held a whole batch's
  pages and then ran the checks on top). Reviewers start fresh from `tools/validator-brief.md`, never from a copy of the
  orchestrator's context. Each reviews at most about 3 papers' new pages (reading) or one integrator group's pages
  (integration), writes its findings to the cache folder and returns one line. Checks run in a context that holds no
  page content: their output goes to files and only summary lines are read. A failure goes to a fresh subagent with only
  the failing items. Every agent waits on a long command with the longest timeout available.
- Integrators read the briefs and the pages they own, not PDFs or the index.

**Bounded reads** (rules added 2026-11-01 so that the cost of ingesting a paper does not grow with the wiki):
- Readers read `tools/reader-brief.md` and their paper, and skip the session protocol (§8.1). Integrators read
  `tools/integrator-brief.md`, and validators `tools/validator-brief.md`.
- A reader's link candidates come from a search for its paper (about the top 15), never a full list of pages.
- Read an existing source page head first (TL;DR, key contributions, section map), then only the sections or part
  notes needed, unless auditing it.
- Command output is bounded: list files (`grep -l`), cap matches (`grep -m`, `| head`), or use `tools/search.py`;
  never print every matching line across the wiki or the briefs. The main agent extracts the brief claims aimed at
  each integrator's pages into one file per integrator.
- Batch queues, inventories, briefs and the orchestrator's state live in a cache folder outside the wiki, never in
  wiki pages. The orchestrator records its batch state in a small file there and starts fresh per batch or phase.
  The session that completes the batch deletes that folder after its commit, once anything worth keeping is in the
  wiki or the log; an incomplete batch keeps it until it resumes or the user drops it (rule added 2026-11-02).
- Review the diff of hand-written pages (in a batch, the reviewers do, §8.2b). Check generated files
  (`index.md`, `sources:` lists) with `git diff --stat`.

### 8.3 Query

Find pages by search: `qmd` where it is set up, otherwise `tools/search.py`, with several phrasings (tools/README.md, section "Schema details").
Search results are leads: read the pages themselves before answering. Use `catalog.py --nav` (the index
preamble and Topics) for orientation; find sources by search, never by reading the whole index. Pick pages, follow links one hop. Go back to Zotero only when the
wiki lacks the detail, and then improve the wiki. Answer with citations down to source pages, keeping scope; say what
the wiki does not cover and which Zotero items would. Offer to file substantive answers in `analyses/` (file them
automatically if the user has said so). Log the query.

### 8.4 Lint

1. `wikilint.py` (its header lists the errors and warnings it checks).
2. `zot.py changed --queue`; handle each change by kind; work through `pending.md`. Tool changes go through the skill
   (§12), never straight into `tools/`.
3. `zot.py coverage <collection> --recursive` for each topic.
4. **Read for**: claims that lost their scope or rest on one source; `open` contradictions newer sources may resolve;
   superseded claims; concepts on ≥ 2 pages without a home; pages that no longer earn their file; syntheses that lag;
   `metadata` or `abstract` sources worth a full read.
5. Fix mechanical issues, present judgment calls, log the pass with counts.

### 8.5 Claim audit

Lint checks structure; only an audit checks the knowledge. Run one after a substantial ingest or synthesis revision,
before the user relies on an important conclusion, or when asked.

Sample about 10 claims and record how they were drawn, trace each to the rendered PDF page it cites, record typed
findings and a verdict per claim, keeping confirmed and unchecked items apart, then fix and propagate (§4, including
`review.py restated`) and save the audit as `analyses/<date>-claim-audit.md`. Finding types and verdicts: tools/README.md, section "Schema details".

### 8.6 Schema change

Propose the edit, apply it after the user agrees, migrate existing pages, add a lint check where the rule is
checkable, and log it as `schema`. Prefer an automated check to another prose rule. Once the first few ingests
and an audit have run, propose **freezing the schema**: from then on, change it only when an actual ingest, sync or audit
fails, and name that failure in the log entry. Rules accumulate faster than they pay for themselves.

## 9. `index.md`

`catalog.py --apply` generates every line of `index.md` below its editorial preamble, from each page's `summary:`
and heading. Never edit index lines by hand. Agents read the index only through `catalog.py --nav` (§8.1) and find
pages by search (§8.3), so it is not split by size. Line format: tools/README.md, section "Schema details".

## 10. `log.md`

Append-only, newest at the bottom; never rewrite past entries (append a `fix`). Headers: `## [YYYY-MM-DD] <op> |
<subject>`, op ∈ `setup | ingest | reingest | query | file | lint | schema | fix`. Body: 2–10 bullets with Zotero keys,
pages created (`+`) and updated (`~`), disagreements and their resolution, open findings, claim-neutral edits not
propagated, and `next:` lines. Append an entry without reading the file (a shell append or a tool), and find past
entries by searching it.

## 11. Writing style

- Write for the user: {{AUDIENCE}} Be precise; skip textbook padding.
- Paraphrase. Numbers with units, systems and conditions. Math in LaTeX with the paper's notation, symbols defined.
- Keep pages focused; split pages that cover two ideas and merge near-duplicates.
- **Size limit**: every page stays under 40,000 bytes (about 10k tokens), because integrations, reviews and audits read
  whole pages. Split oversized pages with `split.py`, which moves sections verbatim (claim-neutral). Historical
  analyses marked `frozen: true` are exempt. Details: tools/README.md, section "Schema details".
- Synthesis is the point of the wiki. Mark it `> [!synthesis]` when it goes beyond any one source, and cite its premises.

## 12. Co-evolution and open decisions

- **Revision history**: {{GIT_LOCATION}}; push on request (tools/README.md).
- **Tools are maintained in the installed skill** (`{{SKILL_DIR}}`): change them there first, test, then upgrade
  this wiki (tools/README.md, section "Schema details").
- **YAML parsing**: a strict, tested parser for the frontmatter subset, so the tools stay dependency-free under
  `python3 -I`. Revisit if the frontmatter outgrows the subset.
- **Search tools**: `qmd` (optional), keyword plus vector search with reranking, run locally, with its index in
  `.qmd` at the wiki root (git-ignored; a link to a folder outside cloud sync when this folder is synced); and
  `tools/search.py`, keyword ranking (BM25) with the standard library only, for machines or agents without qmd.
- **Ingest cost** grows with the wiki unless each step loads a bounded amount: readers get one paper per fresh
  context and a short brief (§8.2b), orientation is the Topics list from `catalog.py --nav` (§8.1), pages are found by
  search, append-only files are written by tools (§10), additive edits do not propagate and reviews read citing
  sentences first (§4), lint details only changed pages, and every page stays under 40,000 bytes (§11). Integrators own
  at most about 10 pages, groups run in waves within any limit on subagents, and the main agent works one phase per
  session (§8.2b).
- **People and groups as entities**: only if they recur in ≥ 3 sources.
- **Group libraries**: `zot.py` reads the user library only; extend it before ingesting from a group.
