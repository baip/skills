# Implementation guide (tools and machine-specific details)

`AGENTS.md` holds the durable policy. This file holds the *how* for this machine and agent setup, which may change
without changing the policy. Set up {{DATE}} ({{ENVIRONMENT}}).

## Tools (Python stdlib only; run from the wiki root as `python3 -I tools/<tool> …`)

| Tool | What it does |
|---|---|
| `zot.py` | Read-only Zotero client. It sends GET requests to Zotero's local API (Zotero 7+, Settings → Advanced → "Allow other applications on this computer to communicate with Zotero") and, if Better BibTeX is installed, one read-only RPC method for citation keys. Its only wiki write is `stamp`. The data directory comes from `$ZOTERO_DATA_DIR`, else the Zotero profile's setting, else `~/Zotero` |
| `wikilint.py [--strict] [--since REV]` | Structural and metadata validation (`--since REV` lists every error but only counts warnings, with details for pages changed since REV: the form to use during work), including explicit `corporate_authors` declarations for organization names in `authors`. It exits 1 on errors; `--strict` (the completion gate) also fails on warnings and open `pending.md` items. Its `tools` warning compares `tools/*.py` with the installed skill (`$ZOTERO_LLM_WIKI_SKILL`, else `~/.claude/skills/zotero-llm-wiki`) |
| `review.py` | Wiki-side review queue: `touched PAGE…` and `since REV --queue` queue the dependents of pages whose content changed (`since` lists *additive* edits, which only insert lines, without propagating them, except inserted `[!contradiction]`/`[!stale]` callouts); `done PAGE… --outcome corrected\|unchanged\|not-affected --basis TEXT [--cause ID]` resolves items into the ledger `reviewed.md`, and a resolved (page, cause) is never re-queued; `restated PAGE --phrase TEXT…` queues every other page whose body (outside code and link-list sections) still contains a phrase of a corrected claim, matching case- and whitespace-insensitively; `list [--context]` groups open items by page and counts resolutions, and with `--context` prints the lines of each page that cite the changed page, which a review reads first |
| `catalog.py [--apply] \| --nav \| --adopt-index-summaries [--apply]` | Generated bookkeeping: re-derives each page's `sources:` from its body, and writes every `index.md` line below the preamble from the pages (display from the title or `# ` heading, summary from the `summary:` field, metadata generated). `--nav` prints the index preamble and Topics section, the session-start read. `--adopt-index-summaries` is the one-time migration that copies index-line summaries into `summary:` fields. Lint warns (`catalog`) while anything is out of date, and (`summary`) for a page without a summary |
| `split.py PARENT --section HEADING --to CHILD --summary TEXT [--title T] [--apply]` | Splits a concept, entity, topic or source page over the 40,000-byte limit (lint `size`, AGENTS.md §11): moves one `##`–`####` section verbatim to a new child page (for a source, a part note `PARENT--<slug>` with `type: source-part`) and leaves the heading, the summary line and a pointer in the parent. It refuses if protected text would change. Dry run by default. Pass the parent to `review.py since --neutral`, then run `catalog.py --apply` |
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

- **One paper per reader context** (AGENTS.md §8.2b). Start a fresh reader subagent (or, for an agent without
  subagents, a fresh session) for each paper and let it end after its page and brief. Do not resume a finished reader
  with a new paper, and do not resume readers after a usage-limit stop: start new ones and let them check which pages
  exist. Bundling short papers would spread
  the reader's startup (system prompt, tools, brief) over them (measured 2026-11-02: about 0.40M input-equivalent
  tokens per paper with one paper each, about 0.34M with 2–3, different papers), but it was rejected the same day
  because an earlier paper in the context could shape the next page.
  Rendered page images stay in a context and are sent again with every later call, so a reader that reads ten papers
  pays for the first nine again on each call of the tenth. Measured 2026-11-01 in Codex logs: mean input per call in
  wiki sessions rose from about 60k tokens (2026-10-25 to 28) to about 240k (2026-10-30 to 11-01).
