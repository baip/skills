# Design notes

Why the schema in `assets/wiki-template/AGENTS.md` looks the way it does. It was developed on a 140-page wiki built from
77 papers in one Zotero collection, through six rounds of external review and four claim audits. Read the section that
matches the question; nothing here is needed for routine work.

## Contents

1. Layers and the read-only rule
2. Reading: rendered pages, and honesty about depth
3. Identity and provenance
4. Review propagation
5. Claim audits, and what they found
6. Generated bookkeeping
7. Keeping the schema small
8. Known limits

## 1. Layers and the read-only rule

Three layers: Zotero holds the sources (owned by the user), the wiki holds the agent's compiled knowledge, and the schema
is shared. The agent never writes to Zotero because the library is the user's long-term record and other tools (citation
managers, sync, group libraries) depend on it. The client sends only GET requests to the local API, plus one read-only
Better BibTeX call for citation keys. Changes the library needs are suggested, never made.

No raw content is duplicated, for two reasons: copyright, and drift (a copied abstract goes stale when the user corrects
the item). Short quotations with locators and paraphrased numbers are enough for a wiki.

## 2. Reading

The first version read Zotero's full-text index. It drops figures, scrambles tables and loses equations, and an early
filter that dropped short lines silently removed content. The rule now is to view rendered PDF pages, with the text index
used only for search and exact quotations. Each source page records `read_depth` (full / partial / abstract /
metadata-only) and `read_mode` (rendered / text-index / mixed / none) separately, because "read" without both is
unverifiable. Claims may come only from parts that were read; an unread supplement can be cited only where the main text
states its result, and then as such. Books over 150 pages are the exception to the complete-read default: in the source
wiki, 13 textbooks would have meant about 11,000 pages, and each batch needed a one-off decision that no other agent
could repeat. They are read by chapter (the user chooses in guided mode, relevance to the collection otherwise), and
the page records the whole chapter map so that unread chapters stay visible.

## 3. Identity and provenance

- Identity is `(library, zotero_key)`; keys are unique only within a library, and qualifying them keeps a later merge of
  two wikis cheap. Filenames are citation keys because users cite from LaTeX.
- Each source page carries a content fingerprint of five parts (bibliographic fields, abstract, PDFs, notes,
  annotations). `zot.py changed` sorts changes into a *metadata refresh* (bibliography only) and a *scientific re-read*
  (anything else). A fingerprint is read as one snapshot between two reads of the library version, so a change cannot
  slip between comparing and stamping; an incomplete fingerprint certifies nothing.
- The user's notes and annotations are part of the fingerprint because they are the highest-signal input the wiki gets.

## 4. Review propagation

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

## 5. Claim audits

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

## 6. Generated bookkeeping

`sources:` lists and index counts were maintained by hand and drifted (two counts were wrong when first generated).
`catalog.py` now derives them; lint warns when they are stale. Index summaries stay editorial.

## 7. Keeping the schema small

The schema grew to 5,300 words in one day of reviews, with machinery added before any real Zotero change had gone
through it. Two lessons: move mechanics (formats, algorithms) to `tools/README.md` and keep policy in `AGENTS.md`; and
once the first ingests and an audit have run, freeze the schema and change it only when an actual ingest, sync or audit
fails, naming that failure in the log. The restatement rule is an example of a change that passed that test.

## 7b. Ingest cost grows with the wiki (2026-11-01)

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

## 7c. Integration dominates a batch (2026-11-02)

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

## 7d. The orchestrator becomes the cost (2026-11-02)

Once readers and integrators were bounded, the orchestrator was the largest consumer. In two 8-paper batches of a
sibling wiki it used 46 % and 64 % of the tokens: 95–163 calls per phase at a mean context of 95–151k tokens, against
56–71k for readers and integrators. Most calls were checks on running subagents, each resending the whole context,
and whole diffs or files it read to review the work. An orchestrator's cost per phase is roughly fixed, so it weighs
most on small batches: in the 51-paper batch of section 7c it was about 11 %. The rules now keep its context small:
it reads only file lists, `--stat` summaries and one-line reports, a fresh validation subagent runs the checks and the
diff review, and it wakes only when a subagent finishes. The rules are stated for any agent. The same wiki is run by
different agents, which notify, poll or block in different ways, so only the goal is fixed.

