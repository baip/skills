---
name: zotero-llm-wiki
description: Set up and run an LLM-maintained research wiki whose raw sources stay in the user's Zotero library (read-only, never copied), with Obsidian-style Markdown pages for sources, concepts, entities and topic syntheses, provenance fingerprints that detect Zotero changes, a review queue, lint, and claim audits. Use this whenever someone wants to turn a Zotero library or collection into a knowledge base, a literature wiki, a second brain, Karpathy-style LLM wiki or Obsidian vault built from their papers; wants an agent to read papers from Zotero and keep running notes, syntheses or a literature review up to date; or wants to upgrade the tools of an existing Zotero wiki, even if they do not say "wiki".
compatibility: Zotero 7+ desktop with the local API enabled; Python 3.9+ (standard library only); macOS or Linux (Windows via WSL); poppler (pdftoppm) so the agent can view PDF pages; optional Better BibTeX, git and Obsidian.
---

# Zotero-backed LLM wiki

The user keeps papers in Zotero; the agent reads them and writes a wiki that compiles what they say into linked Markdown
pages, then keeps it current as sources and questions accumulate. Zotero stays the single source of truth: the wiki
reads it through a read-only client and never copies PDFs, full text or notes into the wiki.

This skill does two things:

1. **Instantiate** a new wiki: a short interview, then `scripts/init_wiki.py` writes the schema (`AGENTS.md`), the
   tools, the bookkeeping files and the folder layout, and checks them.
2. **Hand over** to the wiki's own `AGENTS.md`, which governs every later session (ingest, query, lint, audit). After
   setup the skill stays the home of the tools: a tool is changed in the skill's template first and copied into the
   wiki with `init_wiki.py --upgrade-tools DEST`. The skill also explains the design (`references/design-notes.md`).

## Before you start

Check, and fix with the user, the things setup depends on:

- **Zotero is running** and its local API answers: `curl -s http://localhost:23119/api/users/0/items/top?limit=1`. If
  not, ask the user to start Zotero 7+ and tick Settings → Advanced → "Allow other applications on this computer to
  communicate with Zotero". Do not work around a closed Zotero by reading its database: the wiki's policy is to read
  Zotero only through its API, never `zotero.sqlite`.
- **PDF pages can be viewed.** The wiki's reading rule is to look at rendered pages (figures, tables and equations as
  printed), not only extracted text. In Claude Code that needs poppler (`pdftoppm`). If it is missing, offer the install
  command for their platform; if they decline, readings will be recorded as `read_mode: text-index`.
- **Python 3.9+** is available as `python3`.
- **This skill is installed**, not run from a temporary or one-off copy: at `~/.claude/skills/zotero-llm-wiki` (a
  symlink to a clone works, and picks up updates), or in any folder named by the environment variable
  `ZOTERO_LLM_WIKI_SKILL` (set it in the shell profile so later sessions see it too). The wiki keeps its tools in step
  with this installed copy: its schema says tools are changed here first, and its linter warns when `tools/` differs.
  `init_wiki.py` refuses to run from anywhere else and prints the install command; install it with the user's
  agreement, then run the installed copy.

## Setup interview

Ask only what you cannot infer, in one short round; if you cannot ask (a scripted or delegated run), infer from the
request and state each assumption in your report. Each answer goes into the generated files:

| Question | Why it matters | Where it goes |
|---|---|---|
| Where should the wiki live? | A new or empty folder. Opening it in Obsidian is optional but pleasant. | `DEST` |
| Who reads it, in one sentence? (field, expertise, what they build or decide) | The writing-style rule: what to explain, what to skip, which units and notation to use. | `--audience` |
| Is that folder synced by Google Drive, Dropbox, OneDrive or iCloud? | Sync services corrupt `.git` folders, so the git directory must live outside the synced folder. | `--git separate` (or `inside`, or `none`) |
| Which Zotero collection comes first? | The first topic. | the `next:` line |

For a synced folder, `--git separate` puts the git directory at `~/.local/share/zotero-llm-wiki/<folder name>.git`;
suggest that, or any path outside the synced folder the user prefers (`--git separate:PATH`). Parent folders are
created as needed.

Then run, from the installed skill's folder:

```
python3 scripts/init_wiki.py DEST --audience "SENTENCE" --git inside|separate[:PATH]|none [--library user:ID]
                             [--trailer "LINE"]
```

If your host asks for attribution lines on commits (for example a `Co-Authored-By:` line), pass each as `--trailer`
so the script's commit carries them; the same option works with `--upgrade-tools`.

