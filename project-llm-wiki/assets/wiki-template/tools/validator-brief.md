# Validator brief

You validate one part of a batch (AGENTS.md §8.2b) in a fresh context, as a **reviewer** or as the **checks runner**.
Your assignment names the role, the files, the start revision and the cache folder. Do not read `index.md`, `log.md`,
`reviewed.md`, raw documents or the whole of AGENTS.md, and do not take work outside your assignment. Run commands
from the wiki root with `python3 -I tools/<tool>`. Everything you read stays in your context and is sent again with
every later call, so keep command output bounded (`grep -l`, `grep -m`, `| head`) and read each file once.

## Reviewer

You review at most about 3 documents' new source pages (reading phase) or one integrator group's pages (integration).

- **Reading phase.** Read each source page and its reader report or brief in the cache folder. Check that
  `read_depth` and `read_mode` match what the report says was read, that nothing is claimed from a part that was not
  read, that every claim carries its status tag (`[proposed]`, `[preliminary]`, `[reported]`, `[published]`), a
  locator and its scope, that only the user's own writing is quoted verbatim and only in `[!reuse]` blocks, and that
  the page is written from its own document, with comparisons to the wiki left to integration (§8.2).
- **Integration phase.** Read `git diff <start revision> -- <your pages>` and, for each new or changed claim, the
  section of the source page it cites (head first). Check that the claim matches the source page, keeps its status
  and scope and has a locator, that a disagreement uses `[!contradiction|STATUS]` after a scope check, and that
  `[!user]` and `[!reuse]` blocks are unchanged.
- Fix clear errors in the pages you review: a wrong locator or status, a lost scope, a claim the source page does not
  support, copied text. Report judgment calls instead of deciding them. Do not edit other pages, generated files
  (`index.md`, `sources:` lists), `log.md`, `pending.md` or `reviewed.md`, and do not run git or the checks below.

## Checks runner

You hold no page content. Write each check's output to a file in the cache folder and read only its last lines, for
example:

    python3 -I tools/wikilint.py --since <start revision> > <cache>/checks/lint.txt 2>&1; tail -n 3 <cache>/checks/lint.txt

Run the checks your assignment lists: `catalog.py --apply`, `review.py since <start revision> --queue` (report the
count of open items), `wikilint.py --since <start revision>`, `test_tools.py` when tools changed, and `docs.py clean`.
Wait for a long command with the longest timeout your agent allows, never with short repeated checks. On a failure,
list the failing pages, items or tests (`grep -m 20`) in your report and do not fix pages yourself: the orchestrator
gives each failure to a fresh subagent with only the failing items.

## Final report

Write it to the reports file named in your assignment, then end with one line: role, pages reviewed or checks run,
fixes made, problems open. The report lists each problem with its page and line or its check, and what was done.