- **Integrator groups of about 10 pages, run in waves** (AGENTS.md §8.2b). Cost grows with the pages one integrator
  holds, because each page it reads is re-sent on every later call. Measured 2026-11-02 (51-paper batch, 156 target
  pages): 4 integrators with 25–40 pages each made 437 calls at a mean context of 200–258k tokens (peak 453k) and used
  13.4M of the run's 25.5M input-equivalent tokens (uncached input + 1.25 × cache writes + 0.1 × cache reads + 5 ×
  output). Plan groups of at most about 10 pages; with a cap on subagents, start the next group as one finishes rather
  than merging groups. Write each integrator's slice of the briefs (the claims aimed at its pages) to its own file in
  the cache folder, so it never greps all briefs. Launch a wave only with quota left for it: 9 integrators started just
  before a 5-hour limit used 1.6M tokens and edited nothing.
- **One phase per orchestrator session.** The orchestrator ends its session after reading and after integration:
  commit the checkpoint, write the next phase's instructions to the batch state file (phase, start revision, items,
  integrator groups, cache paths), and stop, telling the user to start a new session with "Continue ingestion". The
  user never writes a handoff prompt. With no batch folder under `~/.cache/zotero-wiki/`, nothing is pending: ask
  what to ingest.
  To run phases back to back without anyone at the keyboard, run `python3
  ~/.claude/skills/zotero-llm-wiki/scripts/continue_ingestion.py <wiki> --agent codex|claude` in a terminal (not from an
  agent session). It starts a fresh headless session per phase with that prompt and goes on while each phase commits.
  After a usage limit it waits for the reset (stopping if that is more than 6 hours away) and resumes the same session.
  It stops on anything else: no commit, uncommitted changes, an error, `--max-phases`, or `--stop`, which ends it after
  the current phase.
  Add `--after-phase "qmd embed && qmd cleanup"` where qmd is set up: it runs after each committed phase, outside the
  agent's sandbox, which blocks the GPU that embedding needs. `qmd cleanup` then drops what no longer belongs to any
  page (embeddings of old page versions, records of deleted pages) and compacts the index, in seconds and without the
  GPU.
  After a stop that leaves uncommitted work, such as exhausted credits, fix the cause and rerun with `--resume
  <session>`, which the stop message names.
  Subagents write their full reports to `<cache>/reports/` and return one line, which keeps the orchestrator's context
  small (measured 2026-11-02: one session through all phases reached 300k tokens per call, 2.7M tokens).
- **A small orchestrator context** (AGENTS.md §8.2b). These rules hold for any agent; only the mechanics differ.
  - Read file lists, `git diff --stat` and one-line reports, never whole pages, diffs or check output. Reviewers
    and a checks runner validate the phase (next item) and return one line each.
  - Wake only when a subagent finishes. Use the agent's completion notice if it has one. Otherwise wait with the
    longest timeout its wait command allows, never in short repeated checks: each wake-up sends the orchestrator's
    whole context again.
  - Record batch size and subagents at once in the batch state file. An orchestrator's cost per phase is roughly
    fixed, so larger batches and more subagents at once spread it over more papers.
  - Measured: in two 8-paper batches of the sibling chatgpt wiki (2026-11-02), the orchestrator used 46 % and 64 %
    of the tokens: 95–163 calls per phase at a mean context of 95–151k tokens (peak 251k), many of them checks on
    running subagents and whole diffs or files it read itself, while readers and integrators averaged 56–71k.
  - After the change, in the next ten 8-paper batches of that wiki (batches 200–209, 2026-11-03 to 2026-11-04), a batch
    used 32–51M tokens (mean 39M) against 52–57M before, and the orchestrator 7–12M (21–28 %) against 24–36M, in 112–174
    calls per batch against 237–255. The validation subagents that took over the checks and diff reviews cost about as
    much as the orchestrator (6–13M per batch, at a mean context of 108k against 76k for readers), so they are the next
    place to look.
