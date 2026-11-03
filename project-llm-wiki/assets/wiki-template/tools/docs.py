#!/usr/bin/env python3
"""Read-only access to the user's document folder (the raw root) for the wiki agent.

Policy (AGENTS.md §2.1): the wiki never modifies the raw root. This tool only reads files there. Extracted text,
embedded media, converted PDFs and rendered pages go to a temp directory outside both the wiki and the raw root.
Word, PowerPoint and Excel files are rendered through a PDF made by LibreOffice (headless) when it is installed,
else by Microsoft Word or PowerPoint on macOS (AppleScript) or Windows (PowerShell), always from a temp copy.
The only wiki writes are `stamp`, which records a provenance fingerprint in a source page's frontmatter, and the
review items that `stamp` and `changed --queue` add to pending.md.

The raw root comes from $PROJECT_WIKI_RAW_ROOT, else `raw_root` in tools/config.json (written at setup).
FILE arguments may be absolute, start with ~, or be relative to the raw root; they must lie inside it.

Usage:
  docs.py status                          # raw root, and the converters found (pandoc, poppler, textutil, and for
                                          # rendering Office files: LibreOffice, else Word/PowerPoint on macOS
                                          # or Windows)
  docs.py ls PATH [--recursive] [--all]   # documents under PATH (renditions grouped by name) with ingestion state
  docs.py info FILE                       # metadata, hash, renditions, suggested doc_id, file URL, existing page
  docs.py text FILE                       # extracted text (and embedded media) -> temp dir, one path per line
  docs.py render FILE [--pages 3-7] [--dpi 150]   # pages -> PNG files in a temp dir, to view as images
  docs.py clean                           # delete the temp dir (rendered pages, text, media, converted PDFs)
  docs.py fingerprint FILE [FILE...]      # f1 content hashes, in the order given
  docs.py stamp PAGE|DOC_ID [...] | ALL   # record the fingerprint of a page's files; queues dependents first if
                                          # their content changed (an argument naming no source page is an error)
  docs.py changed [--queue]               # source pages whose files changed, moved or disappeared since stamping
  docs.py locate PAGE [--under PATH] [--deep]     # find a moved file by its stamped hash (same name first)
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import zipfile
from xml.etree import ElementTree as ET

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikimeta import (FP_VERSION, atomic_write, load_pages, parse_fingerprint, propagate,  # noqa: E402
                      queue_reviews, source_states)

PENDING_HEADER = """# Pending review

Pages whose synthesis must be re-checked against their sources. Items are added by
`docs.py changed --queue`, `docs.py stamp`, `review.py touched|since|restated`, or by hand. Resolve an item with
`review.py done PAGE --outcome O --basis TEXT [--cause ID]` only after re-reading the page against its sources;
the resolution is kept in reviewed.md. Re-stamping a source does **not** clear its dependents.
`wikilint.py --strict` fails while items remain.

"""
WIKI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(os.environ.get("TMPDIR", tempfile.gettempdir()), "project-wiki")
JUNK = re.compile(r"^(~\$|\.~lock|\._|\.DS_Store$|Icon\r?$|desktop\.ini$|Thumbs\.db$)|\.(tmp|crdownload|part)$", re.I)
OFFICE = {".docx", ".doc", ".pptx", ".ppt", ".odt", ".odp", ".rtf", ".xlsx", ".xls", ".ods", ".dotx", ".potx"}
TEXTUTIL = {".doc", ".rtf", ".odt", ".rtfd", ".wordml", ".html", ".htm"}
PLAIN = {".md", ".txt", ".org", ".csv", ".bib", ".tsv"}
NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
      "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
      "dc": "http://purl.org/dc/elements/1.1/", "dcterms": "http://purl.org/dc/terms/",
      "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"}


# ---------------------------------------------------------------- the raw root and its paths

def raw_root():
    """The raw root, resolved (symlinks followed), or exit with advice."""
    root = os.environ.get("PROJECT_WIKI_RAW_ROOT")
    if not root:
        cfg = os.path.join(WIKI, "tools", "config.json")
        try:
            root = json.load(open(cfg, encoding="utf-8")).get("raw_root")
        except (OSError, ValueError):
            root = None
    if not root:
        sys.exit("No raw root: set raw_root in tools/config.json or $PROJECT_WIKI_RAW_ROOT.")
    root = os.path.realpath(os.path.expanduser(root))
    if not os.path.isdir(root):
        sys.exit(f"The raw root {root} is not a readable folder (is the cloud drive mounted?).")
    return root


def resolve(arg, root=None):
    """(absolute real path, path relative to the raw root) of a FILE or PATH argument, or exit."""
    root = root or raw_root()
    p = os.path.expanduser(arg)
    if not os.path.isabs(p):
        p = os.path.join(root, p)
    real = os.path.realpath(p)
    if real != root and not real.startswith(root + os.sep):
        sys.exit(f"{arg} is outside the raw root {root}; the wiki reads only files inside it.")
    if not os.path.exists(real):
        sys.exit(f"{arg} does not exist (moved or renamed? `docs.py locate PAGE`).")
    return real, os.path.relpath(real, root).replace(os.sep, "/")


def file_url(path):
    return pathlib.Path(path).as_uri()


def url_path(url):
    """The local path of a file:// URL (any OS), else None."""
    if not url.startswith("file://"):
        return None
    import urllib.request
    return os.path.normpath(urllib.request.url2pathname(urllib.parse.urlparse(url).path))


