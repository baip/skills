# Implementation guide (tools and machine-specific details)

`AGENTS.md` holds the durable policy. This file holds the *how* for this machine and agent setup, which may change
without changing the policy. Set up {{DATE}} ({{ENVIRONMENT}}).

## Tools (Python stdlib only; run from the wiki root as `python3 -I tools/<tool> …`)

| Tool | What it does |
|---|---|
| `zot.py` | Read-only Zotero client. It sends GET requests to Zotero's local API (Zotero 7+, Settings → Advanced → "Allow other applications on this computer to communicate with Zotero") and, if Better BibTeX is installed, one read-only RPC method for citation keys. Its only wiki write is `stamp`. The data directory comes from `$ZOTERO_DATA_DIR`, else the Zotero profile's setting, else `~/Zotero` |
| `wikilint.py [--strict]` | Structural and metadata validation. It exits 1 on errors; `--strict` (the completion gate) also fails on warnings and open `pending.md` items. Its `tools` warning compares `tools/*.py` with the installed skill (`$ZOTERO_LLM_WIKI_SKILL`, else `~/.claude/skills/zotero-llm-wiki`) |
| `review.py` | Wiki-side review queue: `touched PAGE…` and `since REV --queue` queue the dependents of pages whose content changed; `done PAGE… --outcome corrected\|unchanged\|not-affected --basis TEXT [--cause ID]` resolves items into the ledger `reviewed.md`, and a resolved (page, cause) is never re-queued; `restated PAGE --phrase TEXT…` queues every other page whose body (outside code and link-list sections) still contains a phrase of a corrected claim, matching case- and whitespace-insensitively; `list` groups open items by page and counts resolutions |
| `catalog.py [--apply]` | Generated bookkeeping: re-derives each page's `sources:` from its body, and regenerates the index header counts and line metadata (summaries untouched). Lint warns (`catalog`) while anything is out of date |
| `relink.py` | Converts `↗` Zotero links into wikilinks once the item has a source page. It skips `[!user]` callouts and code, and refuses to write if they would change. Dry run by default; `--apply` writes |
| `wikimeta.py` | Shared module: a strict frontmatter parser, protected spans, page loading, derived source states, evidence links and dependents, the `pending.md` queue and the `reviewed.md` ledger |
| `test_tools.py` | Regression tests, no network. They cover the parser (YAML quoting), validation, protected text (``` and ~~~ fences, inline code, `[!user]`), the integration proxy, fingerprint fixtures, and **end-to-end update sequences** in a temporary wiki: detect → queue → stamp → review → strict gate. These include an interrupted stamp, an incomplete baseline, a v2→v3 migration that hides a change, evidence vs Connections dependencies, and 8 concurrent queue writers. Run after any tool change |

### `zot.py` commands

| Command | Use |
|---|---|
| `status` | Zotero reachable? Run at the start of any session that needs Zotero |
| `collections [--match TEXT]` | Collection keys and paths. `--match` is case-insensitive and matches word starts ("cement" finds *Materials/Cement*, not *Reinforcement*); with no match it lists the closest spellings and says so. Confirm with the user when several collections match |
| `items KEY [--recursive]` | Items in a collection (subtree) |
| `search "QUERY"` | Find items by title, creator or year |
| `item KEY` | Metadata, citekey, collections, tags, attachments (with annotation counts) and child notes |
| `notes KEY` / `annotations ATTACHMENT_KEY` | The user's own notes and highlights, which are high-signal; prints "(no notes …)" or "(no annotations …)" when there are none |
| `pdfpath KEY` | One line per PDF attachment: `ATTACHMENT_KEY<TAB>ABSOLUTE_PATH<TAB>OK\|MISSING` (stored or linked files), for reading in place; take the second field |
| `fulltext ATTACHMENT_KEY` | Zotero's text index, written to `$TMPDIR/zotero-wiki/`. Use it for search and exact quotes only |
| `coverage KEY [--recursive]` | Per-item state: `[ ]` none, `[m]` metadata, `[r]` read, `[x]` integrated |
| `fingerprint KEY` | v3 content hashes: biblio (bibliographic and venue fields), abstract, pdf (attachment key plus MD5, or link mode, path and mtime without one), notes, annotations (with page label and position) |
| `stamp CITEKEY…` / `stamp ALL` | Write `zotero_fingerprint` and `zotero_checked` (atomic write). It first compares with the previous baseline using that baseline's own algorithm (v2 or v3). If a scientific part changed, or the baseline was incomplete, it queues the evidence dependents in `pending.md`, under a lock |
| `changed [--queue]` | Pages whose Zotero item changed since stamping (*metadata refresh*: biblio only; *scientific re-read*: abstract, pdf, notes, annotations), plus pages whose baseline is INCOMPLETE, with their evidence dependents. `--queue` appends review items to `pending.md` under a lock. Every check reads one consistent snapshot (collected between two reads of the library version, retried if it moved; a missing or non-integer `Last-Modified-Version` is an error, because consistency cannot then be verified) |

## Changing a tool (AGENTS.md §12)

1. Edit the tool in `{{SKILL_DIR}}/assets/wiki-template/tools/`, add a test to `test_tools.py` there, and run
   `python3 -I {{SKILL_DIR}}/assets/wiki-template/tools/test_tools.py`.
2. If the skill folder is a git clone (or a link to one), commit the change there.
3. From the wiki root, `python3 {{SKILL_DIR}}/scripts/init_wiki.py --upgrade-tools . [--trailer "LINE"]`: it replaces the
   changed tools, runs the tests and the linter (errors only), appends a `fix` entry to `log.md` and commits the tools and
   the log. It prints the template's rows of this README that differ from yours; update the rows that apply.

## Provenance and review mechanics (AGENTS.md §4)

**Fingerprints.**
- Format `v3`: five parts, `biblio` (bibliographic and venue fields), `abstract`, `pdf` (each PDF bound to its
  attachment key: MD5, or link mode, path and mtime when Zotero has none), `notes`, `ann` (with page label and position).
- **Complete or nothing**: all five parts, each a valid hash or `none`. A missing, malformed or partial fingerprint
  certifies nothing: lint rejects it, `changed` reports it as INCOMPLETE, and stamping over it queues the dependents.
- A stored fingerprint is compared **with the algorithm that produced it**: a v2 baseline is checked with v2 before it
  is replaced, so a change made under the old format cannot slip through a migration.
- **One snapshot per check**: the item, attachments, notes and annotations are collected between two reads of the
  library version and re-read if it moved; it gives up if the library never settles. A missing or non-integer
  `Last-Modified-Version` is an error, never a match. The comparison and the new baseline come from the same snapshot.
- `stamp` queues the dependents **before** it replaces the baseline whenever a scientific part changed, so an
  interrupted update cannot lose a review. An abstract counts as scientific content.

**Dependencies.** `wikimeta.evidence_links` gives the pages a body uses as evidence: links outside `## Connections`,
`## Related` and `## Sources`, minus pointer runs introduced by `→`, "See" or "cf." unless a locator (`§`, `Fig.`,
`Table`, `eq`, `p.`, `SI`, `App.`) follows the link. Lint's `sources:` check and the ingestion states still count every
link. `propagate` chains through source pages only when the changed page is itself a source.
Why not a full transitive closure: in the 140-page wiki these tools were developed on, it queued a median of 136 pages
for any one change; these rules gave a median of 15 for a source change and 5 for a synthesis page.

**Queue (`pending.md`).** Items are `- [ ] [[page]] note (cause: <id>)`, with an alias `[[page|…]]` allowed; causes are
`zotero:<citekey>@<fp-hash>` or `wiki:<page>@<body-hash>` (body hash excludes frontmatter, so frontmatter-only edits
never queue). One item per (page, cause), so a second reason is never dropped. Any other checkbox line, or a ticked
item left in place, is a lint error rather than an empty queue. Hand-written items (without a cause) are allowed for
work that must not be forgotten.

**Ledger (`reviewed.md`).** `review.py done` writes `- DATE OUTCOME (cause: ID) [[page]], … — basis` (one line per
cause, outcome and basis), then removes the items. A (page, cause) in the ledger is never queued again, so `since` can
be repeated until it queues nothing; causeless items are recorded with `(cause: none)` and never suppress later ones.
Lint checks the line format, outcome, basis length and links.

## Concurrency and file safety

- `pending.md` and `reviewed.md` updates take exclusive `fcntl` locks (the ledger is written first). The lock file is in the system temp directory, keyed by path, not in
  the (possibly cloud-synced) wiki. Locking uses `fcntl`, so the tools need macOS or Linux (on Windows, run them under WSL). They then replace the file atomically (temp file plus `os.replace`). `stamp` and `relink.py` also write atomically.
- Locks only coordinate processes on **one machine**. Do not run tools against the same wiki from two computers at once.

## Reading PDFs in place

- Get the path with `zot.py pdfpath KEY`. Then view the rendered pages with the agent's file-reading tool,
  using page ranges (Claude Code's `Read` takes at most 20 pages per call: `"1-20"`, `"21-40"`, …).
- Page rendering in Claude Code needs poppler (`pdftoppm`): `brew install poppler` on macOS, `apt install poppler-utils`
  on Debian/Ubuntu. Other agents need some way to view PDF pages as images; without one, record `read_mode: text-index`.
- `zot.py fulltext` writes the text index to `$TMPDIR/zotero-wiki/`, outside the wiki; delete those files at the end of the
  interaction (AGENTS.md §8.2 step 8). A first `stamp` of a new page has no baseline and never queues anything.
- Rendering happens in memory, so nothing is copied. Never filter or truncate extracted text to "clean" it.

## Batch runs (AGENTS.md §8.2b)

- **Inventory**: items, PDF availability, page counts, notes, annotations and current states; items in *read* or
  *metadata* are included for integration, not skipped. Group them into reader batches by theme and length; a very long
  document gets its own batch.
- **Readers** stamp only the pages they create (no baseline, so nothing is queued); re-stamping existing pages belongs to
  the main agent. They link only to existing pages or to the vocabulary of slugs the main agent fixes in advance.
- **Integrators** treat source pages as the authority and return an index line per page, synthesis bullets tagged by
  open question, and unresolved problems. The main agent runs lint until clean and writes one log entry for the batch.
- Completion is judged by AGENTS.md §8.2, not by whether pages exist. Report what changed in the synthesis.

- Claude Code allows **20 concurrent subagents** by default (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`).
- Keep the reader and integrator instruction files in the session scratchpad. Give each subagent its batch, and the
  fixed vocabulary of planned slugs, in its prompt.
- After a session or rate limit, subagents keep their transcripts. Resume them with a message (SendMessage to their
  id) and tell them to check which of their pages are already complete.
- Run `relink.py --apply` only after every reader has finished, because it rewrites files the readers may be editing.

## Revision history (git)

{{GIT_DETAILS}}
- **Staging:** stage the paths you changed explicitly. Leave pre-existing changes alone until the user confirms who made them
  (AGENTS.md §2.10).
- `.gitignore` excludes OS and cloud-sync temp files, `__pycache__/`, `.obsidian/workspace*.json` and `.obsidian/graph.json` (UI state that changes on every use), and keeps the other
  Obsidian settings.
- **Remote:** add one if you like (`git remote add origin …`). Agents commit locally and push only when asked.
- Typical checks: `git status` (the user's hand edits), `git diff <page>`, `git log --oneline -- <page>` (a page's history).

## Zotero library scope

All commands address the local **user** library (`/api/users/0`, which is `{{LIBRARY}}`). Every source page
records `library:`, and lint keys identity by (library, key) and checks the URI form for user and group libraries.
`zot.py` itself does not read group libraries yet: that needs `/api/groups/<id>` before ingesting from one.
