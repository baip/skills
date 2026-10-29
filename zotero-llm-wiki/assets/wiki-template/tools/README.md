# Implementation guide (tools and machine-specific details)

`AGENTS.md` holds the durable policy. This file holds the *how* for this machine and agent setup, which may change
without changing the policy. Set up {{DATE}} ({{ENVIRONMENT}}).

## Tools (Python stdlib only; run from the wiki root as `python3 -I tools/<tool> …`)

| Tool | What it does |
|---|---|
| `zot.py` | Read-only Zotero client. It sends GET requests to Zotero's local API (Zotero 7+, Settings → Advanced → "Allow other applications on this computer to communicate with Zotero") and, if Better BibTeX is installed, one read-only RPC method for citation keys. Its only wiki write is `stamp`. The data directory comes from `$ZOTERO_DATA_DIR`, else the Zotero profile's setting, else `~/Zotero` |
| `wikilint.py [--strict]` | Structural and metadata validation, including explicit `corporate_authors` declarations for organization names in `authors`. It exits 1 on errors; `--strict` (the completion gate) also fails on warnings and open `pending.md` items. Its `tools` warning compares `tools/*.py` with the installed skill (`$ZOTERO_LLM_WIKI_SKILL`, else `~/.claude/skills/zotero-llm-wiki`) |
| `review.py` | Wiki-side review queue: `touched PAGE…` and `since REV --queue` queue the dependents of pages whose content changed; `done PAGE… --outcome corrected\|unchanged\|not-affected --basis TEXT [--cause ID]` resolves items into the ledger `reviewed.md`, and a resolved (page, cause) is never re-queued; `restated PAGE --phrase TEXT…` queues every other page whose body (outside code and link-list sections) still contains a phrase of a corrected claim, matching case- and whitespace-insensitively; `list` groups open items by page and counts resolutions |
| `catalog.py [--apply]` | Generated bookkeeping: re-derives each page's `sources:` from its body, and regenerates the index header counts and line metadata (summaries untouched). Lint warns (`catalog`) while anything is out of date |
| `relink.py` | Converts `↗` Zotero links into wikilinks once the item has a source page. It skips `[!user]` callouts and code, and refuses to write if they would change. Dry run by default; `--apply` writes |
| `search.py TERM… [--phrase TEXT]… [--type T] [--collection PREFIX] [--depth D] [-n 15]` | Ranked keyword search over the pages, for queries (AGENTS.md §8.3): BM25 over each page, with title, aliases, first heading and filename also ranked on their own, and tags, authors, citekey and headings counted extra. Words are lowercased, split at hyphens and plural-folded; no other stemming and no embeddings, so try synonyms. Prints score, path, type, title, read depth and the best-matching line. Read-only |
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
| `render KEY [--pages 3-7] [--dpi 150]` | PDF pages as PNG files in `$TMPDIR/zotero-wiki/pages/`, one `PAGE<TAB>PATH` line each; view them as images (Reading PDFs, below) |
| `fulltext ATTACHMENT_KEY` | Zotero's text index, written to `$TMPDIR/zotero-wiki/`. Use it for search and exact quotes only |
| `clean` | Deletes `$TMPDIR/zotero-wiki/` (rendered pages, text indexes); run it at the end of an interaction |
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

## Reading PDFs (AGENTS.md §7)

- `zot.py render KEY --pages 1-10` renders PDF pages to PNG files in `$TMPDIR/zotero-wiki/pages/ATTACHMENT_KEY/` and
  prints one `PAGE<TAB>PATH` line per page; view each file with the agent's image viewer. PAGE is the 1-based PDF page
  index used in `zotero://open-pdf/…?page=N` links. The default 150 dpi keeps subscripts and table digits legible; use
  `--dpi 200` for small print. Render about 10–20 pages at a time and view every page of a batch before the next.
- This works for any agent that can view a local image file: Claude Code (`Read`), Codex (its image viewer), OpenCode
  with a vision-capable model. Claude Code's `Read` can also open the PDF directly with page ranges (at most 20 pages
  per call: `"1-20"`, `"21-40"`, …); either way counts as `rendered`.
- An agent that cannot view images reads the text index instead and records `read_mode: text-index` (figures unseen,
  equations unverified). Never record `rendered` for a page that was not viewed as an image.
- Rendering needs poppler (`pdftoppm`, `pdfinfo`): `brew install poppler` on macOS, `apt install poppler-utils` on Debian/Ubuntu.
- `zot.py fulltext` writes the text index to `$TMPDIR/zotero-wiki/`, outside the wiki. `zot.py clean` deletes the rendered
  pages and text indexes; run it at the end of the interaction (AGENTS.md §8.2 step 8). A first `stamp` of a new page has
  no baseline and never queues anything.
- The PDF is read in place and never copied. Never filter or truncate extracted text to "clean" it.

## Batch runs (AGENTS.md §8.2b)

- **Inventory**: items, PDF availability, page counts, notes, annotations and current states; items in *read* or
  *metadata* are included for integration, not skipped. Group them into reader batches by theme and length; a very long
  document gets its own batch.
- **Readers** stamp only the pages they create (no baseline, so nothing is queued); re-stamping existing pages belongs to
  the main agent. They link only to existing pages or to the vocabulary of slugs the main agent fixes in advance.
- **Integrators** treat source pages as the authority and return an index line per page, synthesis bullets tagged by
  open question, and unresolved problems. The main agent runs lint until clean and writes one log entry for the batch.
- Completion is judged by AGENTS.md §8.2, not by whether pages exist. Report what changed in the synthesis.