def out_dir(*parts):
    d = os.path.join(TMP, *parts)
    real = os.path.realpath(d) if os.path.exists(d) else os.path.abspath(d)
    assert not real.startswith(os.path.realpath(WIKI) + os.sep), "refusing to write inside the wiki"
    os.makedirs(d, exist_ok=True)
    return d


def sha8(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:8]


def soffice():
    return shutil.which("soffice") or next((p for p in ("/Applications/LibreOffice.app/Contents/MacOS/soffice",
                                                        r"C:\Program Files\LibreOffice\program\soffice.exe",
                                                        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe")
                                            if os.path.exists(p)), None)


WORD_EXT = {".docx", ".doc", ".dotx", ".rtf", ".odt"}
PPT_EXT = {".pptx", ".ppt", ".potx", ".odp"}
# Microsoft Office scripts: AppleScript on macOS, PowerShell (COM automation) on Windows. Office opens a temp copy
# (never the original, so no `~$` lock file lands in the raw root), saves a PDF, closes without saving, and quits if
# it was not running before.
OFFICE_PROGID = {"word": "Word.Application", "powerpoint": "PowerPoint.Application"}
OFFICE_PS = {
    "word": """$ErrorActionPreference = 'Stop'; $src, $dst = $args[0], $args[1]
$was = [bool](Get-Process WINWORD -ErrorAction SilentlyContinue)
$app = New-Object -ComObject Word.Application; $app.DisplayAlerts = 0
$doc = $app.Documents.Open($src, $false, $true)
$doc.ExportAsFixedFormat($dst, 17); $doc.Close(0)
if (-not $was) { $app.Quit() }""",
    "powerpoint": """$ErrorActionPreference = 'Stop'; $src, $dst = $args[0], $args[1]
$was = [bool](Get-Process POWERPNT -ErrorAction SilentlyContinue)
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Open($src, -1, 0, 0)
$pres.SaveAs($dst, 32); $pres.Close()
if (-not $was) { $app.Quit() }""",
}
OFFICE_SCRIPT = {
    "word": ("Microsoft Word", """on run argv
  set wasRunning to application "Microsoft Word" is running
  tell application "Microsoft Word"
    open (POSIX file (item 1 of argv)) read only true
    save as active document file name (item 2 of argv) file format format PDF
    close active document saving no
    if not wasRunning then quit saving no
  end tell
end run"""),
    "powerpoint": ("Microsoft PowerPoint", """on run argv
  set wasRunning to application "Microsoft PowerPoint" is running
  tell application "Microsoft PowerPoint"
    open (POSIX file (item 1 of argv))
    set p to active presentation
    save p in (POSIX file (item 2 of argv)) as save as PDF
    close p saving no
    if not wasRunning then quit
  end tell
end run"""),
}


_OFFICE_FOUND = {}


def office_app(kind):
    """True if the Microsoft Office app for `kind` can be scripted here: macOS with the app installed (AppleScript),
    or Windows with its COM class registered (PowerShell). Linux and WSL use LibreOffice."""
    if kind not in _OFFICE_FOUND:
        if sys.platform == "darwin":
            app = OFFICE_SCRIPT[kind][0]
            _OFFICE_FOUND[kind] = bool(shutil.which("osascript")) and any(
                os.path.isdir(os.path.join(d, app + ".app")) for d in ("/Applications", os.path.expanduser("~/Applications")))
        elif os.name == "nt" and powershell():
            r = subprocess.run([powershell(), "-NoProfile", "-Command",
                                f"if ([type]::GetTypeFromProgID('{OFFICE_PROGID[kind]}')) {{ 'yes' }}"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            _OFFICE_FOUND[kind] = r.stdout.strip() == "yes"
        else:
            _OFFICE_FOUND[kind] = False
    return _OFFICE_FOUND[kind]


def powershell():
    return shutil.which("powershell") or shutil.which("pwsh")


def office_command(kind, src, dst):
    if sys.platform == "darwin":
        return ["osascript", "-e", OFFICE_SCRIPT[kind][1], src, dst]
    return [powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
            "& {" + OFFICE_PS[kind] + "}", src, dst]


def converters(ext):
    """Converters able to make a PDF of an `ext` file, in the order to try: LibreOffice when installed (headless, no
    app windows or permission prompts), then the Microsoft Office app for that format. $PROJECT_WIKI_CONVERTER=office
    puts Office first (its layout matches what the user sees)."""
    out = []
    if soffice():
        out.append("libreoffice")
    if ext in WORD_EXT and office_app("word"):
        out.append("word")
    if ext in PPT_EXT and office_app("powerpoint"):
        out.append("powerpoint")
    if os.environ.get("PROJECT_WIKI_CONVERTER") == "office":
        out.sort(key=lambda c: c == "libreoffice")
    return out


# ---------------------------------------------------------------- source pages and their files

def source_pages(pages=None):
    for name, versions in (pages or load_pages()).items():
        pg = versions[0]
        if pg["dir"] == "sources" and pg["fields"].get("type") == "source":
            yield name, pg


def page_files(pg):
    f = pg["fields"].get("files")
    return [str(x) for x in f] if isinstance(f, list) else []


def file_index(pages=None):
    """relative path -> source page name, over every page's files:."""
    return {p: name for name, pg in source_pages(pages) for p in page_files(pg)}


# ---------------------------------------------------------------- status, ls, info

def cmd_status(a):
    root = raw_root()
    print(f"OK: raw root {root}")
    for tool, use in (("pandoc", "Word text and media"), ("pdftoppm", "rendering PDF pages"),
                      ("pdfinfo", "PDF page counts"), ("pdftotext", "PDF text"),
                      ("textutil", ".doc/.rtf/.odt text (macOS)")):
        print(f"  {tool:9s} {'found' if shutil.which(tool) else 'MISSING'}  ({use})")
    for ext, label in ((".docx", "Word files"), (".pptx", "PowerPoint files"), (".xlsx", "Excel files")):
        conv = converters(ext)
        print(f"  render {label:16s} via {', then '.join(conv) if conv else 'NOTHING: install LibreOffice (brew install --cask libreoffice)'}")


def is_junk(name):
    return bool(JUNK.search(name))


def documents(folder, recursive):
    """{(dir, stem): [file names]} under folder; renditions of one document share a directory and a stem."""
    docs = {}
    for d, subdirs, files in os.walk(folder):
        subdirs[:] = sorted(s for s in subdirs if not s.startswith(".")) if recursive else []
        for f in sorted(files):
            if is_junk(f) or f.startswith("."):
                continue
            docs.setdefault((d, os.path.splitext(f)[0].lower()), []).append(f)
    return docs


def cmd_ls(a):
    root = raw_root()
    folder, rel = resolve(a.path, root)
    if os.path.isfile(folder):
        folder = os.path.dirname(folder)
    index = file_index()
    states = {name: state for name, state in source_states().values()}
    mark = {"metadata": "m", "read": "r", "integrated": "x"}
    counts, n = {}, 0
    for (d, _), names in sorted(documents(folder, a.recursive).items(), key=lambda kv: (kv[0][0].lower(), kv[0][1])):
        exts = [os.path.splitext(x)[1].lower() for x in names]
        if not a.all and not any(e in OFFICE | TEXTUTIL | PLAIN | {".pdf", ".tex", ".key", ".pages"} for e in exts):
            continue
        rels = [os.path.relpath(os.path.join(d, x), root).replace(os.sep, "/") for x in names]
        page = next((index[r] for r in rels if r in index), None)
        state = states.get(page, "none") if page else "none"
        counts[state] = counts.get(state, 0) + 1
        n += 1
        newest = max(os.path.getmtime(os.path.join(d, x)) for x in names)
        date = datetime.date.fromtimestamp(newest).isoformat()
        size = sum(os.path.getsize(os.path.join(d, x)) for x in names)
        stem = os.path.splitext(rels[0])[0]
        print(f"[{mark.get(state, ' ')}] {date} | {','.join(e.lstrip('.') for e in exts):14s} | {size / 1e6:7.2f} MB | "
              f"{stem}" + (f"  -> [[{page}]]" if page else ""))
    print(f"\n{n} documents under {rel}: " + ", ".join(f"{counts.get(s, 0)} {s}" for s in ("integrated", "read", "metadata", "none")))
    print("legend: [x] integrated  [r] read, not yet integrated  [m] metadata only  [ ] no page;  "
          "renditions = same folder and name, other extension")


def zip_xml(z, name):
    try:
        return ET.fromstring(z.read(name))
    except (KeyError, ET.ParseError):
        return None


def office_props(path):
    """Core and app properties of an OOXML file (title, creator, dates, pages/slides/words)."""
    out = {}
    try:
        with zipfile.ZipFile(path) as z:
            core = zip_xml(z, "docProps/core.xml")
            if core is not None:
                for tag, key in (("dc:title", "title"), ("dc:creator", "creator"), ("cp:lastModifiedBy", "last_modified_by"),
                                 ("dcterms:created", "created"), ("dcterms:modified", "modified"), ("cp:revision", "revision")):
                    el = core.find(tag, NS)
                    if el is not None and (el.text or "").strip():
                        out[key] = el.text.strip()
            app = zip_xml(z, "docProps/app.xml")
            if app is not None:
                for tag in ("Pages", "Slides", "Words", "Company"):
                    el = app.find("ep:" + tag, NS)
                    if el is not None and (el.text or "").strip():
                        out[tag.lower()] = el.text.strip()
    except (zipfile.BadZipFile, OSError):
        out["error"] = "not a readable OOXML (zip) file"
    return out


def pdf_props(path):
    if not shutil.which("pdfinfo"):
        return {}
    r = subprocess.run(["pdfinfo", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = {}
    for line in r.stdout.splitlines():
        k, _, v = line.partition(":")
        if k in ("Title", "Author", "CreationDate", "ModDate", "Pages") and v.strip():
            out[k.lower()] = v.strip()
    return out


def tex_props(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for cmd in ("documentclass", "title", "author", "date"):
        m = re.search(r"\\" + cmd + r"\s*(?:\[[^\]]*\])?\s*\{((?:[^{}]|\{[^{}]*\})*)\}", text)
        if m:
            out[cmd] = " ".join(m.group(1).split())[:200]
    out["main"] = "yes" if re.search(r"\\begin\{document\}", text) else "no (a fragment; find the main file)"
    return out


def cmd_info(a):
    root = raw_root()
    path, rel = resolve(a.file, root)
    if os.path.isdir(path):
        sys.exit(f"{a.file} is a folder; use `docs.py ls`.")
    ext = os.path.splitext(path)[1].lower()
    st = os.stat(path)
    h = sha8(path)
    print(f"file: {rel}")
    print(f"url: {file_url(path)}")
    print(f"size: {st.st_size} bytes; modified {datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')}")
    print(f'sha8: {h}  (for a new page: doc_id: "{h}", quoted)')
    props = office_props(path) if ext in OFFICE and ext not in (".doc", ".ppt", ".xls", ".rtf") else \
        pdf_props(path) if ext == ".pdf" else tex_props(path) if ext == ".tex" else {}
    for k, v in props.items():
        print(f"{k}: {v}")
    hidden = pptx_hidden(path)
    if hidden:
        print(f"hidden slides: {', '.join(map(str, hidden))} (render shows them unless --skip-hidden)")
    d, stem = os.path.dirname(path), os.path.splitext(os.path.basename(path))[0].lower()
    sib = [f for f in sorted(os.listdir(d)) if not is_junk(f) and os.path.splitext(f)[0].lower() == stem
           and os.path.join(d, f) != path]
    print("renditions: " + (", ".join(sib) if sib else "none (no other file with this name in the folder)"))
    if ext == ".tex":
        tex_main = [f for f in sorted(os.listdir(d)) if f.endswith(".pdf")]
        print("pdfs in folder: " + (", ".join(tex_main) if tex_main else "none"))
    index = file_index()
    print("page: " + (f"[[{index[rel]}]]" if rel in index else "none yet"))


# ---------------------------------------------------------------- text extraction

def docx_text_stdlib(path):
    """Paragraph text of a .docx without pandoc (tables flattened, one paragraph per line)."""
    with zipfile.ZipFile(path) as z:
        root = zip_xml(z, "word/document.xml")
    if root is None:
        return ""
    out = []
    for p in root.iter("{%s}p" % NS["w"]):
        out.append("".join(t.text or "" for t in p.iter("{%s}t" % NS["w"])))
    return "\n".join(out)


def rels_of(z, part):
    """{rId: target path inside the zip} for an OOXML part."""
    d, base = os.path.split(part)
    root = zip_xml(z, f"{d}/_rels/{base}.rels")
    out = {}
    for r in (root if root is not None else []):
        target = r.get("Target", "")
        if r.get("TargetMode") == "External":
            continue
        out[r.get("Id")] = os.path.normpath(os.path.join(d, target)).replace(os.sep, "/") if not target.startswith("/") else target[1:]
    return out


def shape_text(root):
    paras = []
    for p in root.iter("{%s}p" % NS["a"]):
        t = "".join(x.text or "" for x in p.iter("{%s}t" % NS["a"])).strip()
        if t:
            paras.append(t)
    return paras


def pptx_slide_parts(z):
    """The slide parts of an open .pptx zip in presentation order (file-name order if presentation.xml lacks it)."""
    pres = zip_xml(z, "ppt/presentation.xml")
    prels = rels_of(z, "ppt/presentation.xml")
    order = []
    if pres is not None:
        for s in pres.iter("{%s}sldId" % NS["p"]):
            rid = s.get("{%s}id" % NS["r"])
            if rid in prels:
                order.append(prels[rid])
    if not order:
        order = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                       key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
    return order


HIDE_EXT = {".pptx", ".pptm", ".potx"}  # zip formats whose slides carry show="0" when hidden


def pptx_hidden(path):
    """Numbers (presentation order, from 1) of the hidden slides of a .pptx, [] for other formats."""
    if os.path.splitext(path)[1].lower() not in HIDE_EXT:
        return []
    try:
        with zipfile.ZipFile(path) as z:
            return [i for i, part in enumerate(pptx_slide_parts(z), 1)
                    if (root := zip_xml(z, part)) is not None and root.get("show") == "0"]
    except (zipfile.BadZipFile, OSError):
        return []


def unhidden_copy(path, d):
    """A copy of a .pptx in directory d (same file name) with every slide's hidden flag cleared, so converters
    render all slides and PDF page N is slide N. The original is only read."""
    dest = os.path.join(d, os.path.basename(path))
    with zipfile.ZipFile(path) as z, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
        slides = set(pptx_slide_parts(z))
        for item in z.infolist():
            data = z.read(item.filename)
            if item.filename in slides:  # drop show="0" from the root <p:sld> start tag only
                data = re.sub(rb'<(?!\?)([\w.-]+:)?sld\b[^>]*>',
                              lambda m: re.sub(rb'\s+show\s*=\s*["\']0["\']', b"", m.group(0)), data, count=1)
            out.writestr(item, data)
    return dest


def pptx_extract(path, media_dir):
    """Markdown text of a .pptx in presentation order: each slide's text, its embedded images (copied to
    media_dir) and its speaker notes. Returns (text, [image paths])."""
    lines, images = [], []
    with zipfile.ZipFile(path) as z:
        order = pptx_slide_parts(z)
        for i, part in enumerate(order, 1):
            root = zip_xml(z, part)
            if root is None:
                continue
            hidden = root.get("show") == "0"
            lines.append(f"\n## Slide {i}" + (" (hidden)" if hidden else ""))
            lines += [f"- {t}" for t in shape_text(root)]
            srels = rels_of(z, part)
            used = {e.get("{%s}embed" % NS["r"]) for e in root.iter("{%s}blip" % NS["a"])}
            for rid in sorted(x for x in used if x in srels):
                target = srels[rid]
                ext = os.path.splitext(target)[1].lower()
                if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".svg", ".emf", ".wmf"):
                    continue
                dest = os.path.join(media_dir, f"slide{i:03d}-{os.path.basename(target)}")
                try:
                    with z.open(target) as src, open(dest, "wb") as out:
                        shutil.copyfileobj(src, out)
                except KeyError:
                    continue
                images.append(dest)
                lines.append(f"- [image: {dest}]")
            notes = next((t for t in srels.values() if "notesSlide" in t), None)
            nroot = zip_xml(z, notes) if notes else None
            if nroot is not None:
                ntext = [t for t in shape_text(nroot) if not re.fullmatch(r"\d+", t)]
                if ntext:
                    lines.append("- Notes: " + " / ".join(ntext))
    return "\n".join(lines).strip() + "\n", images


def xlsx_extract(path):
    """Tab-separated cell values of each sheet of an .xlsx (values as last saved; formulas not evaluated)."""
    out = []
    with zipfile.ZipFile(path) as z:
        sst = zip_xml(z, "xl/sharedStrings.xml")
        strings = ["".join(t.text or "" for t in si.iter("{%s}t" % NS["s"])) for si in sst] if sst is not None else []
        wb = zip_xml(z, "xl/workbook.xml")
        wrels = rels_of(z, "xl/workbook.xml")
        sheets = [(s.get("name"), wrels.get(s.get("{%s}id" % NS["r"]))) for s in wb.iter("{%s}sheet" % NS["s"])] if wb is not None else []
        for name, part in sheets:
            root = zip_xml(z, part) if part else None
            if root is None:
                continue
            out.append(f"\n## Sheet: {name}")
            for row in root.iter("{%s}row" % NS["s"]):
                cells = []
                for c in row.iter("{%s}c" % NS["s"]):
                    v = c.find("s:v", NS)
                    t = c.get("t")
                    if t == "s" and v is not None:
                        val = strings[int(v.text)] if v.text and v.text.isdigit() and int(v.text) < len(strings) else ""
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["s"]))
                    else:
                        val = v.text if v is not None and v.text else ""
                    cells.append(" ".join(val.split()))
                if any(cells):
                    out.append("\t".join(cells))
    return "\n".join(out).strip() + "\n"


TEX_INPUT = re.compile(r"(?<!\\)\\(input|include|subfile)\s*\{([^}]+)\}")
TEX_GRAPHICS = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
TEX_BIB = re.compile(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")


def tex_flatten(path, root_dir=None, seen=None, depth=0):
    """A LaTeX file with \\input/\\include/\\subfile expanded in place (comment lines kept), with markers naming each
    included file. Returns (text, [missing inputs], [graphics references], [bibliographies])."""
    root_dir = root_dir or os.path.dirname(path)
    seen = seen if seen is not None else set()
    missing, graphics, bibs = [], [], []
    if depth > 20 or os.path.realpath(path) in seen:
        return f"%% [docs.py] skipped {path}: include cycle or nesting too deep\n", missing, graphics, bibs
    seen.add(os.path.realpath(path))
    text = open(path, encoding="utf-8", errors="replace").read()
    out = []
    for line in text.splitlines(keepends=True):
        code = re.split(r"(?<!\\)%", line, maxsplit=1)[0]
        graphics += TEX_GRAPHICS.findall(code)
        for b in TEX_BIB.findall(code):
            bibs += [x.strip() for x in b.split(",")]
        m = TEX_INPUT.search(code)
        if not m:
            out.append(line)
            continue
        name = m.group(2).strip()
        cand = [os.path.join(root_dir, name), os.path.join(root_dir, name + ".tex"),
                os.path.join(os.path.dirname(path), name), os.path.join(os.path.dirname(path), name + ".tex")]
        found = next((c for c in cand if os.path.isfile(c)), None)
        if not found:
            missing.append(name)
            out.append(line)
            continue
        sub, mi, gr, bi = tex_flatten(found, root_dir, seen, depth + 1)
        missing += mi
        graphics += gr
        bibs += bi
        out.append(code[:m.start()] + f"\n%% >>> begin {os.path.relpath(found, root_dir)}\n" + sub +
                   f"\n%% <<< end {os.path.relpath(found, root_dir)}\n" + code[m.end():] + ("\n" if line.endswith("\n") else ""))
    return "".join(out), missing, graphics, bibs


def graphics_paths(base_dir, refs):
    """Resolve \\includegraphics references to files (trying the usual extensions)."""
    out = []
    for ref in dict.fromkeys(refs):
        for ext in ("", ".pdf", ".png", ".jpg", ".jpeg", ".eps"):
            p = os.path.join(base_dir, ref + ext)
            if os.path.isfile(p):
                out.append(p)
                break
        else:
            out.append(f"(not found) {ref}")
    return out


def to_pdf(path, h, skip_hidden=False):
    """A PDF of an office file in the temp dir (cached by content hash), made by the first converter that works
    (`converters`). Never opens the original in an editor: Office gets a temp copy. Hidden slides of a .pptx are
    rendered (from a copy with the hidden flags cleared, so page N is slide N) unless skip_hidden."""
    ext = os.path.splitext(path)[1].lower()
    hidden = pptx_hidden(path)
    d = out_dir("pdf", h, ("visible" if skip_hidden else "all")) if hidden else out_dir("pdf", h)
    pdf = os.path.join(d, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    if os.path.exists(pdf):
        return pdf
    src = unhidden_copy(path, out_dir("unhide", h)) if hidden and not skip_hidden else path
    tried = []
    for conv in converters(ext):
        if conv == "libreoffice":
            profile = pathlib.Path(out_dir("lo-profile", h)).as_uri()  # one per document: parallel readers may convert at once
            r = subprocess.run([soffice(), f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
                                "--outdir", d, src], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        else:
            work = out_dir("convert", h)
            copy = os.path.join(work, "in" + ext)
            shutil.copyfile(src, copy)
            r = subprocess.run(office_command(conv, copy, pdf), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
            shutil.rmtree(work, ignore_errors=True)
        if r.returncode == 0 and os.path.exists(pdf):
            return pdf
        tried.append(f"{conv}: {(r.stderr or r.stdout).strip()[:200] or 'no PDF produced'}")
    if not tried:
        sys.exit(f"No converter can render {ext} files here: install LibreOffice (macOS: brew install --cask libreoffice; "
                 "Debian/Ubuntu: apt install libreoffice; Windows: winget install TheDocumentFoundation.LibreOffice), "
                 "or Microsoft Word/PowerPoint on macOS or Windows. Meanwhile render a PDF "
                 "rendition if one exists, or read it with `docs.py text` and record read_mode: source or text-index.")
    sys.exit(f"Could not convert {path} to PDF:\n  " + "\n  ".join(tried))


def cmd_text(a):
    """Extract a file's text (and embedded images) to the temp dir. Prints the files to read, one per line."""
    path, rel = resolve(a.file, raw_root())
    ext = os.path.splitext(path)[1].lower()
    h = sha8(path)
    base = os.path.splitext(os.path.basename(path))[0]
    d = out_dir("text", h)
    out = os.path.join(d, base + ".md")
    if ext in PLAIN:
        print(f"{path}\t(plain text: read it in place)")
        return
    if ext == ".tex":
        text, missing, graphics, bibs = tex_flatten(path)
        out = os.path.join(d, base + ".flat.tex")
        open(out, "w", encoding="utf-8").write(text)
        print(f"{out}\tflattened LaTeX source ({len(text.splitlines())} lines)")
        for g in graphics_paths(os.path.dirname(path), graphics):
            print(f"{g}\tfigure (view it as an image; .pdf/.eps figures: docs.py render)")
        for b in dict.fromkeys(bibs):
            print(f"{b}\tbibliography named in the source")
        for m in missing:
            print(f"(missing input) {m}")
        return
    if ext in (".docx", ".dotx"):
        media = out_dir("media", h)
        if shutil.which("pandoc"):
            r = subprocess.run(["pandoc", "-f", "docx", "-t", "gfm+tex_math_dollars", "--wrap=none",
                                f"--extract-media={media}", path, "-o", out], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode:
                sys.exit(f"pandoc failed on {rel}: {r.stderr.strip()[:300]}")
            how = "pandoc (tracked changes accepted; tables and equations kept)"
        else:
            open(out, "w", encoding="utf-8").write(docx_text_stdlib(path))
            how = "plain paragraphs (pandoc not installed: tables flattened, equations and images lost)"
        print(f"{out}\ttext via {how}")
        for dp, _, fs in os.walk(media):
            for f in sorted(fs):
                print(f"{os.path.join(dp, f)}\tembedded image (view it)")
        return
    if ext in (".pptx", ".potx"):
        text, images = pptx_extract(path, out_dir("media", h))
        open(out, "w", encoding="utf-8").write(text)
        print(f"{out}\tslide text and speaker notes, in presentation order ({text.count('## Slide')} slides)")
        for p in images:
            print(f"{p}\tembedded image (view it)")
        return
    if ext == ".xlsx":
        out = os.path.join(d, base + ".tsv.md")
        open(out, "w", encoding="utf-8").write(xlsx_extract(path))
        print(f"{out}\tcell values per sheet (as last saved)")
        return
    if ext == ".pdf":
        if not shutil.which("pdftotext"):
            sys.exit("pdftotext not found: install poppler (brew install poppler).")
        out = os.path.join(d, base + ".txt")
        subprocess.run(["pdftotext", "-layout", path, out], check=True)
        print(f"{out}\tPDF text layer (for search and exact quotes; read the rendered pages)")
        return
    if ext in TEXTUTIL and shutil.which("textutil"):
        out = os.path.join(d, base + ".txt")
        r = subprocess.run(["textutil", "-convert", "txt", "-output", out, path], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            sys.exit(f"textutil failed on {rel}: {r.stderr.strip()[:300]}")
        print(f"{out}\ttext via textutil (layout, figures and equations lost)")
        return
    if ext in OFFICE | {".key", ".pages"}:
        if ext in (".key", ".pages"):
            sys.exit(f"{ext} files need Keynote/Pages to export a PDF; ask the user for a PDF rendition.")
        pdf = to_pdf(path, h)
        out = os.path.join(d, base + ".txt")
        subprocess.run(["pdftotext", "-layout", pdf, out], check=True)
        print(f"{out}\ttext of the PDF conversion")
        return
    sys.exit(f"No text extractor for {ext} files.")


# ---------------------------------------------------------------- rendering

def page_range(spec, n):
    """'4', '3-7', '5-' or None (all) -> (first, last), 1-based page indices within 1..n."""
    if not spec:
        return 1, n
    m = re.fullmatch(r"(\d+)(?:-(\d*))?", spec.strip())
    if not m:
        sys.exit(f"--pages must look like 4, 3-7 or 5-, not {spec!r}")
    first = int(m.group(1))
    last = n if m.group(2) == "" else int(m.group(2) or first)
    if not 1 <= first <= last <= n:
        sys.exit(f"--pages {spec} is outside this document's pages 1-{n}")
    return first, last


def cmd_render(a):
    """Render pages to PNG files outside the wiki and the raw root, so any agent that can view an image file reads
    the document as laid out (AGENTS.md §7). PDFs render directly; Word, PowerPoint and Excel files are converted
    with LibreOffice first (cached). Overwrites earlier renders of the same pages; `clean` deletes them all."""
    missing = [t for t in ("pdftoppm", "pdfinfo") if shutil.which(t) is None]
    if missing:
        sys.exit(f"{' and '.join(missing)} not found: install poppler (macOS: brew install poppler; Debian/Ubuntu: "
                 "apt install poppler-utils). Without it, read the text and record read_mode: source or text-index.")
    path, rel = resolve(a.file, raw_root())
    ext = os.path.splitext(path)[1].lower()
    h = sha8(path)
    if ext == ".pdf":
        pdf = path
    elif ext in OFFICE:
        pdf = to_pdf(path, h, a.skip_hidden)
    elif ext == ".tex":
        sys.exit("LaTeX is read from its source (`docs.py text`, read_mode: source); render its compiled PDF if one "
                 "exists (`docs.py info` lists PDFs in the folder). The wiki never compiles in the raw root.")
    else:
        sys.exit(f"No renderer for {ext} files; ask the user for a PDF rendition.")
    info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"^Pages:\s+(\d+)", info.stdout, re.M)
    if info.returncode or not m:
        sys.exit(f"pdfinfo could not read {pdf}: {(info.stderr or info.stdout).strip()}")
    n = int(m.group(1))
    first, last = page_range(a.pages, n)
    hidden = pptx_hidden(path)
    out = out_dir("pages", h, "visible") if hidden and a.skip_hidden else out_dir("pages", h)
    r = subprocess.run(["pdftoppm", "-r", str(a.dpi), "-f", str(first), "-l", str(last), "-png", pdf,
                        os.path.join(out, "p")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"pdftoppm failed: {r.stderr.strip()}")
    via = "" if pdf == path else f" (via a PDF conversion: {pdf})"
    if hidden:
        nums = ", ".join(map(str, hidden))
        print(f"hidden slides {nums}: skipped (--skip-hidden), so page numbers are not slide numbers" if a.skip_hidden
              else f"hidden slides {nums}: rendered (page N is slide N); say so on the page; --skip-hidden omits them")
    print(f"{rel}: pages {first}-{last} of {n} at {a.dpi} dpi{via}; view each file as an image (PAGE<TAB>PATH):")
    for f in sorted(os.listdir(out)):
        num = re.fullmatch(r"p-0*(\d+)\.png", f)
        if num and first <= int(num.group(1)) <= last:
            print(f"{num.group(1)}\t{os.path.join(out, f)}")


def cmd_clean(a):
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"removed {TMP}")


# ---------------------------------------------------------------- provenance (§4)

def fingerprint_of(paths):
    """'f1 <hash> <hash> …': one sha256 prefix per file, in the order of files:."""
    return FP_VERSION + " " + " ".join(sha8(p) for p in paths)


def _h(s):
    return hashlib.sha1(s.encode()).hexdigest()[:8]


def compare(stored, new_hashes):
    """Compare a stored fingerprint with current file hashes. Returns (status, kind):
    'ok' | 'changed' | 'incomplete'; kind None | 'content'. Order does not matter, so a file list rewritten after
    a move compares equal when no content changed. An unreadable or wrong-length baseline certifies nothing."""
    r = parse_fingerprint(stored)
    if r is None or len(r[1]) != len(new_hashes):
        return "incomplete", "content"
    return ("ok", None) if sorted(r[1].values()) == sorted(new_hashes) else ("changed", "content")


def review_entries(pages, name, kind, today, new_fp, what):
    """(page, cause, note) review items for a source whose files changed: the source, its evidence dependents,
    and (through chains of source pages that quote each other) theirs."""
    cause = f"file:{name}@{_h(new_fp)}"
    out = [(name, cause, f"document changed ({what}): re-read the changed file and update the page · {today}")]
    for d, via in sorted(propagate(pages, name).items()):
        how = f"uses [[{name}]] as evidence" if via is None else f"uses [[{via}]], which quotes [[{name}]]"
        out.append((d, cause, f"{how}; [[{name}]] changed ({what}): re-check · {today}"))
    return out


def current(pg, root):
    """([(relative path, absolute path or None if missing)]) for a page's files."""
    out = []
    for rel in page_files(pg):
        p = os.path.join(root, rel)
        out.append((rel, p if os.path.isfile(p) else None))
    return out


def cmd_fingerprint(a):
    root = raw_root()
    print(fingerprint_of([resolve(f, root)[0] for f in a.files]))


def cmd_stamp(a):
    """Record the fingerprint of a page's files. Before replacing a previous baseline, compare it; if content
    changed, or the baseline was incomplete, queue the dependents first, so an interrupted update cannot lose a
    review. A page is named by its filename or doc_id; an argument that matches nothing is an error."""
    root = raw_root()
    today = datetime.date.today().isoformat()
    wanted, matched = set(a.keys), set()
    pages = load_pages()
    for name, pg in source_pages(pages):
        hit = {name, str(pg["fields"].get("doc_id"))} & wanted
        if not (hit or "ALL" in wanted):
            continue
        matched |= hit
        files = current(pg, root)
        if not files:
            sys.exit(f"{name}: files: is empty; list the file(s) read, relative to the raw root.")
        gone = [rel for rel, p in files if p is None]
        if gone:
            sys.exit(f"{name}: not stamped, file(s) missing: {', '.join(gone)}. Find them with `docs.py locate {name}` "
                     "and correct files:, or record the loss in the Reading history.")
        hashes = [sha8(p) for _, p in files]
        fp = FP_VERSION + " " + " ".join(hashes)
        stored = pg["fields"].get("doc_fingerprint")
        queued = 0
        if stored:  # no baseline at all is a first ingest: nothing can be stale yet
            status, kind = compare(stored, hashes)
            if status != "ok":
                what = "baseline incomplete or unreadable" if status == "incomplete" else "content hash"
                deps = [e for e in review_entries(pages, name, kind, today, fp, what) if e[0] != name]
                queued = queue_reviews(deps, PENDING_HEADER)
        text = open(pg["path"], encoding="utf-8").read()
        head, sep, rest = text.partition("\n---\n")
        head = re.sub(r"^(doc_fingerprint|doc_checked):.*\n?", "", head + "\n", flags=re.M).rstrip("\n")
        head, n = re.subn(r"^(files:.*)$", lambda m: f'{m.group(1)}\ndoc_fingerprint: "{fp}"\ndoc_checked: {today}',
                          head, count=1, flags=re.M)
        if not n:
            sys.exit(f"{name}: no files: line in the frontmatter")
        atomic_write(pg["path"], head + sep + rest)
        print(f"stamped {name}: {fp}" + (f"  (queued {queued} dependent review(s) in pending.md)" if queued else ""))
    unmatched = sorted(wanted - matched - {"ALL"})
    if unmatched:
        sys.exit(f"stamped nothing for: {', '.join(unmatched)}. A source page is named by its filename or its doc_id; "
                 "`docs.py changed` lists the pages that exist.")


def cmd_changed(a):
    """List source pages whose files changed (content), disappeared (moved, renamed or deleted), or were never
    stamped. With --queue, record review items (with causes) in pending.md: content changes queue the source and
    its dependents; a missing file queues the source page only (find it with `locate`, then fix files:)."""
    root = raw_root()
    pages = load_pages()
    today = datetime.date.today().isoformat()
    queue, n = [], 0
    for name, pg in source_pages(pages):
        stored = pg["fields"].get("doc_fingerprint")
        if pg["fields"].get("read_depth") == "metadata-only" and not stored:
            continue
        if not stored:
            print(f"UNSTAMPED  {name}: run `docs.py stamp {name}`")
            n += 1
            continue
        files = current(pg, root)
        gone = [rel for rel, p in files if p is None]
        if gone:
            n += 1
            print(f"MISSING    {name}: {', '.join(gone)} -> moved, renamed or deleted; `docs.py locate {name}`")
            queue.append((name, f"file:{name}@missing-{_h(' '.join(gone))}",
                          f"file(s) missing: {', '.join(gone)}: locate them and fix files:, then `docs.py stamp {name}` · {today}"))
            continue
        hashes = [sha8(p) for _, p in files]
        status, kind = compare(stored, hashes)
        if status == "ok":
            continue
        n += 1
        fp = FP_VERSION + " " + " ".join(hashes)
        what = "baseline incomplete or unreadable" if status == "incomplete" else "content hash"
        entries = review_entries(pages, name, kind, today, fp, what)
        label = "INCOMPLETE" if status == "incomplete" else "CHANGED   "
        print(f"{label} {name}: {what} -> re-read; to review: {', '.join(p for p, _, _ in entries if p != name) or 'none'}")
        queue += entries
    print(f"{n} need attention")
    if a.queue and queue:
        print(f"queued {queue_reviews(queue, PENDING_HEADER)} item(s) in pending.md")


def cmd_locate(a):
    """Find the files of a page that are no longer at their recorded paths, by the hashes of its stamp. Looks for
    the same file name under PATH first (fast), then with --deep hashes every file with the same extension."""
    root = raw_root()
    pages = load_pages()
    pg = next((p for n, p in source_pages(pages) if a.page in (n, str(p["fields"].get("doc_id")))), None)
    if pg is None:
        sys.exit(f"No source page named {a.page}.")
    fp = parse_fingerprint(pg["fields"].get("doc_fingerprint"))
    if not fp:
        sys.exit(f"{a.page} has no complete doc_fingerprint, so its files cannot be recognized by content.")
    hashes = [fp[1][str(i)] for i in range(len(fp[1]))]
    files = page_files(pg)
    under = resolve(a.under, root)[0] if a.under else root
    todo = [(i, rel) for i, rel in enumerate(files) if not os.path.isfile(os.path.join(root, rel))]
    if not todo:
        print(f"All files of {a.page} are at their recorded paths.")
        return
    for i, rel in todo:
        want, name, ext = hashes[i] if i < len(hashes) else None, os.path.basename(rel), os.path.splitext(rel)[1].lower()
        found = []
        for deep in (False, True) if a.deep else (False,):
            for d, subdirs, fs in os.walk(under):
                subdirs[:] = [s for s in subdirs if not s.startswith(".")]
                for f in fs:
                    if (f == name if not deep else f.lower().endswith(ext)) and sha8(os.path.join(d, f)) == want:
                        found.append(os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/"))
            if found:
                break
        print(f"{rel}: " + (("found at " + "; ".join(dict.fromkeys(found))) if found else
                            "not found" + ("" if a.deep else " by name (try --deep, which hashes every file with this extension)")))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("ls"); s.add_argument("path"); s.add_argument("--recursive", action="store_true")
    s.add_argument("--all", action="store_true", help="also list files of other kinds (images, data, archives)")
    s = sub.add_parser("info"); s.add_argument("file")
    s = sub.add_parser("text"); s.add_argument("file")
    s = sub.add_parser("render"); s.add_argument("file"); s.add_argument("--pages"); s.add_argument("--dpi", type=int, default=150)
    s.add_argument("--skip-hidden", action="store_true", help="omit hidden PowerPoint slides (default: render them)")
    sub.add_parser("clean")
    s = sub.add_parser("fingerprint"); s.add_argument("files", nargs="+")
    s = sub.add_parser("stamp"); s.add_argument("keys", nargs="+", help="page names, doc_ids, or ALL")
    s = sub.add_parser("changed"); s.add_argument("--queue", action="store_true", help="add review items to pending.md")
    s = sub.add_parser("locate"); s.add_argument("page"); s.add_argument("--under"); s.add_argument("--deep", action="store_true")
    a = p.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
