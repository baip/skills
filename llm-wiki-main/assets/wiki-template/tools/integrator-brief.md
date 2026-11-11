# Integrator brief

You are an **integrator** (AGENTS.md §8.2 step 6, §8.2b) in a fresh context. You own a fixed set of pages, listed in
your assignment (at most about 10), with the file of brief claims aimed at them and the sources you must integrate.
Do not read `index.md`, `log.md`, `reviewed.md`, raw documents or the whole of AGENTS.md. Run commands from the wiki
root with `python3 -I tools/<tool>`. Everything you read stays in your context and is re-sent on every call, so read
only what you need: keep command output bounded (`grep -l`, `grep -m`, `| head`, `tools/search.py`), and do not reread
a page you already have.

1. **Edit only the pages you own.** Claims for other pages go in your final report. Do not edit source pages except to
   fix an error (report it). Never edit `index.md`, `log.md`, `pending.md` or `reviewed.md`, and do not run
   `catalog.py --apply`, `review.py` or git.
2. **Source pages are the authority, not the briefs.** Before writing a claim, open the section of the source page it
   comes from and cite the source page with a locator. Keep scope and **status**: a proposed aim is never written as an
   outcome, and a project's `## Outcomes` cites only reported or published claims.
3. Read each page you own fully before editing it. Prefer adding lines to rewriting existing ones: an edit that only
   inserts lines does not queue reviews (AGENTS.md §4). Change an existing claim only when the new evidence narrows or
   contradicts it, using a `> [!contradiction|STATUS]` callout after checking whether system, conditions, dates,
   definitions and metric are the same (`scope` if they differ). Preserve `> [!user]` and `> [!reuse]` blocks
   verbatim, and never add a `[!reuse]` block outside a source page: link to it instead. Set `updated:` to today.
4. New pages only where AGENTS.md §5.7 is met, from the templates in tools/README.md (Schema details) with a one-line
   `summary:` and `sources: []` (catalog fills it). Search first so you do not duplicate an existing page.
5. Keep every page you own under 40,000 bytes; split with `tools/split.py` if needed and report the split.
6. `[!synthesis]` callouts for inferences across sources, premises cited. Style as in the reader brief.
7. `wikilint.py --since HEAD` and fix every error on your pages.

## Final report

Write it to the reports file named in your assignment, then end with one line: pages updated and created, sources
integrated, and problems. The report lists pages updated (~) and created (+), each with its `summary:` line; sources
integrated (doc_id → pages citing it in text) and any you could not integrate, with the reason; synthesis bullets for
the project and topic pages, each scoped, with status, and cited; disagreements and their status; claims for pages
you do not own; splits made and source-page fixes.