- **With subagents** (Claude Code allows 20 concurrent subagents by default, `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`):
  keep the reader and integrator instruction files in a temp directory outside the wiki (in Claude Code, the session
  scratchpad), and give each subagent its batch and the fixed vocabulary of planned slugs in its prompt. Subagents must
  be able to run the tools and view images; if they cannot, use the sequential mode. After a session or rate limit,
  resume each subagent with a message (Claude Code: SendMessage to its id) and tell it to check which of its pages are
  already complete.
- **Without subagents** (or when they cannot run the tools or view images), run the same phases in one session, in
  order: read and write every source page first, one paper at a time, saving each integration brief to a temp file
  outside the wiki; then integrate one page set at a time from the briefs; then write the topic synthesis, index and
  log. Do not edit concept, entity or topic pages during the reading phase. If the session ends midway, the stamped
  source pages are the checkpoint: resume reading at the first item without a page, and rebuild missing briefs from
  the source pages.
- Run `relink.py --apply` only after all reading has finished, because it rewrites files a reader may be editing.

## Semantic search with qmd (optional; AGENTS.md §8.3)

[qmd](https://github.com/tobi/qmd) adds keyword plus vector search with reranking, all on this machine. It indexes the
five page folders only, never PDFs, Zotero or the bookkeeping files, so it stays within AGENTS.md §2.2. Without it,
use `tools/search.py`.

- **Install** (once per machine): `npm install -g @tobilu/qmd` (Node 22+), and on macOS `brew install sqlite`. The
  first `embed` and `query` download three models, about 2 GB in all, to `~/.cache/qmd/models/`.
- **Where the index lives.** `.qmd/` at the wiki root holds the index (`index.sqlite`) and its configuration
  (`index.yml`); qmd uses it whenever it runs inside this folder. It is git-ignored. In a folder that is not
  cloud-synced, `qmd init` makes a real `.qmd/` folder. In a cloud-synced folder (Google Drive, Dropbox, OneDrive,
  iCloud), make `.qmd` a link to a folder outside the synced tree first, so the sync service never uploads the index.
  Each machine builds its own index; a link synced from another machine points nowhere and must be replaced.
- **Set up** (from the wiki root; NAME is a short name for this wiki):

  ```sh
  mkdir -p ~/.cache/qmd/projects/NAME && ln -s ~/.cache/qmd/projects/NAME .qmd   # cloud-synced folder only
  qmd init
  qmd collection add . --name NAME --mask "{sources,concepts,entities,topics,analyses}/*.md"
  qmd context add qmd://NAME "<one sentence on what this wiki covers>"
  qmd context add qmd://NAME/sources "Source pages: one per Zotero item, with what was read"   # and one per folder
  qmd embed
  ```

- **Before each query session**: `qmd update && qmd embed`, which re-index and re-embed only pages that changed.
- **Query**: write the structured form yourself rather than pasting the question:
  `qmd query $'intent: <what to find, and what to avoid>\nlex: <exact terms, abbreviations, names>\nvec: <the idea in
  the wiki's own wording>'`. Use `qmd search "<exact words>"` for names and rare terms. Useful options: `-n 10`,
  `--format files`, `--full-path`. Treat results as leads: open the pages with the normal file reader, and cite them as
  wiki pages, not qmd docids.
- **Slow machines** (no GPU): `qmd query --no-rerank …`, `qmd vsearch`, or `tools/search.py`.

## Running under other coding agents

Every rule is in `AGENTS.md`, which Codex and OpenCode load by themselves and Claude Code loads through `CLAUDE.md`. The
tools are plain `python3 -I tools/…` commands, so what differs between agents is only what they are allowed to do. The
wiki needs:

1. network access to `localhost:23119` (Zotero's local API, and Better BibTeX on the same port);
2. writes to this folder, the system temp directory, the git directory if it is outside this folder (see Revision
   history), and the skill folder (`{{SKILL_DIR}}`) when a tool changes (AGENTS.md §12);
3. viewing local image files (rendered PDF pages) and poppler on the `PATH`;
4. for qmd (optional): writes to `~/.cache/qmd` (the index behind `.qmd`, and the models), and network access to
   huggingface.co the first time the models download. Without these, use `tools/search.py`.

- **Claude Code**: works as is; approve the prompts for these commands, or allow them in its settings.
- **Codex**: its default `workspace-write` sandbox blocks network access and writes outside the folder it was started
  in. Start it from this folder and allow both in `~/.codex/config.toml` (key names as of 2026; newer versions also
  offer permission profiles, so check the Codex docs for yours):

  ```toml
  sandbox_mode = "workspace-write"
  [sandbox_workspace_write]
  network_access = true
  writable_roots = ["<git directory, if outside this folder>", "<skill folder, resolved>", "<home>/.cache/qmd"]
  ```

  Some Codex versions keep `.git` folders read-only even inside writable roots; if a commit is refused, approve it
  to run outside the sandbox when Codex asks.

- **OpenCode**: no sandbox by default, but its permission settings (`opencode.json`) may ask before shell commands and
  edits; allow `python3 -I tools/*`, `git` and the poppler commands.
- **The skill's location.** The tools look for the skill at `$ZOTERO_LLM_WIKI_SKILL`, else
  `~/.claude/skills/zotero-llm-wiki`. OpenCode also loads skills from `~/.claude/skills`. Codex loads them from
  `~/.codex/skills`: link `~/.codex/skills/zotero-llm-wiki` to the same folder, so both paths lead to one copy.

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