Measured over the next ten 8-paper batches of the same wiki (batches 200–209, 2026-11-03 to 2026-11-04), the
orchestrator used 7–12M tokens per batch (21–28 %) against 24–36M (46–62 %) before, in 112–174 calls per batch against
237–255, at a mean context of 51–93k per phase against 97–152k. A batch fell from 52–57M to 32–51M tokens (mean 39M,
about 28 % less) and, on the one account whose weekly quota could be read, from about 23 to about 17 weekly percentage
points. About two fifths of the orchestrator's saving went to the validation subagents that took over the checks and
diff reviews: 6–13M tokens per batch, at a mean context of 108k, more than a reader's 76k. They are the next candidate
for bounding. The baseline is only two batches and the papers differ, so the total saving is less certain than the
orchestrator's, whose ranges do not overlap.

## 7e. Validation becomes the cost (2026-11-04)

With the orchestrator bounded, the validation subagents that took over its checks and diff reviews cost as much as it
did: 6–13M tokens per batch in ten batches of the zotero-chatgpt wiki. Each held a whole batch's notes, records and
reports, or every integrator's diff, then ran the build, checks, tests and search-index refresh on top of that load, so
most of its calls ran above 120k tokens, and seven started as forks of the orchestrator's context. Validation is now
split like integration: reviewers of about 3 papers or one integrator group each, in fresh contexts from a short brief,
and checks in a context that holds no page content. The review standard is unchanged: every new or changed hand-written
page is still reviewed in full, against its reader report or the source page it cites. A reviewer no longer sees other
groups' diffs, but each still checks claims against the source pages, where a conflict between groups shows up as a
mismatch.
Expected saving, not yet measured: about half of validation, some 5M tokens per batch.

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
tokens per phase. The brief names only the state file's scalar fields and itself.
The same runs added one rule: every phase commits, even one that changed nothing, because the headless loop reads a
phase without a commit as stuck.

Measured on the zotero wiki's next batch (Mathematics, 60 records of which 33 were read, 2026-11-07, against the
39-paper batch the same morning): the orchestrator's context at its tenth call fell from 68–78k tokens to 36–41k, and
its mean context from 89k to 53k in reading and from 82k to 63k in integration. The reading orchestrator used 7.1M
tokens against 13.7M. The integration orchestrator used 10.6M against 9.2M, because it coordinated 31 subagents instead
of 14. Synthesis was unchanged at a mean context of 108k (peak 162k), since the orchestrator writes the topic pages
itself. The batch still used 174M tokens against 125M. Readers fell from 1.6M to 0.8–1.0M each (27 of the 60 records
were abstract or metadata only), but propagating the claim audit's corrections to two source pages took 21.6M (12 % of
the batch): 239 review items over three passes went to about 30 fresh subagents, inside the synthesis session, and 180
of the items were not-affected, 41 unchanged and 18 corrected.

Two changes followed the same day. A screener reads `review.py screen`, which prints each cause page's changed lines
once and then each dependent's citing lines (about 21k tokens for that batch's first 189 items), and resolves the items
whose citing lines do not use the change in one `review.py resolve` call, before resolvers open any page. The
propagation of the synthesis's corrections became a phase of its own in a fresh session. Their effect is not yet
measured.

## 8. Known limits

- One user library only; group libraries need `zot.py` extended to `/api/groups/<id>`.
- File locks use `fcntl` (macOS, Linux, WSL). Do not run the tools on one wiki from two machines at once.
- Wikis in a cloud-synced folder need the git directory outside it (`--git separate:PATH`).
- Figure-level reading coverage (which figure supported which claim) is recorded only in prose reading histories.
