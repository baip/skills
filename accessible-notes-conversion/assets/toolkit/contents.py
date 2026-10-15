#!/usr/bin/env python3
"""
The project's table of contents, read from contents.yaml.

Every build script gets its document list from here, so a document is named in
one place rather than in four. Usage:

    python3 contents.py            # show the list and what each build will do

The one field that matters day to day is `checked`. A document with
`checked: false` is kept off the website: mkweb.py does not stage it, no page
is built and nothing links to it. Everything else still covers it, because the
point of holding it back is to have something to proofread from: md2tex.py
writes its LaTeX, buildtex.py builds and checks its PDF,
scripts/figures_audit.py counts its figures and package.py puts it in the
archive.

Where documents live: the lectures in src/, one offering's homework and
exams in a course-year folder such as 2026/. Each document's generated .tex
and its PDF sit beside its Markdown.
"""

import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
FILE = HERE / "contents.yaml"
SRC = "src"                       # the folder the lectures are in


class Doc:
    __slots__ = ("path", "checked", "part")

    def __init__(self, path, checked, part):
        self.path = path              # relative to the project root, with .md
        self.checked = bool(checked)
        self.part = part

    @property
    def stem(self):
        """The path without .md: "src/09_Mixtures", "2026/homework01_solution".

        The .tex and the .pdf are this with their own extension, beside the
        Markdown.
        """
        return self.path[:-3] if self.path.endswith(".md") else self.path

    @property
    def web(self):
        """The page's path on the website: "09_Mixtures", "2026/homework01_solution".

        The src/ prefix is dropped, so the lectures are published at the
        top of the site, as they always have been.
        """
        prefix = SRC + "/"
        return self.stem[len(prefix):] if self.stem.startswith(prefix) else self.stem

    @property
    def name(self):
        """Just the file's own name, without a folder."""
        return Path(self.path).stem

    @property
    def file(self):
        return HERE / self.path

    def __repr__(self):
        return "Doc(%s, checked=%s)" % (self.path, self.checked)


class Part:
    __slots__ = ("title", "documents")

    def __init__(self, title, documents):
        self.title = title
        self.documents = documents

    def published(self):
        return [d for d in self.documents if d.checked]


# What the settings default to when contents.yaml leaves them out. These are
# the only places a course's name appears in the toolkit: the scripts ask for
# a setting and never spell one out themselves.
DEFAULTS = {
    "title": "Course notes",           # website title, first line of its index
    "project": "Course notes",         # Sphinx's project name
    "short": "",                       # short course name, for running feet
    "author": "",
    "copyright": "",
    "intro": ("Accessible transcriptions of the course notes. Every figure "
              "carries a written description, and every equation is real "
              "text rather than a picture."),
    "latex_class": "notes",            # the .cls file, without the extension
    "archive": "course-notes",         # package.py writes <archive>.zip
    "support": [],                     # extra files package.py should ship
    "language": "en",
    "show_source": False,
}


def site(key, default=None):
    """One site-wide setting from the `site:` block of contents.yaml."""
    data = yaml.safe_load(FILE.read_text(encoding="utf-8")) or {}
    value = (data.get("site") or {}).get(key)
    if value is None:
        return DEFAULTS.get(key) if default is None else default
    return value


def parts():
    """Every part, in the order the sidebar shows them."""
    data = yaml.safe_load(FILE.read_text(encoding="utf-8")) or {}
    out = []
    for p in data.get("parts", []):
        title = p.get("title", "")
        docs = [Doc(d["path"], d.get("checked", False), title)
                for d in p.get("documents", [])]
        out.append(Part(title, docs))
    return out


def documents(published_only=False):
    """Every document, in reading order."""
    out = [d for p in parts() for d in p.documents]
    return [d for d in out if d.checked] if published_only else out


def find(name):
    """Look a document up by path, stem or bare name. None if unknown."""
    want = str(name)
    for ext in (".md", ".tex", ".pdf"):
        if want.endswith(ext):
            want = want[:-len(ext)]
    want = want.replace("\\", "/")
    for d in documents():
        if want in (d.path, d.stem, d.web, d.name):
            return d
    return None


def discrepancies():
    """Entries with no file, and Markdown files this list does not mention.

    Both are worth failing a build over. A missing file is a typo. A file that
    is not listed is worse: it is silently absent from the website, the
    archive and every check, and nothing else would ever say so.
    """
    listed = {d.path for d in documents()}
    missing = sorted(p for p in listed if not (HERE / p).exists())

    # A document left at the top of the project, rather than in src/, is
    # reported too, so a stray copy cannot shadow the real one.
    NOT_DOCUMENTS = {"CONVENTIONS.md", "BUILD.md", "README.md"}
    on_disk = {p.name for p in HERE.glob("*.md") if p.name not in NOT_DOCUMENTS}
    on_disk |= {"%s/%s" % (SRC, p.name) for p in (HERE / SRC).glob("*.md")}
    for folder in sorted(HERE.glob("[0-9][0-9][0-9][0-9]")):
        if folder.is_dir():
            on_disk |= {"%s/%s" % (folder.name, p.name)
                        for p in folder.glob("*.md")}
    unlisted = sorted(on_disk - listed)
    return missing, unlisted


def main():
    missing, unlisted = discrepancies()
    for p in parts():
        print("\n%s" % p.title)
        for d in p.documents:
            print("  [%s] %s" % ("published" if d.checked else "  held   ",
                                 d.path))
    n = len(documents())
    pub = len(documents(published_only=True))
    print("\n%d document(s): %d on the website, %d held back."
          % (n, pub, n - pub))
    print("All %d are converted, built as PDFs, checked and archived." % n)
    print("\nSite: %s. LaTeX class %s.cls, archive %s.zip, show_source = %s."
          % (site("title"), site("latex_class"), site("archive"),
             site("show_source")))
    for path in missing:
        print("  listed but not on disk:", path, file=sys.stderr)
    for path in unlisted:
        print("  on disk but not listed:", path, file=sys.stderr)
    sys.exit(1 if (missing or unlisted) else 0)


if __name__ == "__main__":
    main()
