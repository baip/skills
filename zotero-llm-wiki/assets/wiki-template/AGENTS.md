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
   extracted text only, figures unseen and equations unverified · `mixed`, say which · `none`), plus optional
   `supplement` (`read` · `skimmed` · `not-read`: it exists but was not read, or is not attached in Zotero · `none`: the
   work has no supplement). Never write a claim from a part you did not read.
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
├── sources/      # one page per Zotero item: <citekey>.md
├── concepts/     # general ideas, methods, phenomena
├── entities/     # named things: models, codes, datasets, benchmarks
├── topics/       # synthesis hubs, usually mirroring a Zotero collection
├── analyses/     # filed answers, comparisons, audits; assets/ holds charts the agent made
└── tools/        # zot.py, review.py, catalog.py, wikilint.py, relink.py, wikimeta.py, test_tools.py, README.md
```

- No other top-level folders without a schema change. Flat folders; page names unique across folders.
- **Concept vs entity:** an entity has a proper name (a named model, method, dataset, instrument, code, organism, site or
  benchmark); a concept is a general idea, phenomenon or method class.
- **Topics** are the evolving-thesis pages, each listing the Zotero collection(s) it mirrors.
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
- **Review.** When a page's content changes, its dependents may be stale. They are queued in `pending.md`, each item
  with a **cause** (what changed, at which revision):
  - a changed **source** queues its direct dependents, and through source pages that quote it, theirs;
  - a changed **concept, entity, topic or analysis** page queues only its direct dependents;
  - a reviewed page propagates further only if the review changed it (`review.py touched` or `since`);
  - a **claim-neutral** edit (a locator, a typo, wording that keeps the meaning) is not propagated: pass it to
    `review.py since --neutral` and list it in the log;
  - **a corrected claim is also searched for by its wording.** Citation links miss pages that restate the same
    conclusion from the same sources without citing the corrected page. After correcting a claim, run
    `review.py restated PAGE --phrase "…"` with the key phrases of the *old* wording (2–3 distinctive phrases, numbers
    or locators), and review what it queues like any other item.

  Resolve each item with an outcome and its basis (`review.py done`): *corrected* (the page was changed), *unchanged*
  (it uses the revised content and still holds), or *not-affected* (it does not use the part that changed). The basis
  names what was checked, such as the sentences that cite the changed page; a keyword search may choose what to read
  but is not a basis. Resolutions go to `reviewed.md` and are never re-queued. `--strict` lint fails while items are open.
- **Versions of one work** (preprint and published) keep separate pages. The earlier page sets `version_of:` and
  records only what differs; cite the later one. **Count works, not pages** (§6.8), and suggest merging in Zotero.

## 5. Page types and templates

Frontmatter uses the YAML subset `tools/wikimeta.py` parses: `key: value` lines with plain or quoted scalars, flow
lists `[a, "b, c"]` and flow maps `{K: "v"}`. Quote any list element that contains a comma. Required fields are marked *.
Fields marked *generated* are written by tools, never by hand.

### 5.1 Source page — `sources/<citekey>.md`

```yaml
---
type: source*
title: "…"*
authors: ["Smith, J.", "Doe, A."]*      # quoted; first 5, then "et al."
year: 2021*
venue: "J. Example 12(3), 345–367"*
item_type: review*            # review | article | preprint | book | chapter | thesis | software | dataset | conference
library: {{LIBRARY}}*        # user:<id> or group:<id>
zotero_key: ABCD1234*
citekey: smithExampleStudyTitle2021*
zotero_uri: zotero://select/library/items/ABCD1234*   # groups: zotero://select/groups/<id>/items/<key>
zotero_fingerprint: "v3 …"*   # generated by zot.py stamp
zotero_checked: 2026-01-01*   # generated by zot.py stamp
attachment_key: EFGH5678      # the PDF read
doi: 10.xxxx/…
collections: ["Path/To/Collection"]*
zotero_tags: [_review, ML-FF]
read_depth: full*
read_mode: rendered*
supplement: not-read
version_of: <later citekey>
ingested: 2026-01-01*
updated: 2026-01-01*
tags: [topic-tag, method-tag]
---
```

Body, in order: `# <Short title> (<First author> <year>)` with a **TL;DR**; `## Open in Zotero` (item link and a section
map of `zotero://open-pdf/library/items/<attachment_key>?page=N` links, N = 1-based PDF page index); `## Key
contributions` (3–7 bullets); `## Methods / setup`; `## Results and claims` (each with scope and locator); `## Limitations
and caveats` (the authors', then the agent's, marked); `## Connections` (links here are not evidence); `## User notes`
(the user's emphasis, `> [!user]` blocks, and a `> [!note] Reading history` with dates and exactly what was read).

### 5.2–5.5 Other pages

| Type | Frontmatter | Body |
|---|---|---|
| concept `concepts/<name>.md` | `type`*, `aliases`, `tags`, `sources`* (generated), `created`*, `updated`* | definition paragraph; `## Details`; `## Variants / approaches`; `## Evidence and debates`; `## Open questions`; `## Related` |
| entity `entities/<name>.md` | as concept, plus `entity_kind`* (`model \| method \| software \| dataset \| benchmark \| instrument \| material \| organism \| site \| group \| person`) | what it is; `## Key facts`; `## How it fits`; `## Reported performance and issues`; `## Sources` |
| topic `topics/<name>.md` | `type`*, `zotero_collections`* (`{KEY: "path"}`), `sources`* (generated), `created`*, `updated`* | `## Scope` (the mirrored collections, then coverage by state from `zot.py coverage --recursive`, as a line or a table); `## Current synthesis` (what the wiki believes, by open question); `## Map`; `## Timeline`; `## Open questions and tensions`; `## Reading queue` (each with a reason) |
| analysis `analyses/<yyyy-mm-dd>-<slug>.md` | `type`*, `question`* (verbatim), `sources`* (generated), `created`* | the answer, tables, charts in `analyses/assets/`, the pages relied on |

`sources:` is exactly the source pages the body cites; `tools/catalog.py --apply` derives it.

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
- **Reading a paper means viewing its rendered PDF pages.** The text index is for searching and exact quotes only;
  never filter or truncate it. If a PDF cannot be rendered, read the text index and record `read_mode: text-index`.
  Without a PDF, record `abstract` or `metadata-only`. Never copy a PDF.

## 8. Workflows

### 8.0 Route every message

**ingest** (8.2), **query** (8.3), **lint** (8.4), **audit** (8.5), **schema** (8.6) or **meta** (answer; log only if
files changed). When in doubt, a query. Mixed requests: in order, each logged.

### 8.1 Session start

`git status` (§2.10); read `pending.md`, `index.md` and the last five log headers; `zot.py status` if Zotero is needed.

### 8.2 Ingest

**States** (derived, never asserted): *none* (no page) · *metadata* (abstract or metadata-only) · *read* (full or
partial, but no concept, entity or topic page cites it in its text) · *integrated* (cited in such text). *Integrated* is
a structural proxy; the semantic check is integration itself and the claim audit.

**Complete** when every item is integrated or metadata with a reason, the topic synthesis reflects the new evidence,
`index.md` and `log.md` are updated, and strict lint passes. Otherwise the log calls the ingest *incomplete*.

**Modes.** *Guided* (default for one or a few items): discuss (step 4) before writing (step 5). *Delegated* (a batch, or
"proceed"): skip step 4 and record under `## User notes` that there was no discussion, the date, whether Zotero has notes
or annotations, and what the page stresses and why; use §8.2b for more than about 5 items.

1. **Identify** the item (`zot.py item`) and **check its state**; an existing page means a re-ingest or resume.
2. **Gather** metadata, the user's notes and annotations, and the PDF.
3. **Read** the rendered pages. Record the section→page map, transcribe equations, note what was not read.
4. *(Guided)* **Discuss**: 3–6 takeaways, pages to touch, tensions with the wiki. Ask what to emphasize and record it
   under `## User notes`.
5. **Write the source page**, then `zot.py stamp`.
6. **Integrate**: update the pages the source bears on, keeping scope; create pages only by §5.6; check disagreements
   for scope; `zot.py search` cited works and link those in Zotero with `↗`; run `relink.py --apply`.
7. **Propagate and check**: `review.py since <start revision> --queue`; review and resolve; repeat until nothing new.
   Then `catalog.py --apply`, update `index.md` and `log.md`, and lint.
8. **Report** what changed in the wiki's understanding, the disagreements found, and 1–3 next ingests. Clean up temp files.

### 8.2b Batch ingest (subagents)

For more than about 5 items: inventory the items and their states; **reader** subagents do steps 1–5 and write only
their own source pages, returning an integration brief per paper (claims per target page with locators and scope,
tensions, evidence on open questions, reading-queue candidates); after all readers finish, **integrator** subagents
each own a disjoint set of pages; the main agent alone writes the topic synthesis, index and log. Details in tools/README.md.

### 8.3 Query

Read `index.md`, pick pages, follow links one hop. Go back to Zotero only when the wiki lacks the detail, and then
improve the wiki. Answer with citations down to source pages, keeping scope; say what the wiki does not cover and which
Zotero items would. Offer to file substantive answers in `analyses/` (file them automatically if the user has said
so). Log the query.

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

1. **Sample** about 10 claims from the topic synthesis and concept pages, favoring quantitative claims, verdicts,
   headings and single-source claims. Record how the sample was drawn.
2. **Trace** each claim to the source page and then to the rendered PDF page it cites.
3. **Record every finding**, typed: *transcription* (a number, unit or equation differs) · *scope* (a system, condition,
   comparator or metric dropped) · *attribution* (wrong source, or secondary cited as primary) · *inference* (a
   conclusion the scoped evidence does not support) · *locator*. The **verdict** is the most serious finding:
   *supported* · *scope-narrowed* · *misattributed* · *unsupported* · *not checkable* (no PDF, no SI, ambiguous locator;
   inability to verify, not evidence against). Check conclusions as well as numbers. Keep confirmed and unchecked items
   apart in the report.
4. **Fix and propagate** (§4), including `review.py restated` for each corrected claim, and save the audit as
   `analyses/<date>-claim-audit.md`.

### 8.6 Schema change

Propose the edit, apply it after the user agrees, migrate existing pages, add a lint check where the rule is
checkable, and log it as `schema`. Prefer an automated check to another prose rule. Once the first few ingests
and an audit have run, propose **freezing the schema**: from then on, change it only when an actual ingest, sync or audit
fails, and name that failure in the log entry. Rules accumulate faster than they pay for themselves.

## 9. `index.md`

Sections in order: Topics, Sources, Concepts, Entities, Analyses. One line per page, alphabetical (sources by first
author, then year): `- [[page|Display]] — one-line summary · <metadata>`. The header counts and the metadata (sources:
`· <collection> · <read_depth>`; others: `· <n> sources`) are generated by `catalog.py`; summaries are editorial.
Propose splitting the index past about 300 pages.

## 10. `log.md`

Append-only, newest at the bottom; never rewrite past entries (append a `fix`). Headers: `## [YYYY-MM-DD] <op> |
<subject>`, op ∈ `setup | ingest | reingest | query | file | lint | schema | fix`. Body: 2–10 bullets with Zotero keys,
pages created (`+`) and updated (`~`), disagreements and their resolution, open findings, claim-neutral edits not
propagated, and `next:` lines.

## 11. Writing style

- Write for the user: {{AUDIENCE}} Be precise; skip textbook padding.
- Paraphrase. Numbers with units, systems and conditions. Math in LaTeX with the paper's notation, symbols defined.
- Keep pages focused; split pages that cover two ideas and merge near-duplicates.
- Synthesis is the point of the wiki. Mark it `> [!synthesis]` when it goes beyond any one source, and cite its premises.

## 12. Co-evolution and open decisions

- **Revision history**: {{GIT_LOCATION}}; push on request (tools/README.md).
- **Tools are maintained in the installed skill** (`{{SKILL_DIR}}`), so one copy stays the source and fixes reach every
  wiki made from it. To change a tool: edit it in `{{SKILL_DIR}}/assets/wiki-template/tools/`, run
  `python3 -I {{SKILL_DIR}}/assets/wiki-template/tools/test_tools.py`, commit there if the skill is a git clone, then run
  `python3 {{SKILL_DIR}}/scripts/init_wiki.py --upgrade-tools .` here (it tests, logs and commits). `wikilint.py` warns
  (`tools`) while `tools/` differs from the skill or the skill is missing.
- **YAML parsing**: a strict, tested parser for the frontmatter subset, so the tools stay dependency-free under
  `python3 -I`. Revisit if the frontmatter outgrows the subset.
- **Search tool** (e.g. `qmd`): propose one when the index and grep stop being enough (roughly past 150–300 pages).
- **People and groups as entities**: only if they recur in ≥ 3 sources.
- **Group libraries**: `zot.py` reads the user library only; extend it before ingesting from a group.
