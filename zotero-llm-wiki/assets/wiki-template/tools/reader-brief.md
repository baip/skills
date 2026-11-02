# Reader brief

You are a **reader** in an ingest (AGENTS.md §8.2b). You read **the paper or papers in your assignment** in this
context (one paper, or several short ones), file each, and end. For several papers, finish steps 1–6 for one before
opening the next. This brief replaces the session protocol for you: do not read `index.md`, `log.md`, `reviewed.md`
or the whole of AGENTS.md, and do not search memory. Run every command from the wiki root with
`python3 -I tools/<tool>`. Your assignment message gives the Zotero key and target filename of each paper, the cache
folder for your briefs, and any batch-specific notes.

## Hard rules

- Zotero is read only, through `tools/zot.py`. Never copy PDFs, figures, full text, verbatim abstracts or Zotero notes
  into the wiki. Quotations of at most 2 sentences with a locator; equations rewritten in LaTeX.
- Be honest about what you read. Never write a claim from a part you did not read, and never record `rendered` for a
  page you did not view as an image.
- Write only your own source page (and its part notes, if it needs them) and your brief. Do not edit other pages, and
  do not run `relink.py`, `catalog.py`, `review.py` or git.

## Steps

1. `zot.py item KEY`, `zot.py notes KEY`, and `zot.py annotations ATTACHMENT_KEY` for each PDF. The user's notes and
   annotations are high-signal. Identify the main PDF (`attachment_key`) and any supplement.
2. **Read the rendered main PDF: every body page, and every figure and table with its caption** (`zot.py render KEY
   --pages a-b`, then view each image, or the agent's PDF reader with page ranges). Read the supplement where the main
   text relies on it (methods, parameters, data or results deferred there). Otherwise record `supplement: not-read`
   and a Reading history line "Supplement not read: <reason>". Use `zot.py fulltext` only to search or quote exactly.
   Books over 150 PDF pages: front matter plus the chapters named in your assignment, each in full.
3. Write `sources/<filename>.md` per the source page template (tools/README.md, Schema details, Page templates): the frontmatter fields (including a one-line `summary:` of about
   200 characters), then `# <Short title> (<First author> <year>)` with a TL;DR, `## Open in Zotero` (item link and a
   section map of `zotero://open-pdf/library/items/<attachment_key>?page=N`, N the 1-based PDF page),
   `## Key contributions` (3–7 bullets), `## Methods / setup`, `## Results and claims` (each with scope and locator),
   `## Limitations and caveats` (the authors', then yours, marked), `## Connections`, `## User notes` (delegated mode:
   no discussion, the date, whether Zotero has notes or annotations, what the page stresses and why) ending with a
   `> [!note] Reading history` (date, exactly which PDF and supplement pages were read, what was not read and why).
   - Write the page **from the paper alone**: no comparison with wiki pages in the TL;DR or key contributions.
   - Every quantitative claim keeps system, method, metric and conditions, with a locator (§, Fig., Table, eq., p.).
   - If the page would exceed 40,000 bytes, keep the source page to the parts AGENTS.md §5.1 lists for it and put chapter
     or section detail in part notes with `tools/split.py` (or write them directly in that form).
4. `zot.py stamp <filename>`. **The stamped page is the checkpoint**: file it before doing anything else, so an
   interruption never forces a re-read.
5. `wikilint.py --since HEAD` and fix every error on your page. An `unintegrated` warning is expected.
6. Write the integration brief in the cache folder (format below). After your last paper, end with one line per
   paper: key, filename, read_depth/read_mode/supplement, pages read, problems.

## Links

- Link candidates come from a search for your paper: `tools/search.py` (or `qmd query`) on its main subjects, about the
  top 15. Link only to pages that exist. Do not invent concept or entity slugs; propose them in the brief.
- Items in Zotero without a page: `[Author Year ↗](zotero://select/library/items/KEY)` (find them with `zot.py search`).
  Works not in Zotero: plain text with the DOI printed in the paper; never guess a DOI.

## Style

Paraphrase, with numbers, units, systems and conditions. Math in LaTeX with the paper's notation. No Unicode
superscripts or subscripts. Spell out acronyms at first use. Label your own inferences and speculation. Avoid
semicolons and parenthetical em dashes in new prose.

## Brief format (cache folder, `<KEY>.md`)

```
# <KEY> <filename> — <short title>
state: read_depth / read_mode / supplement
## Claims per target page
- [[existing-page]] (or NEW: proposed-slug, concept|entity, why it earns a page per AGENTS.md §5.6):
  claim with numbers, system, method, metric, conditions; locator
## Tensions
- possible disagreements with existing pages (page + what differs), or "none noticed"
## Evidence on open questions
## Reading-queue candidates
## Problems
```
