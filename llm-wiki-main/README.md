# llm-wiki-main: maintenance notes

This README is about maintaining the skill; it stays out of the package. `SKILL.md` is what an agent reads.

## Where it comes from

Named `project-llm-wiki` until 2026-11-11, when it was renamed `llm-wiki-main` to match the wiki it maintains. Older
wiki log entries and commits use the old name.


Adapted on 2026-11-02 from `llm-wiki-zotero` (this repository, commit cad8b4c), whose schema came out of a working
literature wiki after six external reviews and four claim audits. The raw layer changed from a Zotero library to a
folder of the user's own documents; the reading, provenance, review, lint, catalog, search and audit machinery is
kept. What differs is listed in `references/design-notes.md` §1.

The two skills keep separate copies of the generic tools (`wikimeta.py`, `review.py`, `catalog.py`, `search.py`,
`split.py`, `relink.py`, `wikilint.py`). A fix to one of them in either skill should be considered for the other:
`diff -r ../llm-wiki-zotero/assets/wiki-template/tools assets/wiki-template/tools` shows what differs. Expected
differences: `zot.py` vs `docs.py`, the identity and fingerprint code, the page types (`projects/`), reuse blocks,
claim status, the cross-platform locks and UTF-8 file handling (not yet in llm-wiki-zotero).

## The skill is the home of the tools

Edit `assets/wiki-template/tools/`, add a test, run `python3 -I assets/wiki-template/tools/test_tools.py`, commit
here, then run `init_wiki.py --upgrade-tools` in each wiki. Wikis' `wikilint.py` warns (`tools`) when their tools
differ from the installed skill (`~/.claude/skills/llm-wiki-main`, a symlink to this folder, or
`$PROJECT_LLM_WIKI_SKILL`).

Policy (schema) changes start in a wiki, where a real ingest or audit shows the need; port them to
`assets/wiki-template/AGENTS.md` by hand, keeping the placeholders.

Smoke test from the installed path:
`python3 ~/.claude/skills/llm-wiki-main/scripts/init_wiki.py "$TMPDIR/w" --audience "test" --raw-root "$TMPDIR"
--git none` must report tool tests OK and strict lint OK; then delete it. Package with
`python3 ../package.py llm-wiki-main`.

## Platforms

Developed and tested on macOS (Word, PowerPoint and LibreOffice conversion all exercised). The Windows paths
(PowerShell COM automation of Word and PowerPoint, `msvcrt` locks, `C:\Program Files\LibreOffice`) and Linux
(LibreOffice only) are written to the same interfaces but were **not yet run on those systems**; the first Windows or
Linux user should run the test suite and one `docs.py render` of a .docx and a .pptx and report back.

## Evaluations

`evals/evals.json` holds test prompts. Runs and grading live in `../llm-wiki-main-workspace/` (git-ignored).
