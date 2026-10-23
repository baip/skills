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

## 8. Known limits

- One user library only; group libraries need `zot.py` extended to `/api/groups/<id>`.
- File locks use `fcntl` (macOS, Linux, WSL). Do not run the tools on one wiki from two machines at once.
- Wikis in a cloud-synced folder need the git directory outside it (`--git separate:PATH`).
- Figure-level reading coverage (which figure supported which claim) is recorded only in prose reading histories.