- **Bounded validation** (AGENTS.md §8.2b, rule added 2026-11-04). Give each validator `tools/validator-brief.md` plus
  its role, files, start revision and cache folder, in a fresh context (in Codex, a new agent rather than a fork of the
  orchestrator).
  - Reviewers: about 3 papers each in the reading phase (their source pages and reader reports), one integrator group
    each in integration (`git diff <start> -- <its pages>` and the source-page sections its claims cite). They fix clear
    errors, report judgment calls and run no checks.
  - Checks runner: the orchestrator itself or a small fresh subagent. It writes each check's output to `<cache>/checks/`
    and reads only the last lines. A failure goes to a fresh subagent with only the failing items.
  - Measured before the change (chatgpt wiki, batches 199–210, 31 validators): 0.4–7.6M tokens each, 3.6M on average at
    a mean context of 108k. Each read 400–600 kB of notes, records, reports or diffs, then ran the build, checks, tests
    and search-index refresh on top, so half or more of its calls ran above 120k. Seven started as forks of the
    orchestrator at 63–82k. Split reviews of 13–17 calls cost 0.6–0.9M.
  - After the change (batches 211–239, 29 batches): validation 4.6M tokens per batch (2.2–6.7M) against 9.8M, but the
    orchestrator 13.2M against 9.7M, since it coordinates about 30 subagents per batch instead of about 20. A batch used
    37.0M against 39.3M, within the spread (24.9–54.9M). About half of the orchestrator's tokens are its startup reading
    (context 23k at the first call, 62k by the tenth).
- **Bounded reads.** Give each reader `tools/reader-brief.md` plus its assignment (key, filename, cache folder, batch notes)
  and each integrator `tools/integrator-brief.md` plus its pages, briefs and sources. Readers take link candidates from a
  search for their paper, never a full list of pages; integrators read briefs and the pages they own. Keep batch
  queues, inventories, briefs and the orchestrator's state file in a cache folder outside the wiki, one folder per
  batch (`~/.cache/zotero-wiki/<wiki>-<batch>/`). Delete it when the batch is complete and committed: the briefs,
  reports and drafts in it are derived from pages that now exist, and next ingests belong in the log's `next:` line.
  Nobody reads `index.md`, `log.md` or `reviewed.md` whole: use `catalog.py --nav`, `grep`, and the tools.
- **With subagents** (Claude Code allows 20 concurrent subagents by default, `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`):
  keep the reader and integrator instruction files in a temp directory outside the wiki (in Claude Code, the session
  scratchpad), and give each subagent its batch and the fixed vocabulary of planned slugs in its prompt. Subagents must
  be able to run the tools and view images; if they cannot, use the sequential mode. After a session or rate limit,
  start new subagents for the remaining papers and tell them to check which pages already exist (resuming an old one
  would send its whole context again).
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

- **Before each query session**: `qmd update && qmd embed && qmd cleanup`, which re-index and re-embed only pages that
  changed.
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

## Schema details

Detailed rules moved verbatim from AGENTS.md on 2026-11-01 so the automatically loaded schema stays short.
They are binding. Each subsection is referenced from the AGENTS.md rule it details.

### Review rules (AGENTS.md §4)

- **Review.** When a page's content changes, its dependents may be stale. They are queued in `pending.md`, each item
  with a **cause** (what changed, at which revision):
  - a changed **source** queues its direct dependents, and through source pages that quote it, theirs;
  - a changed **concept, entity, topic or analysis** page queues only its direct dependents;
  - a reviewed page propagates further only if the review changed it (`review.py touched` or `since`);
  - a **claim-neutral** edit (a locator, a typo, wording that keeps the meaning) is not propagated: pass it to
    `review.py since --neutral` and list it in the log;
  - an **additive** edit (whole lines inserted, no existing line changed or deleted) is not propagated:
    `review.py since` detects and lists it, and the log counts it. An inserted `[!contradiction]` or `[!stale]`
    callout still propagates, and an insertion that narrows an existing claim must also edit that claim (§6.8),
    which propagates (rule added 2026-11-01 to control ingest cost);
  - **a corrected claim is also searched for by its wording.** Citation links miss pages that restate the same
    conclusion from the same sources without citing the corrected page. After correcting a claim, run
    `review.py restated PAGE --phrase "…"` with the key phrases of the *old* wording (2–3 distinctive phrases, numbers
    or locators), and review what it queues like any other item.

  Resolve each item with an outcome and its basis (`review.py done`): *corrected* (the page was changed), *unchanged*
  (it uses the revised content and still holds), or *not-affected* (it does not use the part that changed). The basis
  names what was checked, such as the sentences that cite the changed page; a keyword search may choose what to read
  but is not a basis. Read those citing sentences first (`review.py list --context`) and open the whole dependent page
  only when they use the changed content, so each item costs about the same however large the wiki grows. Resolutions go to `reviewed.md` and are never re-queued. `--strict` lint fails while items are open.

