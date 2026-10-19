# zotero-llm-wiki: maintenance notes

This README is about maintaining the skill; it stays out of the package. `SKILL.md` is what an agent reads.

## Where it comes from

The template is distilled from a working wiki (`research/zotero-wiki`, 140+ pages on machine-learned interatomic
potentials) after six external reviews and four claim audits. Differences from that wiki:

- `AGENTS.md`: domain examples replaced by neutral ones; `{{LIBRARY}}`, `{{AUDIENCE}}`, `{{GIT_LOCATION}}` filled at
  setup; no freeze at birth (§8.6 proposes one after the first ingests and an audit); the founding "LLM wiki" idea is
  summarized in the opening paragraph instead of shipping a third-party `llm-wiki.md`.
- `tools/README.md`: machine-specific notes replaced by `{{GIT_DETAILS}}`, `{{ENVIRONMENT}}`, `{{DATE}}`.
- Tool changes not yet in the source wiki:
  - `zot.py`: Zotero data directory from `$ZOTERO_DATA_DIR` or the profile's `dataDir` (macOS, Linux, Windows profile
    paths); a generated citekey in Better BibTeX's default style when neither Zotero 7's field nor Better BibTeX supplies
    one (matches the real BBT key for 72 of 73 BBT-style keys in the source wiki; the miss, `novelliFinetuningFoundationModels`,
    is a BBT key without a year although the item now has one, so it was probably generated before the date was set); `status` prints the library id;
    `collections --match` matches word starts case-insensitively with a fuzzy fallback; `notes`/`annotations` say when
    there are none.
  - `review.py since` reports new pages separately from changed ones.
  - `wikilint.py`: wider `entity_kind` set (method, instrument, material, organism, site).
  - every tool sets `sys.dont_write_bytecode`, so no `__pycache__` lands in a cloud-synced wiki.
  - `test_tools.py`: tests for all of the above.
- `init_wiki.py --trailer` adds attribution lines (e.g. `Co-Authored-By:`) to its commits, as the source wiki's commits carry.
- `gitignore` ships without its dot (some hosts drop dotfiles); `init_wiki.py` renames it.

## The skill is the home of the tools

Since 2026-10-19 the tools are changed here first, for the source wiki as for any other: edit
`assets/wiki-template/tools/`, add a test, run `python3 -I assets/wiki-template/tools/test_tools.py`, commit in this
repository, then run `init_wiki.py --upgrade-tools` in each wiki. The wikis' `AGENTS.md` (§12) states the rule, and their
`wikilint.py` warns (`tools`) when a wiki's tools differ from the installed skill. That is why the skill must be
installed (`~/.claude/skills/zotero-llm-wiki`, here a symlink to this folder, or `$ZOTERO_LLM_WIKI_SKILL`):
`init_wiki.py` refuses to run from any other copy.

Policy (schema) changes still start in a wiki, where a real ingest or audit shows the need:

1. Diff the source wiki's `AGENTS.md` against `assets/wiki-template/AGENTS.md` and port policy changes by hand, keeping
   the placeholders and neutral examples.
2. Smoke test from the installed path: `python3 ~/.claude/skills/zotero-llm-wiki/scripts/init_wiki.py "$TMPDIR/w"
   --audience "test" --git none --library user:1` must report tool tests OK and strict lint OK; then delete it.
3. `python3 ../package.py --list zotero-llm-wiki`, then `python3 ../package.py zotero-llm-wiki`.

## Evaluations

`evals/evals.json` holds three test prompts (new wiki with a first ingest; setup only in a cloud-synced folder; tool
upgrade of an existing wiki). Runs and grading live in `../zotero-llm-wiki-workspace/`, which is git-ignored.
