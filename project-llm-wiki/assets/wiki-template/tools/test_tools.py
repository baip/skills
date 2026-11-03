#!/usr/bin/env python3
"""Regression tests for the wiki tools. Stdlib only, no network: documents are small files written to a temporary
raw root. Run from the wiki root: python3 -I tools/test_tools.py  (exits 1 on failure)."""
import argparse
import contextlib
import copy
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.realpath(tempfile.mkdtemp(prefix="wiki-raw-test-"))
os.environ["PROJECT_WIKI_RAW_ROOT"] = RAW  # read on every call, so every tool sees the test raw root
import docs  # noqa: E402
import relink  # noqa: E402
import wikilint  # noqa: E402
import wikimeta  # noqa: E402
from wikimeta import parse_frontmatter, protected_text, synthesis_body, links  # noqa: E402

FAILS = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def fm(s):
    return parse_frontmatter(f"---\n{s}\n---\nbody\n")


def write(rel, data):
    """Write a file under the test raw root (bytes or text) and return its absolute path."""
    p = os.path.join(RAW, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    return p


def refused(fn, *a, **k):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn(*a, **k)
        return False
    except SystemExit:
        return True


def run(fn, **kw):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        fn(argparse.Namespace(**kw))
    return buf.getvalue()


# ---- parser ----------------------------------------------------------------------------------
check("quoted '#' is not a comment", fm('title: "Model #1"')[0].get("title") == "Model #1")
check("comment after quoted value", fm('title: "Model #1"  # note')[0].get("title") == "Model #1")
check("comment after plain value", fm("read_depth: full  # see §2.6")[0].get("read_depth") == "full")
check("'#' inside a flow-list element", fm('tags: [a, "b #c"]  # x')[0].get("tags") == ["a", "b #c"])
check("quoted author keeps its comma", fm('authors: ["Bai, P.", "Siepmann, J. I."]')[0].get("authors") == ["Bai, P.", "Siepmann, J. I."])
check("unquoted author splits (and lint must flag it)", fm("authors: [Bai, P.]")[0].get("authors") == ["Bai", "P."])
check("unterminated quote is an error", fm('title: "unterminated')[2] != [])
check("unbalanced bracket is an error", fm("tags: [a, b")[2] != [])
check("text after closing quote is an error", fm('title: "a" b')[2] != [])
check("flow map", fm('m: {A1: "P/x"}')[0].get("m") == {"A1": "P/x"})
check("file paths with spaces and commas survive quoting",
      fm('files: ["Proposals/NSF CAREER/Bai, P. draft.docx", "a.pdf"]')[0].get("files") == ["Proposals/NSF CAREER/Bai, P. draft.docx", "a.pdf"])
check("integer year", fm("year: 2021")[0].get("year") == 2021)
check("duplicate key is an error", any("duplicate" in e for e in fm("a: 1\na: 2")[2]))
check("'' decodes to one apostrophe", fm("title: 'O''Brien'")[0].get("title") == "O'Brien")
check("escaped quote + comma stays one list element", fm('tags: ["a \\" , b", c]')[0].get("tags") == ['a " , b', "c"])
check("unsupported escape rejected", fm('title: "bad \\q"')[2] != [])
check("stray quote in single-quoted string rejected", fm("title: 'a'b'")[2] != [])

# ---- field validation ------------------------------------------------------------------------
BASE = dict(type="source", title="T", authors=["Bai, P."], year=2021, doc_kind="proposal", doc_id="0123abcd",
            files=["P/a.docx", "P/a.pdf"], read_file="P/a.pdf", read_depth="full", read_mode="rendered",
            ingested="2026-10-17", updated="2026-10-17", doc_checked="2026-10-18",
            doc_fingerprint="f1 0000000a 0000000b")


def errors_for(**changes):
    f = copy.deepcopy(BASE)
    f.update(changes)
    errs = []
    wikilint.check_fields("x", {k: v for k, v in f.items() if v is not None}, errs)
    return errs


def has(errs, text):
    return any(text in m for _, m in errs)


check("baseline source page is valid", errors_for() == [])
check("source read (LaTeX or Word text with figures viewed) is valid", errors_for(read_mode="source", read_file="P/a.docx") == [])
check("text-index read needs no read_file", errors_for(read_mode="text-index", read_file=None) == [])
check("metadata-only record is valid", errors_for(read_depth="metadata-only", read_mode="none", read_file=None,
                                                  doc_fingerprint=None, doc_checked=None) == [])
check("every doc_kind in the schema is valid", all(errors_for(doc_kind=k) == [] for k in wikilint.DOC_KINDS))
check("unknown doc_kind rejected", has(errors_for(doc_kind="memo-ish"), "doc_kind"))
check("my_role validated", errors_for(my_role="PI") == [] and has(errors_for(my_role="boss"), "my_role"))
check("rendered without read_file rejected", has(errors_for(read_file=None), "no read_file"))
check("read_file must be one of files:", has(errors_for(read_file="P/other.pdf"), "not in files:"))
check("absolute file path rejected", has(errors_for(files=["/Users/x/a.pdf"], read_file=None, read_mode="text-index",
                                                    doc_fingerprint="f1 0000000a"), "relative to the raw root"))
check("Windows separators rejected", has(errors_for(files=["P\\a.pdf"], read_file=None, read_mode="text-index",
                                                     doc_fingerprint="f1 0000000a"), "/ separators"))
check("a path listed twice rejected", has(errors_for(files=["P/a.pdf", "P/a.pdf"]), "twice"))
check("full read without a fingerprint rejected", has(errors_for(doc_fingerprint=None), "lacks doc_fingerprint"))
check("fingerprint count must match files:", has(errors_for(doc_fingerprint="f1 0000000a"), "1 hash(es) for 2 file(s)"))
for bad, why in [("f1", "bare version"), ("f1 zz", "malformed hash"), ("v3 biblio:0000000a abstract:none pdf:none notes:none ann:none", "Zotero format")]:
    check(f"incomplete fingerprint rejected by lint ({why})", has(errors_for(doc_fingerprint=bad), "incomplete or malformed"))
check("doc_id must be 8 lowercase hex digits", has(errors_for(doc_id="ABCD1234"), "doc_id"))
check("an all-digit doc_id must be quoted (a number would drop leading zeros)",
      has(errors_for(doc_id=1234567), 'doc_id must be quoted, e.g. doc_id: "01234567"') and errors_for(doc_id="01234567") == [])
check("partial dates accepted, malformed rejected",
      errors_for(date="2024-08") == [] and errors_for(date="2024-08-15") == [] and has(errors_for(date="Aug 2024"), "date="))
check("empty authors invalid for full reads", has(errors_for(authors=[]), "missing authors"))
check("explicitly uncredited full source is valid", errors_for(authors=[], author_status="uncredited") == [])
check("uncredited flag cannot coexist with a named author", has(errors_for(author_status="uncredited"), "requires authors: []"))
check("declared corporate author is valid", errors_for(authors=["National Science Foundation"], corporate_authors=["National Science Foundation"]) == [])
check("undeclared corporate author rejected", has(errors_for(authors=["National Science Foundation"]), "author entry"))
check("arbitrary year string rejected", has(errors_for(year="unknown"), "year must be"))
check("undated is a valid year", errors_for(year="undated") == [])
check("list-valued title rejected", has(errors_for(title=["a", "b"]), "title must be a single string"))
check("read_depth full + read_mode none rejected", has(errors_for(read_mode="none"), "cannot have read_mode"))
_e = []
wikilint.check_fields("x", {"type": ["source"]}, _e)
check("type: [source] reported, not a crash", has(_e, "type"))
PROJ = dict(type="project", summary="s", sponsor="NSF", status="awarded", sources=["s"], created="2026-01-01", updated="2026-01-01")
_e = []
wikilint.check_fields("p", PROJ, _e)
check("project page with sponsor and status is valid", _e == [])
_e = []
wikilint.check_fields("p", dict(PROJ, status="funded"), _e)
check("project status outside the set rejected", has(_e, "status"))
_e = []
wikilint.check_fields("p", dict(PROJ, sponsor=None), _e)
check("project without sponsor rejected", has(_e, "missing sponsor"))
_e = []
wikilint.check_fields("e", dict(type="entity", entity_kind="program", sources=["s"], created="2026-01-01", updated="2026-01-01"), _e)
check("entity kinds include sponsor programs", _e == [])

# ---- file URLs, junk names, renditions -----------------------------------------------------------
_odd = os.path.join(RAW, "Proposals", "NSF CAREER", "Bai #1 – draft (v2).docx")
check("file URL round-trips a path with spaces, '#', and non-ASCII", docs.url_path(docs.file_url(_odd)) == os.path.normpath(_odd))
check("junk files are skipped (Office locks, macOS metadata)",
      all(docs.is_junk(n) for n in ("~$draft.docx", ".~lock.a.docx#", "._a.pdf", ".DS_Store", "x.tmp")) and
      not docs.is_junk("Proposal.docx"))
write("P/report.docx", b"x")
write("P/report.pdf", b"y")
write("P/~$report.docx", b"lock")
write("P/sub/other.tex", "x")
_docs = docs.documents(os.path.join(RAW, "P"), recursive=False)
check("renditions of one document group by folder and name", _docs == {(os.path.join(RAW, "P"), "report"): ["report.docx", "report.pdf"]})
check("--recursive descends into subfolders", len(docs.documents(os.path.join(RAW, "P"), recursive=True)) == 2)
check("paths outside the raw root are refused", refused(docs.resolve, tempfile.gettempdir()))
check("relative paths resolve against the raw root", docs.resolve("P/report.pdf")[1] == "P/report.pdf")

# ---- text extraction ---------------------------------------------------------------------------
write("T/main.tex", "\\documentclass{article}\\title{Aims}\\begin{document}\n\\input{sec/aims}\n% \\input{sec/ignored}\n"
                    "\\includegraphics[width=3in]{fig/one}\n\\bibliography{refs,more}\n\\end{document}\n")
write("T/sec/aims.tex", "Aim 1 text.\n\\include{sec/deeper}\n")
write("T/sec/deeper.tex", "Deeper text.\n")
write("T/fig/one.png", b"\x89PNG")
_flat, _miss, _gr, _bib = docs.tex_flatten(os.path.join(RAW, "T/main.tex"))
check("LaTeX: \\input and nested \\include are expanded in place, with markers",
      "Aim 1 text." in _flat and "Deeper text." in _flat and "%% >>> begin sec/aims.tex" in _flat)
check("LaTeX: commented-out inputs are not followed", _flat.count(">>> begin") == 2 and _miss == [])
check("LaTeX: graphics and bibliographies are listed",
      docs.graphics_paths(os.path.join(RAW, "T"), _gr) == [os.path.join(RAW, "T/fig/one.png")] and _bib == ["refs", "more"])
check("LaTeX: properties", docs.tex_props(os.path.join(RAW, "T/main.tex")).get("title") == "Aims")
write("T/loop.tex", "\\input{loop}\n")
check("LaTeX: an include cycle is cut, not followed forever", "skipped" in docs.tex_flatten(os.path.join(RAW, "T/loop.tex"))[0])


def ooxml(rel, parts):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return write(rel, buf.getvalue())


A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
P = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
RELS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'


def slide(text, embed=None):
    pic = f'<p:pic><p:blipFill><a:blip r:embed="{embed}"/></p:blipFill></p:pic>' if embed else ""
    return (f'<p:sld {A} {P} {R}><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p>'
            f'</p:txBody></p:sp>{pic}</p:spTree></p:cSld></p:sld>')


_pptx = ooxml("S/talk.pptx", {
    "ppt/presentation.xml": f'<p:presentation {P} {R}><p:sldIdLst><p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId1"/></p:sldIdLst></p:presentation>',
    "ppt/_rels/presentation.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Target="slides/slide1.xml"/><Relationship Id="rId2" Target="slides/slide2.xml"/></Relationships>',
    "ppt/slides/slide1.xml": slide("Second in order", "rIdImg"),
    "ppt/slides/slide2.xml": slide("First in order"),
    "ppt/slides/_rels/slide1.xml.rels": f'<Relationships {RELS}><Relationship Id="rIdImg" Target="../media/image1.png"/>'
                                        f'<Relationship Id="rIdN" Target="../notesSlides/notesSlide1.xml"/></Relationships>',
    "ppt/media/image1.png": b"\x89PNG fake",
    "ppt/notesSlides/notesSlide1.xml": f'<p:notes {A} {P}><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Say this</a:t></a:r></a:p>'
                                       f'<a:p><a:r><a:t>2</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>',
    "docProps/core.xml": '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                         'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Talk</dc:title><dc:creator>Bai, P.</dc:creator></cp:coreProperties>',
})
_media = tempfile.mkdtemp(prefix="wiki-media-test-")
_text, _imgs = docs.pptx_extract(_pptx, _media)
check("PowerPoint: slides follow the presentation order, not file names",
      _text.index("First in order") < _text.index("Second in order") and "## Slide 1" in _text)
check("PowerPoint: speaker notes kept, slide numbers in notes dropped", "- Notes: Say this" in _text and "Say this / 2" not in _text)
check("PowerPoint: embedded images copied out to view", len(_imgs) == 1 and os.path.isfile(_imgs[0]) and _imgs[0].startswith(_media))
check("PowerPoint: core properties", docs.office_props(_pptx) == {"title": "Talk", "creator": "Bai, P."})
shutil.rmtree(_media, ignore_errors=True)
_hid = ooxml("S/hidden.pptx", {
    "ppt/presentation.xml": f'<p:presentation {P} {R}><p:sldIdLst><p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId1"/></p:sldIdLst></p:presentation>',
    "ppt/_rels/presentation.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Target="slides/slide1.xml"/><Relationship Id="rId2" Target="slides/slide2.xml"/></Relationships>',
    "ppt/slides/slide1.xml": slide("Shown"),
    "ppt/slides/slide2.xml": slide("Hidden first").replace("<p:sld ", '<p:sld show="0" ', 1),
})
check("PowerPoint: hidden slides found by presentation order", docs.pptx_hidden(_hid) == [1] and docs.pptx_hidden(_pptx) == [])
_before = docs.sha8(_hid)
_unhide_dir = tempfile.mkdtemp(prefix="wiki-unhide-test-")
_copy = docs.unhidden_copy(_hid, _unhide_dir)
check("PowerPoint: the render copy clears hidden flags and keeps the text; the original is untouched",
      docs.pptx_hidden(_copy) == [] and "Hidden first" in docs.pptx_extract(_copy, _unhide_dir)[0]
      and docs.sha8(_hid) == _before and os.path.basename(_copy) == "hidden.pptx")
shutil.rmtree(_unhide_dir, ignore_errors=True)
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_docx = ooxml("D/plan.docx", {"word/document.xml": f'<w:document {W}><w:body><w:p><w:r><w:t>Data management</w:t></w:r></w:p>'
                                                    f'<w:p><w:r><w:t>plan </w:t></w:r><w:r><w:t>text</w:t></w:r></w:p></w:body></w:document>'})
check("Word: paragraphs without pandoc", docs.docx_text_stdlib(_docx) == "Data management\nplan text")
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
_xlsx = ooxml("B/budget.xlsx", {
    "xl/workbook.xml": f'<workbook {S} {R}><sheets><sheet name="Y1" sheetId="1" r:id="rId1"/></sheets></workbook>',
    "xl/_rels/workbook.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
    "xl/sharedStrings.xml": f'<sst {S}><si><t>Salary</t></si></sst>',
    "xl/worksheets/sheet1.xml": f'<worksheet {S}><sheetData><row><c t="s"><v>0</v></c><c><v>52000</v></c></row></sheetData></worksheet>'})
check("Excel: cell values per sheet", "## Sheet: Y1\nSalary\t52000" in docs.xlsx_extract(_xlsx))

# ---- converters: LibreOffice first when installed, then Office for its own formats --------------
_saved = (docs.office_app, docs.soffice)
docs.office_app = lambda kind: True
docs.soffice = lambda: "/x/soffice"
check("converters: LibreOffice, then Word, for a Word file", docs.converters(".docx") == ["libreoffice", "word"])
check("converters: LibreOffice, then PowerPoint, for slides", docs.converters(".pptx") == ["libreoffice", "powerpoint"])
check("converters: LibreOffice alone for Excel", docs.converters(".xlsx") == ["libreoffice"])
os.environ["PROJECT_WIKI_CONVERTER"] = "office"
check("converters: PROJECT_WIKI_CONVERTER=office puts Office first", docs.converters(".docx") == ["word", "libreoffice"])
del os.environ["PROJECT_WIKI_CONVERTER"]
docs.soffice = lambda: None
check("converters: Office alone when LibreOffice is absent", docs.converters(".pptx") == ["powerpoint"])
docs.soffice = lambda: "/x/soffice"
docs.office_app = lambda kind: False
docs.soffice = lambda: None
check("converters: none available -> advice to install, not a crash",
      docs.converters(".docx") == [] and refused(docs.to_pdf, _docx, "deadbeef"))
docs.office_app = lambda kind: False
docs.soffice = lambda: "/x/soffice"
_calls, _real_run, _real_tmp = [], docs.subprocess.run, docs.TMP
docs.TMP = tempfile.mkdtemp(prefix="wiki-lo-test-")
docs.subprocess.run = lambda cmd, **k: _calls.append(cmd) or argparse.Namespace(returncode=1, stdout="", stderr="x")
refused(docs.to_pdf, _docx, "aaaa0001")
refused(docs.to_pdf, _pptx, "aaaa0002")
docs.subprocess.run, docs.TMP = _real_run, _real_tmp
check("LibreOffice: each document converts with its own profile, so parallel conversions do not collide",
      len(_calls) == 2 and _calls[0][1] != _calls[1][1] and "aaaa0001" in _calls[0][1] and "aaaa0002" in _calls[1][1])
_calls.clear()
docs.TMP = tempfile.mkdtemp(prefix="wiki-lo-test-")
docs.subprocess.run = lambda cmd, **k: _calls.append(cmd) or argparse.Namespace(returncode=1, stdout="", stderr="x")
refused(docs.to_pdf, _hid, "aaaa0003")
refused(docs.to_pdf, _hid, "aaaa0003", True)
docs.subprocess.run, docs.TMP = _real_run, _real_tmp
check("LibreOffice: hidden slides render from an unhidden copy by default; --skip-hidden converts the original",
      len(_calls) == 2 and os.sep + "unhide" + os.sep in _calls[0][-1] and _calls[1][-1] == _hid)
docs.office_app, docs.soffice = _saved
check("Office commands are AppleScript on macOS and PowerShell elsewhere",
      (docs.office_command("word", "a", "b")[0] == "osascript") == (sys.platform == "darwin"))

# ---- protected text and relink ----------------------------------------------------------------
_rep = write("R/AnnualReport 2024.docx", b"r")
_url = docs.file_url(_rep)
KEYS = {os.path.normcase(os.path.realpath(_rep)): "2024-career-report"}
doc = (f"Body [Report 2024 ↗]({_url}).\n"
       f"> [!user] I think [Report 2024 ↗]({_url}) is key\n"
       f"> [!reuse] Facilities paragraph · p. 2\n> Our cluster [R ↗]({_url}) has 40 nodes.\n\n"
       f"```\n[X ↗]({_url})\n```\n"
       f"Inline `[Y ↗]({_url})` too.\n")
new, n = relink.relink_text(doc, KEYS)
check("relink rewrites the body link only", n == 1 and new.startswith("Body [[2024-career-report|Report 2024]]"))
check("relink leaves [!user], [!reuse], fenced and inline code identical", protected_text(new) == protected_text(doc))
check("relink skips a source page's own file", relink.relink_text(doc, KEYS, "2024-career-report")[1] == 0)
check("~~~ fence protected", relink.relink_text(f"~~~\n[X ↗]({_url})\n~~~\n", KEYS)[1] == 0)
check("unclosed fence protects to end of file", relink.relink_text(f"```\n[X ↗]({_url})\n", KEYS)[1] == 0)
with tempfile.TemporaryDirectory() as _sd:
    open(os.path.join(_sd, "rep.md"), "w", encoding="utf-8").write('---\ntype: source\nfiles: ["R/AnnualReport 2024.docx"]\n---\n')
    open(os.path.join(_sd, "decoy.md"), "w", encoding="utf-8").write('---\ntype: concept\nfiles: ["R/AnnualReport 2024.docx"]\n---\n')
    check("relink maps every file of a source page, and only source pages",
          relink.source_keys(_sd, RAW) == {os.path.normcase(os.path.realpath(_rep)): "rep"})

# ---- integration proxy ----------------------------------------------------------------------
body = "Text cites [[a]].\n\n## Related\n[[b]]\n\n## Sources\n[[c]]\n\n## Connections\n[[d]]\n"
check("Related/Sources/Connections lists don't count as evidence", links(synthesis_body(body)) == {"a"})
check("slide locators make a 'see' link a citation",
      wikimeta.dependents({"x": [dict(dir="concepts", body="", fields={})],
                           "y": [dict(dir="topics", body="see [[x]] slide 4", fields={})]}, "x") == ["y"])

# ---- fingerprints ----------------------------------------------------------------------------
_f1, _f2 = write("F/a.docx", b"one"), write("F/a.pdf", b"two")
_fp = docs.fingerprint_of([_f1, _f2])
check("fingerprint: one hash per file, in order", wikimeta.parse_fingerprint(_fp) == ("f1", {"0": docs.sha8(_f1), "1": docs.sha8(_f2)}))
check("compare: the same files in another order are unchanged", docs.compare(_fp, [docs.sha8(_f2), docs.sha8(_f1)]) == ("ok", None))
check("compare: a changed file is a content change", docs.compare(_fp, [docs.sha8(_f1), "00000000"]) == ("changed", "content"))
check("compare: a baseline with another file count is incomplete", docs.compare(_fp, [docs.sha8(_f1)])[0] == "incomplete")
check("compare: a malformed baseline is incomplete", docs.compare("f1", [docs.sha8(_f1)])[0] == "incomplete")

# ---- end-to-end update sequences (temp wiki + temp raw root) -----------------------------------


def source_page(name, doc_id, files, body, project=None):
    fl = ", ".join(f'"{f}"' for f in files)
    return f"""---
type: source
title: "Source {name}"
summary: "Summary of {name}."
authors: ["Bai, P."]
year: 2021
doc_kind: report
doc_id: {doc_id}
files: [{fl}]
read_file: "{files[0]}"
read_depth: full
read_mode: rendered
""" + (f"project: {project}\n" if project else "") + f"""ingested: 2026-10-18
updated: 2026-10-18
---
# {name}
{body}
"""


for rel, data in [("W/s1.pdf", "s1 v1"), ("W/s1.docx", "s1 docx"), ("W/s2.pdf", "s2"), ("W/s3.pdf", "s3"), ("W/s4.pdf", "s4")]:
    write(rel, data)
S1 = source_page("s1", "0000aaa1", ["W/s1.pdf", "W/s1.docx"], "## Claims and results\n- [reported] Own results (p. 2).\n", project="p1")
S2 = source_page("s2", "0000aaa2", ["W/s2.pdf"], "## Claims and results\n- [reported] Quotes numbers from [[s1]] (Table 1).\n")
S3 = source_page("s3", "0000aaa3", ["W/s3.pdf"], "## Claims and results\n- [proposed] Own plans.\n\n## Connections\n[[s1]]\n")
S4 = source_page("s4", "0000aaa4", ["W/s4.pdf"], "## Claims and results\n- [published] Re-uses the [[s2]] numbers (Fig. 3).\n")
C2 = "---\ntype: concept\nsummary: \"c2 summary\"\nsources: [s2]\ncreated: 2026-10-18\nupdated: 2026-10-18\n---\n# c2\nBuilds on [[s2]] §2.\n"
C3 = ("---\ntype: concept\nsummary: \"c3 summary\"\nsources: [s3]\ncreated: 2026-10-18\nupdated: 2026-10-18\n---\n# c3\n"
      "Extends the idea of [[c1]]; data from [[s3]].\n")
CON = "---\ntype: concept\nsummary: \"c1 summary\"\nsources: [s1]\ncreated: 2026-10-18\nupdated: 2026-10-18\n---\n# c1\nA claim ([[s1]] §1).\n"
TOP = ("---\ntype: topic\nsummary: \"t1 summary\"\nfolders: [\"W\"]\nsources: [s1, s2, s3, s4]\ncreated: 2026-10-18\nupdated: 2026-10-18\n"
       "---\n# t1\nSynthesis ([[s1]], [[s2]], [[s3]], [[s4]]); see [[c1]], [[c2]], [[c3]], [[a1]] and [[p1]].\n")
ANA = ("---\ntype: analysis\nsummary: \"a1 summary\"\nquestion: \"q?\"\nsources: [s1]\ncreated: 2026-10-18\n---\n# a1\n"
       "Answer resting on [[s1]] Fig. 2.\n")
PRJ = ("---\ntype: project\nsummary: \"p1 summary\"\nsponsor: NSF\nprogram: CBET\nstatus: awarded\nsources: [s1]\n"
       "created: 2026-10-18\nupdated: 2026-10-18\n---\n# p1\nYear-1 outcomes ([[s1]] p. 2).\n")
DEPS = ["a1", "c1", "c2", "p1", "s2", "s4", "t1"]  # s1's reviews: direct (a1, c1, p1, s2, t1) + via source s2 (s4, c2)


def lint_strict():
    buf = io.StringIO()
    old = sys.argv
    sys.argv = ["wikilint.py", "--strict"]
    try:
        with contextlib.redirect_stdout(buf):
            wikilint.main()
        code = 0
    except SystemExit as ex:
        code = ex.code
    finally:
        sys.argv = old
    return code, buf.getvalue()


def queued():
    return sorted(p for p, _ in wikimeta.pending_items())


def clear_queue():
    open(wikimeta.PENDING, "w", encoding="utf-8").write(docs.PENDING_HEADER + "*(no open items)*\n")


def set_field(path, key, value):
    t = open(path, encoding="utf-8").read()
    open(path, "w", encoding="utf-8").write(re.sub(rf'^{key}: .*$', lambda m: f"{key}: {value}", t, count=1, flags=re.M))


with tempfile.TemporaryDirectory() as tmp:
    for d in ("sources", "projects", "concepts", "topics", "analyses"):
        os.makedirs(os.path.join(tmp, d))
    for rel, text in [("sources/s1.md", S1), ("sources/s2.md", S2), ("sources/s3.md", S3), ("sources/s4.md", S4),
                      ("concepts/c1.md", CON), ("concepts/c2.md", C2), ("concepts/c3.md", C3),
                      ("topics/t1.md", TOP), ("analyses/a1.md", ANA), ("projects/p1.md", PRJ)]:
        open(os.path.join(tmp, rel), "w", encoding="utf-8").write(text)
    open(os.path.join(tmp, "log.md"), "w", encoding="utf-8").write("# Log\n")
    saved = (wikimeta.WIKI, wikimeta.PENDING, wikilint.WIKI, wikimeta.REVIEWED)
    wikimeta.WIKI = wikilint.WIKI = tmp
    wikimeta.PENDING = os.path.join(tmp, "pending.md")
    wikimeta.REVIEWED = os.path.join(tmp, "reviewed.md")
    import catalog  # noqa: E402
    open(os.path.join(tmp, "index.md"), "w", encoding="utf-8").write(catalog.fix_index(wikimeta.load_pages(), "# Index\n", "2026-10-18"))
    s1p = os.path.join(tmp, "sources/s1.md")
    try:
        clear_queue()
        run(docs.cmd_stamp, keys=["ALL"])
        pages = wikimeta.load_pages()
        check("deps: evidence citations count, Connections links don't, analyses and projects count",
              wikimeta.dependents(pages, "s1") == ["a1", "c1", "p1", "s2", "t1"])
        check("propagation: follows source chains (s2 -> s4, c2) but not concept links (c3) or Connections (s3)",
              sorted(wikimeta.propagate(pages, "s1")) == DEPS)
        check("states: a source cited by a project page is integrated",
              wikimeta.source_states({"s": [dict(dir="sources", body="", fields={"type": "source", "doc_id": "0000000f", "read_depth": "full"})],
                                      "p": [dict(dir="projects", body="Result ([[s]] p. 3).", fields={})]})["0000000f"][1] == "integrated")
        out = run(docs.cmd_stamp, keys=["0000aaa1"])
        check("stamp: resolves by doc_id", "stamped s1" in out)
        check("stamp: an argument naming no source page is an error, not a silent no-op", refused(docs.cmd_stamp, argparse.Namespace(keys=["nope"])))
        check("stamp: it still reports the unmatched one when another argument did match",
              refused(docs.cmd_stamp, argparse.Namespace(keys=["s1", "nope"])))
        check("seq: first stamp queues nothing", queued() == [])
        code, out = lint_strict()
        check("seq: clean wiki passes the strict gate", code == 0)
        if code:
            print(out)

        write("W/s1.pdf", "s1 v2")  # the document was edited
        out = run(docs.cmd_changed, queue=True)
        check("seq: an edited file is detected as a content change", "CHANGED" in out and "s1" in out)
        check("seq: queue holds the source and all evidence dependents", queued() == sorted(DEPS + ["s1"]))
        check("seq: strict gate fails while reviews are open", lint_strict()[0] == 1)
        run(docs.cmd_stamp, keys=["s1"])
        check("seq: re-stamping after queueing adds no duplicates", queued() == sorted(DEPS + ["s1"]))
        check("seq: changed is quiet after the stamp", "0 need attention" in run(docs.cmd_changed, queue=False))
        clear_queue()
        check("seq: gate passes once reviews are done", lint_strict()[0] == 0)

        write("W/s1.docx", "s1 docx v2")  # edited again; the agent re-stamps WITHOUT running `changed --queue` first
        out = run(docs.cmd_stamp, keys=["s1"])
        check("seq: interrupted path, stamp auto-queues dependents", queued() == DEPS and f"queued {len(DEPS)}" in out)
        clear_queue()

        # a moved file: reported as missing, found by locate, and a stamp after fixing files: queues nothing
        os.makedirs(os.path.join(RAW, "W/archive"), exist_ok=True)
        os.replace(os.path.join(RAW, "W/s1.pdf"), os.path.join(RAW, "W/archive/s1.pdf"))
        out = run(docs.cmd_changed, queue=True)
        check("move: a moved file is MISSING, and only the source page is queued", "MISSING" in out and queued() == ["s1"])
        check("move: stamping with a missing file is refused", refused(docs.cmd_stamp, argparse.Namespace(keys=["s1"])))
        out = run(docs.cmd_locate, page="s1", under=None, deep=False)
        check("move: locate finds the file by name and hash", "found at W/archive/s1.pdf" in out)
        t = open(s1p, encoding="utf-8").read().replace('"W/s1.pdf"', '"W/archive/s1.pdf"')
        open(s1p, "w", encoding="utf-8").write(t)
        clear_queue()
        out = run(docs.cmd_stamp, keys=["s1"])
        check("move: re-stamping a moved, unchanged file queues no dependents", "queued" not in out and queued() == [])
        os.replace(os.path.join(RAW, "W/archive/s1.pdf"), os.path.join(RAW, "W/archive/renamed.pdf"))
        check("move: a renamed file is found with --deep (hash of every file with that extension)",
              "not found by name" in run(docs.cmd_locate, page="s1", under="W", deep=False) and
              "found at W/archive/renamed.pdf" in run(docs.cmd_locate, page="s1", under="W", deep=True))
        os.replace(os.path.join(RAW, "W/archive/renamed.pdf"), os.path.join(RAW, "W/archive/s1.pdf"))

        # an incomplete baseline must never certify "unchanged"
        set_field(s1p, "doc_fingerprint", '"f1"')
        code, out = lint_strict()
        check("incomplete: strict lint fails on a bare 'f1' fingerprint", code == 1 and "incomplete or malformed" in out)
        out = run(docs.cmd_changed, queue=False)
        check("incomplete: changed reports INCOMPLETE, not 0", "INCOMPLETE" in out and "0 need attention" not in out)
        run(docs.cmd_stamp, keys=["s1"])
        check("incomplete: stamping over it queues the dependents", queued() == DEPS)
        clear_queue()

        # identity
        open(os.path.join(tmp, "sources/dup.md"), "w", encoding="utf-8").write(
            source_page("dup", "0000aaa2", ["W/s2.pdf"], "## Claims and results\n- [reported] x (p. 1).\n"))
        code, out = lint_strict()
        check("identity: a duplicate doc_id and a file on two pages are errors",
              "doc_id 0000aaa2 used by both" in out and "W/s2.pdf is listed by both" in out)
        os.remove(os.path.join(tmp, "sources/dup.md"))

        # reuse blocks and claim status
        s3p = os.path.join(tmp, "sources/s3.md")
        _s3 = open(s3p, encoding="utf-8").read()
        open(s3p, "w", encoding="utf-8").write(
            _s3.replace("- [proposed] Own plans.\n", "- [proposed] Own plans.\n- An untagged claim.\n") +
            "\n## Reusable material\n\n> [!reuse] Computing facilities\n> Our cluster has 40 nodes.\n")
        code, out = lint_strict()
        check("reuse: a block needs '<label> · <locator>'", "[!reuse] header needs" in out)
        check("claim status: an untagged claim is a warning", "claim without [proposed" in out)
        open(s3p, "w", encoding="utf-8").write(_s3)
        c1p = os.path.join(tmp, "concepts/c1.md")
        _c1 = open(c1p, encoding="utf-8").read()
        open(c1p, "w", encoding="utf-8").write(_c1 + "> [!reuse] Text · p. 2\n> Copied.\n")
        check("reuse: a block outside a source page is an error", "belongs in a source page" in lint_strict()[1])
        open(c1p, "w", encoding="utf-8").write(_c1)
        s2p = os.path.join(tmp, "sources/s2.md")
        _s2 = open(s2p, encoding="utf-8").read()
        set_field(s2p, "doc_kind", "report\nproject: missing-project")
        check("project: the field must name a project page", "is not a page in projects/" in lint_strict()[1])
        open(s2p, "w", encoding="utf-8").write(_s2)

        # stale ↗ links, using the files of source pages
        t1p = os.path.join(tmp, "topics/t1.md")
        _t1 = open(t1p, encoding="utf-8").read()
        open(t1p, "w", encoding="utf-8").write(_t1 + f"Not yet read: [S4 ↗]({docs.file_url(os.path.join(RAW, 'W/s4.pdf'))}).\n")
        check("lint: a ↗ link to a file that has a page is a stale link", "s4.pdf is now [[s4]]" in lint_strict()[1])
        open(t1p, "w", encoding="utf-8").write(_t1)

        # concurrent stampers share the queue: no item may be lost
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import wikimeta\n"
                "wikimeta.PENDING = sys.argv[2]\n"
                "for j in range(15): wikimeta.queue_reviews([(f'p{sys.argv[3]}-{j}', 'n')], '# q\\n\\n')\n")
        procs = [subprocess.Popen([sys.executable, "-I", "-B", "-c", code, tools_dir, wikimeta.PENDING, str(i)]) for i in range(8)]
        for pr in procs:
            pr.wait()
        check("concurrency: 8 processes x 15 queued items all survive", len(wikimeta.pending_items()) == 120)
        clear_queue()

        # multiple causes on one page are all kept, and can be resolved one at a time
        import review  # noqa: E402
        write("W/s1.docx", "s1 docx v3")
        run(docs.cmd_changed, queue=True)
        run(review.cmd_touched, pages=["s2"], reason="corrected a number")
        t1_causes = [c for p, _, c in wikimeta.pending_parse()[0] if p == "t1"]
        check("causes: a second reason for an already-queued page is kept", len(t1_causes) == 2 and len(set(t1_causes)) == 2)
        check("causes: a document change is named file:<page>@<hash>", any(c.startswith("file:s1@") for c in t1_causes))
        run(review.cmd_touched, pages=["s2"], reason="corrected a number")
        check("causes: the same cause is not duplicated", len([c for p, _, c in wikimeta.pending_parse()[0] if p == "t1"]) == 2)
        first = sorted(t1_causes)[0]
        run(review.cmd_done, pages=["t1"], cause=first, outcome="unchanged", basis="re-read t1 against s1 and s2")
        left = [c for p, _, c in wikimeta.pending_parse()[0] if p == "t1"]
        check("causes: done --cause resolves only that cause", left == [c for c in t1_causes if c != first])
        run(docs.cmd_stamp, keys=["s1"])
        clear_queue()

        # wiki-side change: stepwise propagation (concept c1 changed -> its dependent c3)
        subprocess.run(["git", "init", "-q", tmp], check=True)
        subprocess.run(["git", "-C", tmp, "add", "-A"], check=True)
        subprocess.run(["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], check=True)
        c1_text = open(c1p, encoding="utf-8").read()
        open(c1p, "w", encoding="utf-8").write(c1_text.replace("updated: 2026-10-18", "updated: 2026-10-19"))
        out = run(review.cmd_since, rev="HEAD", queue=True)
        check("since: a frontmatter-only edit is not a content change", "0 existing page(s) with changed content" in out and queued() == [])

        def revise_c1(line):  # rewrite c1's claim line: a changed line, not an addition
            t = open(c1p, encoding="utf-8").read().rstrip("\n").split("\n")
            t[-1] = line
            open(c1p, "w", encoding="utf-8").write("\n".join(t) + "\n")
        revise_c1("A corrected claim ([[s1]] §2).")
        run(review.cmd_since, rev="HEAD", queue=True)
        check("since: a body edit queues the page's dependents (stepwise); t1's 'see [[c1]]' pointer is not one", queued() == ["c3"])
        clear_queue()
        revise_c1("Another corrected claim ([[s1]] §3).")
        run(review.cmd_since, rev="HEAD", queue=True)
        first_round = queued()
        run(review.cmd_done, pages=first_round, cause=None, outcome="not-affected", basis="neither page uses the c1 claim that changed")
        out = run(review.cmd_since, rev="HEAD", queue=True)
        check("ledger: repeating since with the same revision queues nothing", queued() == [] and f"{len(first_round)} already resolved" in out)
        revise_c1("A claim ([[s1]] §1).")
        open(c1p, "a", encoding="utf-8").write("\nA new claim from a new document ([[s2]] p. 5).\n")
        out = run(review.cmd_since, rev="HEAD", queue=True)
        check("since: an edit that only inserts lines is additive and not propagated", queued() == [] and "1 additive edit(s)" in out)
        open(c1p, "w", encoding="utf-8").write(c1_text)

        # generated bookkeeping
        c3p = os.path.join(tmp, "concepts/c3.md")
        open(c3p, "w", encoding="utf-8").write(C3.replace("sources: [s3]", "sources: [s3, s2]"))
        code, out = lint_strict()
        check("catalog: a stale sources: list is reported", code == 1 and "catalog" in out)
        with contextlib.redirect_stdout(io.StringIO()):
            sys.argv, old_argv = ["catalog.py", "--apply"], sys.argv
            catalog.main()
            sys.argv = old_argv
        check("catalog: --apply re-derives sources: from the body", parse_frontmatter(open(c3p, encoding="utf-8").read())[0]["sources"] == ["s3"])
        _idx_text = open(os.path.join(tmp, "index.md"), encoding="utf-8").read()
        check("catalog: source lines show title, kind and year, then project or folder and read depth",
              "- [[s1|Source s1 (report, 2021)]] — Summary of s1. · p1 · full" in _idx_text and
              "- [[s2|Source s2 (report, 2021)]] — Summary of s2. · W · full" in _idx_text)
        check("catalog: project lines show status and source count", "- [[p1]] — p1 summary · awarded · 1 source" in _idx_text)
        _hdr = catalog.fix_index(wikimeta.load_pages(), "# Index\n**0 topics · 0 projects · 0 sources · 0 concepts · 0 entities · 0 analyses** · updated 2026-01-01\n", "2026-11-02")
        check("catalog: header counts projects", "**1 topic · 1 project · 4 sources · 3 concepts · 0 entities · 1 analysis** · updated 2026-11-02" in _hdr)
        _nav = catalog.nav(wikimeta.load_pages(), _idx_text)
        check("catalog: --nav prints Topics and Projects only", "## Topics" in _nav and "## Projects" in _nav and "## Sources" not in _nav)
        check("catalog: an index line's summary is read without its generated metadata",
              catalog.index_summaries("## Projects\n- [[p9|Nine]] — kept editorial text · awarded · 3 sources\n") == {"p9": "kept editorial text"})
        code, out = lint_strict()
        check("seq: the whole fixture passes the strict gate again", code == 0)
        if code:
            print(out)

        # version_of: the earlier version of a cited document is integrated
        vp = {"later": [dict(dir="sources", body="x", fields={"type": "source", "doc_id": "0000bbb1", "read_depth": "full"})],
              "early": [dict(dir="sources", body="x", fields={"type": "source", "doc_id": "0000bbb2", "read_depth": "full", "version_of": "later"})],
              "c9v": [dict(dir="concepts", body="A claim ([[later]] §1).", fields={})]}
        vs = wikimeta.source_states(vp)
        check("version_of: an earlier version (a draft) counts as integrated once the later one is cited",
              vs["0000bbb1"][1] == "integrated" and vs["0000bbb2"][1] == "integrated")

        # part notes: a long source page split into parts stays one identity
        import split  # noqa: E402
        _s3_new = _s3.replace("- [proposed] Own plans.\n", "- [proposed] Own plans.\n\n### Thrust 2\nA long thrust (p. 9).\n")
        _pn, _cn = split.plan_split(_s3_new, "Thrust 2", "s3--thrust-2", "Thrust 2 notes.", "Thrust 2", "s3", "2026-11-01")
        _pf = parse_frontmatter(_cn)[0]
        check("part note: type source-part, part_of the source", _pf.get("type") == "source-part" and _pf.get("part_of") == "s3")
        _e = []
        wikilint.check_fields("s3--thrust-2", _pf, _e)
        check("part note: lint accepts the part-note frontmatter", _e == [])

        # bounded lint output and cited-sentence review
        sys.argv, _old = ["wikilint.py", "--since", "HEAD"], sys.argv
        with contextlib.redirect_stdout(io.StringIO()) as _buf:
            try:
                wikilint.main()
            except SystemExit:
                pass
        sys.argv = _old
        check("lint --since: warnings are counted by category", "warnings by category:" in _buf.getvalue())
        with open(wikimeta.PENDING, "a", encoding="utf-8") as f:
            f.write("- [ ] [[c3]] test item (cause: wiki:c1@abcd1234)\n")
        out = run(review.cmd_list, context=True)
        check("review list --context prints the lines that cite the changed page", "[[c1]]" in out and "Extends the idea" in out)
        clear_queue()
        with open(wikimeta.PENDING, "a", encoding="utf-8") as f:
            f.write("- [ ] c1 without a wikilink\n- [x] [[t1]] done\n")
        code, out = lint_strict()
        check("queue: malformed open item and completed item left in place are errors",
              code == 1 and "open item not in the form" in out and "completed item left" in out)
    finally:
        wikimeta.WIKI, wikimeta.PENDING, wikilint.WIKI, wikimeta.REVIEWED = saved

# ---- rendering pages to images ----------------------------------------------------------------
check("page range: single page, span, open end, all", (docs.page_range("4", 9), docs.page_range("3-7", 9),
      docs.page_range("5-", 9), docs.page_range(None, 9)) == ((4, 4), (3, 7), (5, 9), (1, 9)))
for _bad in ("0", "8-3", "2-12", "a-b"):
    check(f"page range {_bad!r} is refused", refused(docs.page_range, _bad, 9))
if shutil.which("pdftoppm") and shutil.which("pdfinfo"):
    def _tiny_pdf(pages):
        objs = ["<< /Type /Catalog /Pages 2 0 R >>",
                "<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(f"{3 + i} 0 R" for i in range(pages)), pages)]
        objs += ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] >>"] * pages
        out, offs = b"%PDF-1.4\n", []
        for i, o in enumerate(objs, 1):
            offs.append(len(out))
            out += f"{i} 0 obj\n{o}\nendobj\n".encode()
        x = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        out += "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
        out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
        return out
    write("PDF/paper.pdf", _tiny_pdf(12))
    _saved_tmp = docs.TMP
    docs.TMP = os.path.realpath(tempfile.mkdtemp(prefix="wiki-render-test-"))
    try:
        _out = run(docs.cmd_render, file="PDF/paper.pdf", pages="9-11", dpi=20)
        _rows = [l.split("\t") for l in _out.splitlines()[1:]]
        check("render: one PNG per requested page, numbered by page index",
              [r[0] for r in _rows] == ["9", "10", "11"] and all(os.path.isfile(r[1]) for r in _rows))
        check("render: pages land in the temp dir, outside the wiki and the raw root",
              all(r[1].startswith(docs.TMP + os.sep) and not r[1].startswith(RAW + os.sep) for r in _rows))
        check("render: LaTeX is refused with advice (read the source)",
              refused(docs.cmd_render, argparse.Namespace(file="T/main.tex", pages=None, dpi=20)))
        run(docs.cmd_clean)
        check("clean: removes the temp dir", not os.path.exists(docs.TMP))
    finally:
        docs.TMP = _saved_tmp
else:
    print("skip render tests: poppler (pdftoppm, pdfinfo) not installed")
check("the tools wrote nothing into the raw root besides this test's own files",
      sorted(f for _, _, fs in os.walk(RAW) for f in fs if docs.is_junk(f)) == ["~$report.docx"])

# ---- search ranks pages for a query ----------------------------------------------------------
import search  # noqa: E402


def _page(d, text):
    fields, body, errors = parse_frontmatter(text)
    return dict(dir=d, path=f"{d}/x.md", fields=fields, body=body, errors=errors)


_mention = "Broader impacts are mentioned here among many other things. " + "Filler words about other topics. " * 60
_PAGES = {
    "broader-impacts": [_page("concepts", "---\ntype: concept\n---\n# Broader impacts\n\nShort definition.\n")],
    "2021-career-proposal": [_page("sources", "---\ntype: source\ntitle: \"CAREER proposal\"\nread_depth: full\ndoc_kind: proposal\n"
                                   "files: [\"Proposals/NSF-CAREER/NSF-CAREER.docx\"]\n---\n# Long\n\n" + _mention * 3 +
                                   "\nbroader impacts again, and broader-impacts.\n")],
    "2024-doe-report": [_page("sources", "---\ntype: source\ntitle: \"Annual report\"\nauthors: [\"Bai, P.\"]\n"
                              "read_depth: partial\ndoc_kind: report\nfiles: [\"Proposals/DOE-Catalysis/report.pdf\"]\n---\n# Report\n\n"
                              "Zeolite networks for catalysis. Expected improvement is not discussed.\n```\nzeolitecodeword\n```\n")],
    "nsf-cbet": [_page("entities", "---\ntype: entity\nentity_kind: program\nsponsor: NSF\n---\n# CBET\n\nThe improvement expected.\n")],
}


def _hits(*terms, phrases=(), **flt):
    a = argparse.Namespace(type=flt.get("type"), folder=flt.get("folder"), kind=flt.get("kind"), depth=flt.get("depth"))
    return [h[2] for h in search.search(_PAGES, terms, phrases, a, 10)]


check("search: the page named after the query outranks a long page that mentions it more often",
      _hits("broader", "impacts")[:1] == ["broader-impacts"])
check("search: plurals fold ('network' finds 'networks')", _hits("network") == ["2024-doe-report"])
check("search: author words are searchable", _hits("bai")[:1] == ["2024-doe-report"])
check("search: --phrase requires the words in order", _hits("improvement", phrases=["expected improvement"]) == ["2024-doe-report"])
check("search: words inside code blocks are not indexed", _hits("zeolitecodeword") == [])
check("search: --type keeps one page type", set(_hits("broader", type="concept")) == {"broader-impacts"})
check("search: --folder keeps sources by raw-root path prefix", _hits("broader", "zeolite", folder="Proposals/DOE") == ["2024-doe-report"])
check("search: --kind keeps sources of one doc_kind", _hits("broader", "zeolite", kind="proposal") == ["2021-career-proposal"])
check("search: --depth keeps sources read to that depth", _hits("broader", depth="full") == ["2021-career-proposal"])
check("search: sponsor words are searchable", "nsf-cbet" in _hits("nsf"))
check("search: no query words, no results", search.search(_PAGES, [], (), None, 10) == [])

# ---- split.py moves a section verbatim to a child page ----------------------------------------
import split  # noqa: E402
_parent = ("---\ntype: concept\nsummary: \"p\"\ntags: [a, b]\nsources: [s1]\ncreated: 2026-10-18\nupdated: 2026-10-18\n---\n"
           "# P\n\n## Details\n\n### 1. First part\nClaim one ([[s1]] §1).\n\n#### Sub\nMore.\n```\n### not a heading\n```\n"
           "\n### 2. Second part\nClaim two.\n\n## Related\n")
_pn, _cn = split.plan_split(_parent, "1. First part", "p-first", "One line.", "First part", "p", "2026-11-01")
check("split: the section moves verbatim, the parent keeps its heading and a pointer line",
      "Claim one ([[s1]] §1)." in _cn and "Claim one" not in _pn and "### 1. First part\n\nOne line. → [[p-first]]\n" in _pn)
try:
    split.plan_split(_parent, "Missing", "x", "y", "t", "p", "2026-11-01")
    check("split: a heading that is not found is refused", False)
except ValueError:
    check("split: a heading that is not found is refused", True)

# ---- tools are checked against the installed skill -------------------------------------------
_t = tempfile.mkdtemp(prefix="wiki-tools-test-")
try:
    _wiki, _tmpl = os.path.join(_t, "w"), os.path.join(_t, "skill", "assets", "wiki-template", "tools")
    os.makedirs(os.path.join(_wiki, "tools"))
    os.makedirs(_tmpl)
    for _n in wikilint.TOOLS:
        for _d in (os.path.join(_wiki, "tools"), _tmpl):
            open(os.path.join(_d, _n), "w", encoding="utf-8").write(f"# {_n}\n")
    _w = []
    wikilint.check_tools(_wiki, _w, _tmpl)
    check("tools: identical to the installed skill, no warning", _w == [])
    open(os.path.join(_wiki, "tools", "docs.py"), "a", encoding="utf-8").write("# local edit\n")
    _w = []
    wikilint.check_tools(_wiki, _w, _tmpl)
    check("tools: a tool edited in the wiki is flagged", len(_w) == 1 and "tools/docs.py" in _w[0][1])
    _w = []
    wikilint.check_tools(_wiki, _w, os.path.join(_t, "missing"))
    check("tools: a missing skill is flagged", len(_w) == 1 and "not installed" in _w[0][1])
finally:
    shutil.rmtree(_t, ignore_errors=True)
    shutil.rmtree(RAW, ignore_errors=True)

print(f"\n{len(FAILS)} failed")
sys.exit(1 if FAILS else 0)