### Page templates (AGENTS.md §5)

Frontmatter uses the YAML subset `tools/wikimeta.py` parses: `key: value` lines with plain or quoted scalars, flow
lists `[a, "b, c"]` and flow maps `{K: "v"}`. Quote any list element that contains a comma. Required fields are marked *.
Fields marked *generated* are written by tools, never by hand.

### 5.1 Source page — `sources/<citekey>.md`

```yaml
---
type: source*
title: "…"*
summary: "…"*               # one line, about 200 characters: the page's index entry (§9)
authors: ["Smith, J.", "Doe, A."]*      # quoted; first 5, then "et al."
corporate_authors: []        # optional exact organization names also listed in authors
author_status: uncredited   # optional, only when the document itself credits no author
year: 2021*                  # integer year, or undated when no date can be verified
venue: "J. Example 12(3), 345–367"*
item_type: review*            # review | article | preprint | book | chapter | thesis | software | dataset | conference | patent | presentation | report | webpage
library: {{LIBRARY}}*        # user:<id> or group:<id>
zotero_key: ABCD1234*
citekey: smithExampleStudyTitle2021*
zotero_uri: zotero://select/library/items/ABCD1234*   # groups: zotero://select/groups/<id>/items/<key>
zotero_fingerprint: "v3 …"*   # generated by zot.py stamp
zotero_checked: 2026-01-01*   # generated by zot.py stamp
attachment_key: EFGH5678      # the PDF read
doi: 10.xxxx/…
collections: ["Path/To/Collection"]*
zotero_tags: [_review, ML-FF]
read_depth: full*
read_mode: rendered*
supplement: not-read*        # * for full and partial reads; not-read needs a reason (§2.6)
version_of: <later citekey>
ingested: 2026-01-01*
updated: 2026-01-01*
tags: [topic-tag, method-tag]
---
```

