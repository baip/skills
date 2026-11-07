# Orchestrator brief

You coordinate one batch phase (AGENTS.md §8.2b) in a fresh session, usually started with "Continue ingestion". This
brief replaces the session protocol (§8.1), `tools/README.md`, and the skill's SKILL.md and references for you.
AGENTS.md remains the authority. Everything you read stays in your context and is sent again with every later call,
about 80 times per phase, so read only what this brief names.

## Start

1. `git status --short`. Uncommitted changes you were not resumed into are pre-existing: stop and report them (§2.11).
2. Find this wiki's batch: `ls -d ~/.cache/llm-wiki/<wiki>/*/`, where `<wiki>` is this folder's name. With no folder,
   nothing is pending: start a new batch if the user named files or folders (§2.2), otherwise say there is nothing to
   ingest and stop without a commit.
3. Read only the state file's scalar fields: `jq 'with_entries(select(.value | type != "array"))' <folder>/state.json`.
   Read a list (items, groups) only when you launch the subagents that need it. If the state says no readable item is
   left, report that and stop without a commit. This is the one stop without a commit, and it ends a headless loop on
   purpose.
4. Do not read SKILL.md, the skill's references, `tools/README.md`, `pending.md`, the index, the log or the subagent
   briefs, and do not search workspace memory: the state file and this brief are the handoff. Subagents read their own
   briefs: give them the path.

## New batch

1. Inventory: `python3 -I tools/docs.py ls <named path> --recursive > <folder>/inventory.txt`, then read only its last
   lines (the counts). Documents in *read* or *metadata* are included for integration, not skipped.
2. A document already *metadata* because it could not be read (missing, corrupt, password-protected, no converter) is
   not batched again unless `docs.py changed` reports its file changed or the user asks. A new document that cannot be
   read still gets a reader, which records it *metadata* with the reason.
3. Write `<folder>/state.json`: the wiki path, phase, start revision, documents, batch size, subagents at once (the
   user's, or the agent's limit), the fixed vocabulary of planned slugs, cache paths and the next phase's instructions.
   The orchestrator's cost per phase is roughly fixed, so a request that fits one reading phase can be one batch.

## Both phases

- Every subagent starts fresh, never as a fork of your context. Its prompt names its brief (`tools/reader-brief.md`,
  `tools/integrator-brief.md` or `tools/validator-brief.md`), its assignment (documents or pages, start revision, cache
  paths, report file, slug vocabulary) and today's date. It writes its full report to `<folder>/reports/` and returns
  one line.
- Run at most the state file's number of subagents at once, in waves. Wake only on a subagent's completion notice, or
  wait with the longest timeout available, never with short repeated checks.
- Hold only file lists, `git diff --stat` and one-line reports. Never read pages, briefs, diffs or check output
  yourself.
- **Validation.** Reviewers (validator brief, role reviewer) take about 3 documents (reading) or one integrator group
  (integration) each, and may start as soon as their files exist. Then one checks runner (same brief) runs `catalog.py
  --apply`, `review.py since <start revision> --queue`, `wikilint.py --since <start revision>`, `test_tools.py` when
  tools changed, `docs.py clean`, and, where qmd is set up, `qmd update && qmd embed && qmd cleanup` (an embedding
  failure inside a sandbox is a reported limit, not an error to repair). Failures and open review items go to a fresh
  subagent with only those items, until none remain.
- **Commit.** Every phase ends with a commit, also one that changed nothing in the wiki: its log entry says so. Append
  one log entry without reading the log (`## [YYYY-MM-DD] ingest | <subject>` and 2–10 bullets, §10), stage the phase's
  paths by name (never `git add -A`) and commit with the entry's subject. Update the state file with a self-contained
  next phase (phase, start revision, documents or groups, cache paths). Then stop, telling the user to start a fresh
  session with "Continue ingestion".
- **Headless runs** (started by the skill's `scripts/continue_ingestion.py`): nobody answers questions. Decide by the
  state file, this brief and AGENTS.md, or end the phase with the question in your final message and nothing left
  uncommitted.
- **Interruptions.** After a stop or a usage limit, filed pages are the checkpoint. Start fresh subagents for unfiled
  documents, never resume old ones, and do not re-read filed documents.

## Reading phase

1. One reader per document: its path, the project it belongs to, the cache folder, the slug vocabulary and the date. The
   reader reads the document, writes and stamps its source page, and writes its integration brief to the cache folder
   before ending. Never give a reader a second document. Long documents are read in part (§8.2 step 3).
2. Filed documents leave the batch queue. Reviewers, then the checks runner, as above. Commit, with the next phase set
   to integration.

## Integration phase

1. A planning subagent (fresh) reads the new source pages' heads and the readers' integration briefs, groups the target
   pages into disjoint groups of at most about 10 pages, and writes per group a file list and an extract of only the
   brief claims aimed at those pages. You read only its plan summary.
2. One integrator per group, in waves. Integrators treat source pages as the authority and report index lines, synthesis
   bullets by open question, and unresolved problems.
3. One reviewer per group, then the checks runner. Commit, with the next phase set to synthesis.

## Synthesis phase

1. You write the topic synthesis yourself (§8.2b), from the integrators' synthesis bullets in `<folder>/reports/` and
   the topic and project pages they concern. These are the only pages you read.
2. After a substantial ingest, a claim audit (§8.5) of about 10 claims runs in fresh subagents.
3. A reviewer for the topic pages, then the checks runner, until strict lint passes (§2.8). Commit with the batch's
   report (§8.2 step 8), delete the batch folder and run `docs.py clean`. The batch is complete.

## When to open more

Open a file only for its case, and only the section you need: `tools/README.md` "Batch runs" for mechanics this brief
leaves out, "Schema details" for page templates, AGENTS.md §8.5 for an audit. Readers, not you, need the document access
and rendering procedure (§7).