The library id is read from the running Zotero if `--library` is left out. The script checks every input before writing
anything, refuses a non-empty `DEST`, fills the templates, creates the folders, runs the bundled tool tests and the
strict linter on the empty wiki, and makes the initial commit if git is set up. If setup fails partway, it removes what
it wrote, so a rerun starts clean. Report what it printed; if anything failed, fix that before going on.

**If the user asked only for setup**, stop here: report the location, the git arrangement, and the next steps (pick a
collection and a first paper, then a guided ingest), and do not read any papers.

## First session in the new wiki

Read the new `AGENTS.md` in full: from here on it is the operating manual, and it is written to be followed by any agent,
not just you. Then, with the user:

1. `python3 -I tools/zot.py collections --match "WORDS"` to find the collection key (matching is case-insensitive and by
   word starts; if it reports several top-level matches or only close spellings, ask the user which collection they
   mean), and `zot.py items KEY` to list it. Some users keep a collection's own items in a `_root` subcollection: the
   topic then mirrors the parent collection, and `zot.py coverage PARENT --recursive` counts everything under it.
2. **Ask the user to pick the first paper.** Offer three to five candidates from the collection that have a PDF, with
   one line each on why they would make a good start (central to the topic, well known to the user, clean PDF). Pick one
   yourself only if the user has explicitly left the choice to you, and say why you chose it.
3. **Ingest it in guided mode** (AGENTS.md §8.2): read its rendered pages, give 3–6 takeaways, ask what to emphasize,
   then write the source page, stamp it, and create the topic page for the collection. One paper done carefully, with the
   user steering, sets the tone for every later page. If the user has said not to wait for their emphasis, ingest it in
   delegated mode instead: skip the discussion, and say so under `## User notes`, e.g. *(Nothing yet. No Zotero notes or
   annotations as of 2026-10-19. Delegated ingest, so there was no discussion. The page stresses X because the user
   works on Y.)*. The TL;DR and key contributions carry the takeaways; your report (§8.2 step 8) says what the paper
   changed in the wiki, so the user can redirect the emphasis later.
4. Finish the way every changing interaction finishes: `catalog.py --apply`, update `log.md`, `wikilint.py --strict`,
   and one commit of the paths you changed.

Suggest what comes next (more of the collection, possibly as a batch per §8.2b), and mention that a claim audit (§8.5)
after the first substantial batch is the only check that tests the knowledge rather than the structure.

## Changing tools and upgrading a wiki

Tools are never edited inside a wiki. To fix or extend one, edit it in this skill's `assets/wiki-template/tools/`, add a
test to `test_tools.py` there and run `python3 -I assets/wiki-template/tools/test_tools.py`; if the skill folder is a git
clone, commit the change there. Then bring it into each wiki with the upgrade. One copy stays the source, so a fix made
for one wiki reaches every wiki made from the skill, and no wiki drifts into its own variant.

`python3 scripts/init_wiki.py --upgrade-tools DEST` replaces only the Python tools, runs the tests and the linter there
(errors only, so open review items from other work do not block it), and, if they pass, appends a `fix` entry to `log.md` and commits the changed tools and the log (in a git repository; if
`log.md` already had uncommitted edits it leaves the commit to you). Git history keeps the old tools; outside git they
are copied to a temp folder, never into the wiki. It never touches pages, `AGENTS.md` or `tools/README.md`, but prints
the template's README rows for the tools that changed: show those to the user and update their README if they agree.
If the user's schema has diverged from the template, compare the two and propose changes; the schema is theirs
(AGENTS.md §1, §8.6). Before upgrading, run `git status`: uncommitted changes of unknown authorship are the user's to
resolve first (AGENTS.md §2.10).

## What not to do

- Do not modify Zotero in any way (no writes through the API, no edits in its data folder). Suggest library changes, such
  as attaching a missing PDF, to the user.
- Do not copy PDFs, full text, verbatim abstracts or Zotero notes into the wiki. Extracted text goes to a temp directory
  outside it.
- Do not instantiate into a folder that already has content, and do not overwrite an existing wiki's schema.

## Files

- `scripts/init_wiki.py`: create a wiki, or upgrade its tools.
- `assets/wiki-template/`: the schema, bookkeeping files and tools that a new wiki starts from. `{{…}}` placeholders are
  filled by the script.
- `references/design-notes.md`: why the schema looks the way it does: reading rules, provenance, review propagation,
  audits, and what failed while it was developed. Read it when the user asks why a rule exists, wants to change one, or
  hits a problem the schema does not cover.
