# skills

Each folder holds a `SKILL.md` and the references, scripts and assets it points
to, following the Agent Skills format, so the same folder works in the Claude
app, Claude Code and other hosts that read `SKILL.md`.

## The skills

| Skill | What it does | Needs |
|---|---|---|
| [`accessible-notes-conversion`](accessible-notes-conversion/) | Converts handwritten, typed or OneNote-exported course notes, homework solutions and exams into accessible Markdown that builds a tagged PDF (PDF/UA-1) and a website (WCAG 2.1 AA), with figures redrawn as described SVG and equations typeset with a spoken form. | Python 3.10+, pandoc 3, TeX Live 2024+ with LuaLaTeX, and, for the website, Sphinx, MathJax 3 and Playwright. See its [README](accessible-notes-conversion/README.md). |
| [`funding-monitor`](funding-monitor/) | Monitors research funding announcements for a US academic researcher: builds a research-fit profile, scans Grants.gov, NSF and NIH feeds, optional Simpler.Grants.gov and SAM.gov APIs, agency and institutional web pages and funding newsletters, and writes a ranked digest with deadlines. | Python 3.11+ and outbound HTTPS. Optional API keys, Playwright for pages built by JavaScript, and an email connector for newsletters. |
| [`zotero-llm-wiki`](zotero-llm-wiki/) | Sets up an LLM-maintained research wiki whose sources stay in the user's Zotero library (read-only), with source, concept, entity and topic pages, provenance fingerprints that detect Zotero changes, a review queue, lint and claim audits; also upgrades the tools of an existing wiki. | Zotero 7+ with the local API on, Python 3.9+ (standard library), macOS or Linux (Windows via WSL), poppler to view PDF pages; optional Better BibTeX, git and Obsidian. |

## Installing a skill

Build the installable files from the repository root:

```
python3 package.py                     # every skill, to dist/<name>.skill
python3 package.py funding-monitor     # only the named skill(s)
python3 package.py --list              # what each package would hold, writing nothing
```

- **Claude app:** open `dist/<name>.skill` and save it. Saving a newer
  build replaces the installed one.
- **Claude Code:** link or copy the skill's folder into `~/.claude/skills/`,
  for example `ln -s "$PWD/funding-monitor" ~/.claude/skills/funding-monitor`.
  A link picks up every later change without reinstalling.
- **Codex and OpenCode:** link the folder into `~/.agents/skills/`, which
  both read: `ln -s "$PWD/funding-monitor" ~/.agents/skills/funding-monitor`.
  OpenCode also reads `~/.claude/skills/`, so a Claude Code link serves it
  too. Codex's documentation names `~/.agents/skills/` as of October 2026,
  and older versions read `~/.codex/skills/`.
- **Other hosts:** install the folder, or unzip the `.skill` file, wherever
  the host looks for skills.

`package.py` checks each `SKILL.md` header before packaging (a kebab-case
name that matches the folder, a description of at most 1024 characters,
and only the header fields the app accepts). It leaves out each skill's
`README.md`, Python caches and anything `.gitignore` excludes.

## Personal data stays out

The repository holds shareable skills only. `.gitignore` keeps out what is
personal or generated, and `package.py` follows it, so none of this reaches
a commit or a package:

- built packages in `dist/`
- a personal funding-monitor profile at `funding-monitor/config/profile.toml`
- funding scan state and output
- local secrets files such as `.env`

For `funding-monitor`, keep the personal profile at
`~/.config/funding-monitor/profile.toml` and the API keys in the host's
secret store or in environment variables, never in the profile.
`funding-monitor/config/credentials.toml` declares which keys exist and
what each one unlocks. A personal build with the profile bundled inside is
made by the skill's own setup in a chat, and should not be shared onward.

## Adding a skill

1. Make a folder at the top of the repository, named for the skill in
   kebab-case, with a `SKILL.md` whose `name` matches the folder.
2. Put anything about maintaining the skill, rather than using it, in the
   folder's `README.md`, which stays out of the package.
3. Add ignore rules for anything the skill writes that is personal or
   generated.
4. Run `python3 package.py --list <name>` to check what the package will
   hold, then `python3 package.py <name>`.

Commit the sources only. The `.skill` files are build products.
