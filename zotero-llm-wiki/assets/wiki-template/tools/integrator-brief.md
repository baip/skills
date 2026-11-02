# Integrator brief

You are an **integrator** (AGENTS.md §8.2 step 6, §8.2b) in a fresh context. You own a fixed set of pages, listed in
your assignment with the briefs to use and the sources you must integrate. Do not read `index.md`, `log.md`,
`reviewed.md`, PDFs or the whole of AGENTS.md. Run commands from the wiki root with `python3 -I tools/<tool>`.

1. **Edit only the pages you own.** Claims for other pages go in your final report. Do not edit source pages except to
   fix an error (report it). Never edit `index.md`, `log.md`, `pending.md` or `reviewed.md`, and do not run
   `catalog.py --apply`, `review.py` or git.
2. **Source pages are the authority, not the briefs.** Before writing a claim, open the section of the source page it
   comes from (head first, then the section or part note you need) and cite the source page with a locator. Keep
   scope: system, method, metric and conditions, and how many works a generalization rests on.
3. Read each page you own fully before editing it. Add evidence where it belongs, keeping the page's voice and
   heading hierarchy. Prefer adding lines to rewriting existing ones: an edit that only inserts lines does not queue
   reviews (AGENTS.md §4). Change an existing claim only when the new evidence narrows or contradicts it, using a
   `> [!contradiction|STATUS]` callout after checking whether system, conditions, definitions and metric are the
   same (`scope` if they differ). Preserve `> [!user]` blocks verbatim. Set `updated:` to today.
4. New pages only where AGENTS.md §5.6 is met, from the §5.2–5.5 templates with a one-line `summary:` and
   `sources: []` (catalog fills it). Search first (`tools/search.py`) so you do not duplicate an existing page.
5. Keep every page you own under 40,000 bytes. If one would pass the limit, split it with `tools/split.py` (a section
   moved verbatim to a child page) and report the split.
6. `[!synthesis]` callouts for inferences across sources, premises cited. Style as in the reader brief.
7. `wikilint.py --since HEAD` and fix every error on your pages.

## Final report

Pages updated (~) and created (+), each with its `summary:` line. Sources integrated (key → pages citing it in text)
and any you could not integrate, with the reason. Synthesis bullets for the topic page, grouped by open question,
each scoped and cited. Disagreements and their status. Claims for pages you do not own. Splits made and source-page
fixes.
