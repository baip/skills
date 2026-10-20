# Building the {{SHORT}} notes

There is one source, the Markdown files, and two builds come out of it. The
lectures are in `src/`, one offering's homework and exams in a year folder
such as `2026/`, and each document's `.tex` and `.pdf` are written beside
its Markdown. Every command below is run from the top of the project.

```
                     ┌─ mkweb.py   → Sphinx + MyST + MathJax → site/   (website)
Markdown (*.md) ─────┤
                     └─ md2tex.py  → {{CLASS}}.cls → lualatex → *.pdf  (tagged PDF)
```

Mathematics is LaTeX between dollar signs, so both builds read the same
equations. The `.tex` files are generated output, never source.

## One-time setup

```
# PDF build
#   TeX Live 2024 or later with lualatex (MacTeX, or apt install texlive-full)
#   pandoc 3 or later
pip install cairosvg pypdf pyyaml

# website build
pip install sphinx myst-parser furo
npm install                    # MathJax 3, from package.json, into node_modules/
pip install playwright         # for checkweb.py; then: playwright install chromium

# figures
#   DejaVu Sans and DejaVu Sans Oblique, which figlib measures labels with
#   (a system install, ~/Library/Fonts, or the copy inside matplotlib)
pip install pillow
```

## Running under other coding agents

`AGENTS.md` holds the instructions: Codex and OpenCode load it by themselves,
and Claude Code loads it through `CLAUDE.md`. Every step is a plain command,
so what differs between agents is only what they are allowed to do. The work
needs:

1. Writes in this folder, `.git` included, and in the skill's folder when a
   toolkit fix goes into the skill first.
2. Running `python3`, `git`, `lualatex`, `pandoc`, `pdftoppm`, and the
   Chromium that Playwright starts for `checkweb.py`.
3. Viewing local image files: the rendered pages of the originals, the
   contact sheets and the rendered PDF pages.
4. The network, but only for the one-time installs above.

- **Claude Code** works as is. Approve its prompts, or allow these commands
  in its settings.
- **Codex.** Its default `workspace-write` sandbox blocks the network and
  writes outside the folder it was started in. Start it from this folder and
  add the skill's folder (resolved, if it is a link) to the writable roots
  in `~/.codex/config.toml`:

  ```toml
  sandbox_mode = "workspace-write"
  [sandbox_workspace_write]
  writable_roots = ["<skill folder, resolved>"]
  ```

  Set `network_access = true` in the same table only while installing. The
  key names are as of 2026, and newer versions may offer permission
  profiles instead, so check the Codex documentation for yours. Some
  versions keep `.git` read-only even inside the workspace: if a commit is
  refused, approve running it outside the sandbox. Do the same if
  `checkweb.py` cannot start its browser inside the sandbox.
- **OpenCode** has no sandbox by default, but its permission settings
  (`opencode.json`) may ask before shell commands and edits. Allow
  `python3`, `git`, `lualatex`, `pandoc` and the poppler commands.
- **An agent without parallel helpers** (subagents) does a revision across
  many documents one or two at a time, as the skill's
  `references/notation-pass.md` describes.
- **An agent that cannot view images** cannot transcribe, draw or check
  figures. Give it only work that needs no looking.

## The everyday loop

```
python3 scripts/figures/make_figures_03.py  # writes figures/fig_c03_*.svg
python3 md2tex.py 03_Second_Law             # writes src/03_Second_Law.tex
python3 buildtex.py 03_Second_Law           # src/03_Second_Law.pdf, 12 checks
python3 mkweb.py && python3 checkweb.py     # website, 9 checks per page
python3 scripts/figures_audit.py            # disk, references and scripts agree
python3 package.py                          # {{ARCHIVE}}.zip, from contents.yaml
```

A document is named by its bare name (`03_Second_Law`,
`homework01_solution`) or by its path (`src/03_Second_Law.md`).
`md2tex.py --all` and `buildtex.py --all` do every document.

## What gets published: contents.yaml

```
python3 contents.py            # the list, and what each build does with it
```

Each entry carries `checked: true` or `false`. `false` keeps the document off
the website but still builds its PDF, which is what you proofread from. Change
the word and run `mkweb.py` to publish. Adding a document means adding it here.
`scripts/figures_audit.py` fails on a Markdown file that is not listed, and
`package.py` will not build an archive while the audit fails.

The `site:` block holds the project-wide settings:

| Key | What it does |
|---|---|
| `title` | website title and front-page heading |
| `project` | the Sphinx project name |
| `short` | the short course name, for a PDF running foot the frontmatter leaves out |
| `author`, `copyright` | the website footer |
| `intro` | the paragraph under the front-page heading |
| `latex_class` | the class file every PDF uses (`{{CLASS}}`) |
| `archive` | `package.py` writes `<archive>.zip` |
| `support` | extra files the archive should carry (data modules, helpers) |
| `language` | the documents' language |
| `show_source` | Sphinx's "Show Source" link. `false` also keeps the Markdown out of `_sources/` |

## The website

```
python3 mkweb.py               # builds into site/
python3 mkweb.py --serve       # builds, then serves on http://localhost:8000
python3 checkweb.py            # nine accessibility checks, page by page
```

`mkweb.py` stages a copy of the Markdown into `web/`, adjusting it for MyST on
the way: fenced divs become directives, image paragraphs become MyST figures
carrying their alt text, `[](#fig-…)` becomes `` {numref}`…` ``, and the
frontmatter becomes the page title and subtitle. The sources are not touched.
It also renumbers figures per page, writes `site.css`, which sets captions
flush left, and drops the `src/` folder from the lectures' addresses.

