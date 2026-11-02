# Reader brief

You are a **reader** in an ingest (AGENTS.md §8.2b). You read **one document** in this context, file it, and end.
This brief replaces the session protocol for you: do not read `index.md`, `log.md`, `reviewed.md` or the whole of
AGENTS.md, and do not search memory. Run every command from the wiki root with `python3 -I tools/<tool>`. Your
assignment message gives the document's files (relative to the raw root), the target page name, the project page if
any, the cache folder for your brief, and any batch-specific notes.

## Hard rules

- The raw root is read only, through `tools/docs.py`. Never write, move or open a file there in an editor. Never copy
  files, figures, full text or extracted text into the wiki.
- Only the user's own writing may be quoted verbatim, and only in `> [!reuse] <label> · <locator>` blocks (up to about
  300 words each). Text by co-authors, reviewers or sponsors is paraphrased, with quotations of at most 2 sentences.
- If the document turns out to be confidential to others (a review the user wrote of someone else's work, someone
  else's proposal, a student record), stop, write nothing, and report it.
- Be honest about what you read. Never write a claim from a part you did not read, and never record `rendered` for a
  page you did not view as an image.
- Write only your own source page (and its part notes, if it needs them) and your brief. Do not edit other pages, and
  do not run `relink.py`, `catalog.py`, `review.py` or git.

## Steps

1. `docs.py info FILE` for each file: renditions, properties, the suggested `doc_id`, the `file://` URL.
2. **Read every page or slide, and every figure and table with its caption.** Prefer the submitted PDF rendition
   (`docs.py render FILE --pages a-b`, then view each image). For Word or PowerPoint without a PDF, `docs.py render`
   converts it; if no converter is available, read `docs.py text FILE` and view every image it lists (`read_mode:
   source`). LaTeX: `docs.py text main.tex` and view each figure it lists. Use extracted text to search or quote.
3. Write `sources/<page>.md` per the source page template (tools/README.md, Schema details, Page templates): the
   frontmatter (with a one-line `summary:` of about 200 characters, `doc_kind`, `my_role`, `project` if given,
   `doc_id`, `files`, `read_file`, `read_depth`, `read_mode`), then `# <Short title> (<doc kind>, <date>)` with a
   TL;DR, `## Files`, `## Context`, `## Key content`, `## Claims and results` (each bullet starting with `[proposed]`,
   `[preliminary]`, `[reported]` or `[published]`, with scope and a locator: p., §, Fig., Table, slide), `## Reviewer
   feedback` (reviews only), `## Reusable material`, `## Limitations and caveats`, `## Connections`, `## User notes`
   (delegated mode: no discussion, the date, what the page stresses and why) ending with a `> [!note] Reading
   history` (date, which file and pages or slides were read and how, what was not read and why).
   - Write the page **from the document alone**: no comparison with wiki pages in the TL;DR or key content.
   - A plan is `[proposed]` even when it sounds certain. Preliminary data in a proposal is `[preliminary]`.
   - If the page would exceed 40,000 bytes, put section detail in part notes with `tools/split.py`.
4. `docs.py stamp <page>`. **The stamped page is the checkpoint**: file it before doing anything else.
5. `wikilint.py --since HEAD` and fix every error on your page. An `unintegrated` warning is expected.
6. Write the integration brief in the cache folder (format below), then end with one line: doc_id, page,
   read_depth/read_mode, pages or slides read, problems.

## Links

- Link candidates come from a search for your document: `tools/search.py` (or `qmd query`) on its main subjects,
  about the top 15. Link only to pages that exist. Do not invent slugs; propose them in the brief.
- Documents in the raw root without a page: `[Short name ↗](file:///…)` with the URL `docs.py info` prints.

## Style

Paraphrase, with numbers, units, systems and conditions. Math in LaTeX with the document's notation. No Unicode
superscripts or subscripts. Spell out acronyms at first use. Label your own inferences and speculation. Avoid
semicolons and parenthetical em dashes in new prose.

## Brief format (cache folder, `<doc_id>.md`)

```
# <doc_id> <page> — <short title>
state: read_depth / read_mode
project: <project page or proposed slug>
## Claims per target page
- [[existing-page]] (or NEW: proposed-slug, project|concept|entity|topic, why it earns a page per AGENTS.md §5.7):
  [status] claim with numbers, system, method, metric, conditions; locator
## Reusable material
- block labels on the source page, and figures or tables worth pointing to
## Reviewer feedback (reviews only)
## Tensions
- possible disagreements with existing pages (page + what differs), or "none noticed"
## Problems
```