Body, in order: `# <Short title> (<First author> <year>)` with a **TL;DR**; `## Open in Zotero` (item link and a section
map of `zotero://open-pdf/library/items/<attachment_key>?page=N` links, N = 1-based PDF page index); `## Key
contributions` (3–7 bullets); `## Methods / setup`; `## Results and claims` (each with scope and locator); `## Limitations
and caveats` (the authors', then the agent's, marked); `## Connections` (links here are not evidence); `## User notes`
(the user's emphasis, `> [!user]` blocks, and a `> [!note] Reading history` with dates and exactly what was read).

A source page over 40,000 bytes (§11) is split into **part notes** `sources/<citekey>--<part>.md` (`type: source-part`,
`part_of: <citekey>`, `summary`, `created`, `updated`), each holding a chapter or group of sections verbatim. The
source page keeps the frontmatter, TL;DR, Open in Zotero map, key contributions, limitations, Reading history and one
summary line with a pointer per part. Parts are the same work's notes, never a second identity; citing a part counts
as citing the source.

Keep `authors` in credited order. Optional `corporate_authors` identifies organization names exactly as they occur in
`authors`. Its entries must be nonempty strings, without duplicates, and each must occur in `authors`. Only declared
organizations are exempt from the personal-name format. Do not add artificial personal-name punctuation to institutions.

For a metadata-only record with no author verifiable from Zotero, use `authors: []` and explain the missing attribution in Reading history. The `authors` field remains required. For a full or partial read of a document that credits no author, use `authors: []` with `author_status: uncredited` and a Reading history line "No credited author: <evidence from the rendered document>". This explicit exception must not replace a known author or turn unknown attribution in an unread document into a verified absence.

Use `year: undated` only when no publication date can be verified. Explain the missing date in Reading history and display “undated” in the source heading. Never substitute a guessed year or numeric placeholder.

### 5.2–5.5 Other pages

| Type | Frontmatter | Body |
|---|---|---|
| concept `concepts/<name>.md` | `type`*, `summary`*, `aliases`, `tags`, `sources`* (generated), `created`*, `updated`* | definition paragraph; `## Details`; `## Variants / approaches`; `## Evidence and debates`; `## Open questions`; `## Related` |
| entity `entities/<name>.md` | as concept, plus `entity_kind`* (`model \| method \| software \| dataset \| benchmark \| instrument \| material \| organism \| site \| group \| person`) | what it is; `## Key facts`; `## How it fits`; `## Reported performance and issues`; `## Sources` |
| topic `topics/<name>.md` | `type`*, `summary`*, `zotero_collections`* (`{KEY: "path"}`), `sources`* (generated), `created`*, `updated`* | `## Scope` (the mirrored collections, then coverage by state from `zot.py coverage --recursive`, as a line or a table); `## Current synthesis` (what the wiki believes, by open question); `## Map`; `## Timeline`; `## Open questions and tensions`; `## Reading queue` (each with a reason) |
| analysis `analyses/<yyyy-mm-dd>-<slug>.md` | `type`*, `summary`*, `question`* (verbatim), `sources`* (generated), `created`* | the answer, tables, charts in `analyses/assets/`, the pages relied on |

`sources:` is exactly the source pages the body cites; `tools/catalog.py --apply` derives it.

### Query search mechanics (AGENTS.md §8.3)

Find pages by search. Where qmd is set up (`.qmd` at the wiki root; tools/README.md), refresh it with `qmd update && qmd
embed && qmd cleanup`, then use `qmd query` with `intent:`, `lex:` and `vec:` lines you write yourself, and `qmd search`
for exact names. Otherwise use `tools/search.py` (try several phrasings, synonyms and abbreviations; narrow with
`--type` or `--collection`).

### Claim audit procedure (AGENTS.md §8.5)

1. **Sample** about 10 claims from the topic synthesis and concept pages, favoring quantitative claims, verdicts,
   headings and single-source claims. Record how the sample was drawn.
2. **Trace** each claim to the source page and then to the rendered PDF page it cites.
3. **Record every finding**, typed: *transcription* (a number, unit or equation differs) · *scope* (a system, condition,
   comparator or metric dropped) · *attribution* (wrong source, or secondary cited as primary) · *inference* (a
   conclusion the scoped evidence does not support) · *locator*. The **verdict** is the most serious finding:
   *supported* · *scope-narrowed* · *misattributed* · *unsupported* · *not checkable* (no PDF, no SI, ambiguous locator;
   inability to verify, not evidence against). Check conclusions as well as numbers. Keep confirmed and unchecked items
   apart in the report.
4. **Fix and propagate** (§4), including `review.py restated` for each corrected claim, and save the audit as
   `analyses/<date>-claim-audit.md`.

### Index format (AGENTS.md §9)

`catalog.py --apply` writes `index.md` below its preamble (the text before `## Topics`, which stays editorial).
Sections in order: Topics, Sources, Concepts, Entities, Analyses. One line per page, sorted (sources by first author,
then year; other pages by name): `- [[page|Display]] — summary · <metadata>`. Display is "First-author year, title" for
a source and the page's `# ` heading otherwise. The summary is the page's `summary:` field, which is editorial; the
header counts and the metadata (sources: `· <collection> · <read_depth>`; others: `· <n> sources`) are generated. Never
edit index lines by hand: change the page's `summary:` or heading. Agents read the index only through
`catalog.py --nav` (§8.1) and find pages by search (§8.3), so the index is not split by size.

### Size limit (AGENTS.md §11)

- **Size limit**: a page over 40,000 bytes (about 10k tokens) is split, because every integration, review or audit
  reads the whole page. A concept, entity or topic page becomes a parent page and child pages by sub-question, a
  source page becomes part notes (§5.1). `split.py` moves a section verbatim and leaves the heading, a one-line
  summary and a pointer. A split is claim-neutral (`review.py since --neutral PARENT`). An analysis kept as a
  historical record is marked `frozen: true`, is exempt and is no longer edited. Lint warns (`size`) above the limit
  (rule added 2026-11-01, extended to source pages and analyses the same day).

### Tool maintenance (AGENTS.md §12)

- **Tools are maintained in the installed skill** (`{{SKILL_DIR}}`), so one copy stays the source and fixes reach every
  wiki made from it. To change a tool: edit it in `{{SKILL_DIR}}/assets/wiki-template/tools/`, run
  `python3 -I {{SKILL_DIR}}/assets/wiki-template/tools/test_tools.py`, commit there if the skill is a git clone, then run
  `python3 {{SKILL_DIR}}/scripts/init_wiki.py --upgrade-tools .` here (it tests, logs and commits). `wikilint.py` warns
  (`tools`) while `tools/` differs from the skill or the skill is missing.
