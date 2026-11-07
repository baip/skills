# Validator brief

You validate one part of a batch (AGENTS.md §8.2b) in a fresh context, as a **reviewer**, the **screener**, a
**resolver** or the **checks runner**.
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

## Screener

You screen the open review items (AGENTS.md §4) before anyone opens a page, so that only items the change may affect
reach a resolver. Run `python3 -I tools/review.py screen <since revision> > <cache>/checks/screen.txt` and read that
file once. For each cause it shows the cause page's changed lines, then every open dependent with the lines that cite
it.

- Resolve an item as *not-affected* when its citing lines do not use the changed content: a pointer to the page
  (`are on [[x]]`, `→ [[x]]`), a citation of another claim, section, figure or result of that page, or a quotation
  chain that ends in a part that did not change. The basis names, in one line, what the citing lines use and what
  changed.
- Leave an item open when a citing line uses, restates or depends on the changed content, when no citing line was
  found, when the changed lines were cut short, or when you are unsure. Do not open pages to decide: that is the
  resolvers' work.
- Write your decisions to `<cache>/checks/screened.tsv`, one per line (`PAGE<TAB>CAUSE<TAB>not-affected<TAB>BASIS`),
  and apply them with one `python3 -I tools/review.py resolve <cache>/checks/screened.tsv`. Do not edit pages.
- Your report lists the items left open, grouped by cause, each with its reason.

## Resolver

You take the open items of one cause, about 10 pages, from the screener's report. For each, compare the citing
sentences (`review.py list --context`) with the cause page's changed lines, and open the whole dependent page only when
those sentences use the changed content. Correct a page that no longer matches its sources (§6.8), then resolve each
item with `review.py done PAGE --cause CAUSE --outcome corrected|unchanged|not-affected --basis TEXT`. Do not run
`review.py since`: report the pages you corrected, and the checks runner queues their dependents.

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