Sphinx wraps every display equation that contains a line break (`\\`, as in
`aligned` or `\substack`) in `split`, where MathJax refuses `\tag`. Such
equations are staged as a `:nowrap:` math block inside `equation*`, so their
number prints. `checkweb.py` fails on any formula MathJax renders as an
error, since such a formula otherwise counts as typeset.

MathJax is served from the site rather than from a content delivery network,
so the notes work on a network that blocks the CDN. `mkweb.py` looks in the
project's `node_modules/`, then in npm's global root.
`NOTES_MATHJAX=/path/to/mathjax` overrides the search. Without MathJax the
site still builds, but equations arrive as raw TeX with no MathML behind
them, which defeats the point of the website.

To publish, copy `site/` to any static host (GitHub Pages, a department web
server).

The website is where the mathematics is most accessible: MathJax adds a
hidden MathML copy of every formula, so a screen reader can speak it and a
reader can walk through it term by term. `checkweb.py` confirms that copy
exists for every formula on every page.

## The PDFs

`buildtex.py` converts any figure whose SVG is newer than its PDF, runs
lualatex twice so the page count in the footer settles, runs twelve
checks, and exits non-zero if any fail: ten on the tagged structure, the
formula-alternative check below, and one that reads the log for characters
the fonts lack. It also warns about anything more than 10 pt too wide for
the page. It compiles from the project root, so the class file and the
figures resolve wherever the `.tex` is, and writes the scratch files and the
PDF beside the `.tex`.

### The check that depends on your TeX Live

Check 11, "formula alternative text is not raw LaTeX", fails on older TeX
Live (tagpdf before 1.0), where the alternative text of every formula is its
LaTeX source and a screen reader announces "LaTeX formula starts, begin
equation, frac…". Run a build on the machine that will produce the published
PDFs and look at the last lines first:

```
python3 buildtex.py 01_Example | tail -3
```

If check 11 still fails there, update TeX Live (`tlmgr update --self --all`)
before publishing. Equations written with `::: {.eq alt="…"}` carry their own
sentence and pass regardless.

### The PDF version is stated

Each `.tex` begins

```latex
\DocumentMetadata{lang=en, pdfversion=1.7, pdfstandard=ua-1,
                  testphase={phase-III,math,table,firstaid}}
```

From LaTeX 2025-06-01 a tagged document defaults to PDF 2.0, but PDF/UA-1 is
a PDF 1.7 standard, and tagpdf aborts if the version changes after it has
loaded ("The PDF version has changed after the loading of tagpdf"). Stating
1.7 up front avoids that. Moving to PDF/UA-2 means changing the pair
together: `pdfversion=2.0, pdfstandard=ua-2`.

### Workarounds in the class

- **Tables carry no rules.** `\hline` and booktabs rules abort the tagged
  run. Tables are set open with the header row in bold sans.
- **Tables are `longtable`.** The tagging code takes header rows from
  `\endhead`. A plain `tabular` would tag every cell `/TD` and fail check 10.
- **No `[H]` floats.** The `float` package is not compatible with the
  tagging code. Figures are `[!ht]` with loosened float parameters, and
  `::: flush` is the only placement control.
- **No `caption` package.** The tagging code handles captions itself.
  `\figcaption` sets them flush left by passing `\RaggedRight` and a
  full-width `\hspace` into the caption text with no group round them,
  because a group ends before the paragraph does and the setting is lost.

### When a build fails

| Symptom | Usual cause |
|---|---|
| "text-unit para hooks differ" | a list or display equation that never entered horizontal mode. Check the list is outside `::: eq` |
| "PDF version has changed after the loading of tagpdf" | `pdfversion` and `pdfstandard` disagree |
| a symbol missing from the PDF, fine on the web | the text font lacks it. Write it as mathematics |
| a figure off the bottom of a page | a figure right after a long table. Move it before the table |
| "too wide for the page" warning | a wide table or long equation. Shorten headers, or break the equation with `aligned` |
| "\tag not allowed in split environment" on the web | an old `mkweb.py`; update the toolkit |
| "Figure ??" | a `[](#fig-…)` with no figure of that id. `md2tex.py` reports these |
| a table's cells run together on the web | not a pipe table |

## Keeping the figure set honest

```
python3 scripts/figures_audit.py    # report; --delete removes the orphans
python3 package.py --list           # what the archive would contain
```

The audit compares the SVG files on disk, the figures the Markdown
references and the names the drawing scripts write, and fails if they
disagree. Renaming a figure leaves the old file behind, and this is what
catches it.

## Updating the toolkit

The build scripts came from the `accessible-notes-conversion` skill. To take
a newer version without touching the documents, drawing scripts, class file
or this file:

```
python3 <skill>/scripts/init_project.py . --update-toolkit
```

A project from before the `src/` and `scripts/` layout is refused, because
the new scripts expect it. To move one over: `git mv` the lectures into
`src/`, `make_figures_*.py`, `figlib.py` and data helpers into
`scripts/figures/`, and `figures_audit.py` into `scripts/`. Then rewrite
the lectures' figure links from `](figures/` to `](../figures/`, prefix
their `contents.yaml` paths with `src/`, update `.gitignore` (the
template's PDF section), and run the update again. Regenerate a few
documents' `.tex` before and after the move and compare them: they should
differ only in their first line.
