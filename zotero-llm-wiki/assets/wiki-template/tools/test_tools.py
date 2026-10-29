#!/usr/bin/env python3
"""Regression tests for the wiki tools. Stdlib only, no network: Zotero responses are faked.
Run from the wiki root: python3 -I tools/test_tools.py  (exits 1 on failure)."""
import copy
import os
import shutil
import tempfile
import sys

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import relink  # noqa: E402
import wikilint  # noqa: E402
import zot  # noqa: E402
from wikimeta import parse_frontmatter, protected_text, synthesis_body, links  # noqa: E402

FAILS = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def fm(s):
    return parse_frontmatter(f"---\n{s}\n---\nbody\n")


# ---- relink discovers valid plain and quoted source identities --------------------------------
with tempfile.TemporaryDirectory() as identity_root:
    for filename, value in [("plain", "PLAIN001"), ("double", '\"DOUBLE01\"'), ("single", "'SINGLE01'")]:
        with open(os.path.join(identity_root, filename + ".md"), "w") as source:
            source.write("---\ntype: source\nzotero_key: " + value + " # identity\ncitekey: changedAlias\n---\n")
    with open(os.path.join(identity_root, "decoy.md"), "w") as source:
        source.write("---\ntype: concept\n---\nA body example:\nzotero_key: DECOY001\n")
    with open(os.path.join(identity_root, "invalid.md"), "w") as source:
        source.write('---\ntype: source\nzotero_key: "BROKEN01\n---\n')
    found = relink.source_keys(identity_root)
    check("relink discovers plain and both quoted YAML keys",
          found == {"PLAIN001": "plain", "DOUBLE01": "double", "SINGLE01": "single"})
    check("relink resolves to stable filenames rather than changed citekey aliases", found.get("DOUBLE01") == "double")
    check("relink ignores body decoys and invalid frontmatter", "DECOY001" not in found and "BROKEN01" not in found)
    linked, count = relink.relink_text("[Paper ↗](zotero://select/library/items/DOUBLE01)", found)
    check("relink actually rewrites links to quoted-key source records", count == 1 and linked == "[[double|Paper]]")


# ---- parser ----------------------------------------------------------------------------------
check("quoted '#' is not a comment", fm('title: "Model #1"')[0].get("title") == "Model #1")
check("comment after quoted value", fm('title: "Model #1"  # note')[0].get("title") == "Model #1")
check("comment after plain value", fm("read_depth: full  # see §2.6")[0].get("read_depth") == "full")
check("'#' inside a flow-list element", fm('tags: [a, "b #c"]  # x')[0].get("tags") == ["a", "b #c"])
check("quoted author keeps its comma", fm('authors: ["Behler, J.", "Parrinello, M."]')[0].get("authors") == ["Behler, J.", "Parrinello, M."])
check("unquoted author splits (and lint must flag it)", fm("authors: [Behler, J.]")[0].get("authors") == ["Behler", "J."])
check("unterminated quote is an error", fm('title: "unterminated')[2] != [])
check("unbalanced bracket is an error", fm("tags: [a, b")[2] != [])
check("text after closing quote is an error", fm('title: "a" b')[2] != [])
check("flow map", fm('zotero_collections: {NMY5N3K8: "FF/ML"}')[0].get("zotero_collections") == {"NMY5N3K8": "FF/ML"})
check("quoted map value keeps its comma",
      fm('zotero_collections: {A1: "M/a, b", B2: "M/c"}')[0].get("zotero_collections") == {"A1": "M/a, b", "B2": "M/c"})
check("integer year", fm("year: 2021")[0].get("year") == 2021)
check("fallback citekey: authorTitleWordsYear without stop words",
      zot.fallback_citekey({"creators": [{"lastName": "Behler"}], "title": "Four Generations of High-Dimensional Neural Network Potentials",
                            "date": "2021-03-29"}) == "behlerFourGenerationsHighDimensional2021")
check("fallback citekey: no creator or date", zot.fallback_citekey({"title": "On the Theory"}) == "anonTheory")
check("fallback citekey: markup removed, accents folded, acronyms kept, E(3) -> E3",
      zot.fallback_citekey({"creators": [{"lastName": "Csányi"}], "title": "<i>Ab initio</i> MACE: E(3)-Equivariant Models", "date": "2022"})
      == "csanyiInitioMACEE3Equivariant2022")
check("fallback citekey: hyphenated last names keep the hyphen",
      zot.fallback_citekey({"creators": [{"lastName": "Barroso-Luque"}], "title": "Open Materials 2024", "date": "2024"})
      == "barroso-luqueOpenMaterials20242024")
check("fallback citekey: version numbers stay in one word",
      zot.fallback_citekey({"creators": [{"lastName": "Yao"}], "title": "The TensorMol-0.1 Model Chemistry", "date": "2018"}) == "yaoTensorMol01ModelChemistry2018")
_cols = {"A1": ("Materials/Cement", 0, None), "A2": ("Materials/Cement/carbonation", 3, "A1"),
         "B1": ("Machine Learning/Reinforcement Learning", 2, None)}
check("collections: word-start match, case-insensitive ('cement' is not 'Reinforcement')",
      zot.match_collections(_cols, "cement") == (["A1", "A2"], False))
check("collections: every query word must match", zot.match_collections(_cols, "cement carbon") == (["A2"], False))
check("collections: misspelling falls back to close matches, flagged as fuzzy",
      zot.match_collections(_cols, "cemnet")[1] is True and "A1" in zot.match_collections(_cols, "cemnet")[0])
check("duplicate key is an error", any("duplicate" in e for e in fm("a: 1\na: 2")[2]))

# ---- field validation ------------------------------------------------------------------------
BASE = dict(type="source", title="T", authors=["Behler, J."], year=2021, venue="V", item_type="review",
            library="user:1", zotero_key="RKJEQMJ4", citekey="x", zotero_uri="zotero://select/library/items/RKJEQMJ4",
            collections=["C"], read_depth="full", read_mode="rendered", attachment_key="PLXDWZZT", supplement="none",
            ingested="2026-10-17", updated="2026-10-17", zotero_checked="2026-10-18",
            zotero_fingerprint="v3 biblio:0000000a abstract:none pdf:0000000b notes:none ann:none")


def errors_for(**changes):
    f = copy.deepcopy(BASE)
    f.update(changes)
    errs = []
    wikilint.check_fields("x", {k: v for k, v in f.items() if v is not None}, errs)
    return errs


check("baseline source page is valid", errors_for() == [])
check("patent full read is valid", errors_for(item_type="patent") == [])
check("presentation full read is valid", errors_for(item_type="presentation") == [])
check("presentation metadata-only record is valid", errors_for(item_type="presentation", read_depth="metadata-only", read_mode="none", attachment_key=None, supplement=None) == [])
check("patent metadata-only record is valid", errors_for(item_type="patent", read_depth="metadata-only", read_mode="none", attachment_key=None, supplement=None) == [])
check("report full read is valid", errors_for(item_type="report") == [])
check("report metadata-only record is valid", errors_for(item_type="report", read_depth="metadata-only", read_mode="none", attachment_key=None, supplement=None) == [])
check("unknown source type rejected", any("item_type" in m for _, m in errors_for(item_type="invented-type")))
check("impossible date rejected", any("valid YYYY-MM-DD" in m for _, m in errors_for(updated="2026-99-99")))
check("list-valued title rejected", any("title must be a single string" in m for _, m in errors_for(title=["a", "b"])))
check("read_depth full + read_mode none rejected", any("cannot have read_mode" in m for _, m in errors_for(read_mode="none")))
check("full read without supplement rejected", any("must record supplement" in m for _, m in errors_for(supplement=None)))
check("metadata-only read needs no supplement", not any("supplement" in m for _, m in errors_for(supplement=None, read_depth="metadata-only", read_mode="none", attachment_key=None)))
check("supplement reason: an explicit reason line counts, a bare 'not read' does not",
      bool(wikilint.SUPP_REASON.search("> Supplement not read: the main text states every parameter used here."))
      and not wikilint.SUPP_REASON.search("> The SI was not read."))
check("metadata-only + rendered rejected", any("cannot have read_mode" in m for _, m in errors_for(read_depth="metadata-only")))
check("rendered without attachment_key rejected", any("no attachment_key" in m for _, m in errors_for(attachment_key=None)))
check("split author rejected", any("author entry" in m for _, m in errors_for(authors=["Behler", "J."])))
check("declared corporate author is valid", errors_for(authors=["International Energy Agency"], corporate_authors=["International Energy Agency"]) == [])
check("mixed personal and declared corporate authors are valid", errors_for(authors=["Behler, J.", "International Energy Agency"], corporate_authors=["International Energy Agency"]) == [])
check("empty optional corporate author list is valid", errors_for(corporate_authors=[]) == [])
check("undeclared corporate author rejected", any("author entry" in m for _, m in errors_for(authors=["International Energy Agency"])))
check("another undeclared corporate author still rejected", any("author entry" in m for _, m in errors_for(authors=["International Energy Agency", "U.S. Department of Energy"], corporate_authors=["International Energy Agency"])))
check("corporate author declaration requires a list", any("corporate_authors must be a [list]" in m for _, m in errors_for(corporate_authors="International Energy Agency")))
for invalid in ["", "   ", 1, None, ["organization"]]:
    check(f"invalid corporate author entry rejected ({invalid!r})", any("corporate_authors entries must be nonempty strings" in m for _, m in errors_for(corporate_authors=[invalid])))
check("duplicate corporate author declaration rejected", any("duplicate corporate_authors" in m for _, m in errors_for(authors=["International Energy Agency"], corporate_authors=["International Energy Agency", "International Energy Agency"])))
check("corporate author must occur exactly in authors", any("is not in authors" in m for _, m in errors_for(corporate_authors=["International Energy Agency"])))
check("corporate declaration does not rescue split personal authors", any("author entry" in m for _, m in errors_for(authors=["Behler", "J.", "International Energy Agency"], corporate_authors=["International Energy Agency"])))
check("uri/key mismatch rejected", any("zotero_uri" in m for _, m in errors_for(zotero_uri="zotero://select/library/items/AAAAAAAA")))
check("library is required", any("missing library" in m for _, m in errors_for(library=None)))
check("library must be user:<id> or group:<id>", any("is not user:<id>" in m for _, m in errors_for(library="mine")))
check("a group library needs a group URI", any("zotero://select/groups/7/items/RKJEQMJ4" in m for _, m in errors_for(library="group:7")))
check("citekey not filename rejected", any("citekey" in m for _, m in errors_for(citekey="other")))
check("old fingerprint format rejected", any("old format" in m for _, m in errors_for(zotero_fingerprint="v2 meta:0000000a pdf:0000000b notes:none ann:none")))
for bad, why in [("v3", "bare version"), ("v3 biblio:0000000a abstract:none pdf:0000000b notes:none", "missing part"),
                 ("v3 biblio:0000000a abstract:none pdf:0000000b notes:none ann:none ann:none", "duplicated part"),
                 ("v3 biblio:zz abstract:none pdf:0000000b notes:none ann:none", "malformed hash"),
                 ("v3 biblio:0000000a abstract:none pdf:0000000b notes:none ann:none extra:none", "unknown part")]:
    check(f"incomplete fingerprint rejected by lint ({why})",
          any("incomplete or malformed" in m for _, m in errors_for(zotero_fingerprint=bad)))
check("undated full-read presentation is valid", errors_for(item_type="presentation", year="undated") == [])
check("undated metadata-only record is valid", errors_for(year="undated", read_depth="metadata-only", read_mode="none", attachment_key=None, supplement=None) == [])
check("arbitrary year string rejected", any("year must be" in m for _, m in errors_for(year="unknown")))
check("non-integer year rejected", any("year must be" in m for _, m in errors_for(year="2021")))

# ---- protected text --------------------------------------------------------------------------
KEYS = {"LA52H69Y": "parkerFalseMetallizationShortRanged2026"}
doc = ("Body [Parker 2026 ↗](zotero://select/library/items/LA52H69Y).\n"
       "> [!user] I think [Parker 2026 ↗](zotero://select/library/items/LA52H69Y) is key\n"
       "> and so does [P ↗](zotero://select/library/items/LA52H69Y)\n\n"
       "```\n[X ↗](zotero://select/library/items/LA52H69Y)\n```\n"
       "Inline `[Y ↗](zotero://select/library/items/LA52H69Y)` too.\n")
new, n = relink.relink_text(doc, KEYS)
check("relink rewrites the body link only", n == 1 and new.startswith("Body [[parkerFalseMetallizationShortRanged2026|Parker 2026]]"))
check("relink leaves [!user], fenced and inline code identical", protected_text(new) == protected_text(doc))
check("relink skips a source page's own item", relink.relink_text(doc, KEYS, "parkerFalseMetallizationShortRanged2026")[1] == 0)
check("relink: a label never spans an earlier '['",
      relink.relink_text("on $[x_l, x_{l+1})$ and [Zhang 2021 ↗](zotero://select/library/items/LA52H69Y)", KEYS)[0]
      == "on $[x_l, x_{l+1})$ and [[parkerFalseMetallizationShortRanged2026|Zhang 2021]]")

# ---- integration proxy ----------------------------------------------------------------------
body = "Text cites [[a]].\n\n## Related\n[[b]]\n\n## Sources\n[[c]]\n\n## Connections\n[[d]]\n"
check("Related/Sources/Connections lists don't count as evidence", links(synthesis_body(body)) == {"a"})

# ---- fingerprints (fake Zotero) --------------------------------------------------------------
ITEM = {"data": {"title": "T", "creators": [], "date": "2021", "DOI": "d", "itemType": "journalArticle",
                 "abstractNote": "", "publicationTitle": "Chem. Rev."}}
CHILDREN = [{"key": "ATT1", "data": {"itemType": "attachment", "contentType": "application/pdf",
                                     "linkMode": "linked_file", "path": "attachments:a.pdf", "mtime": 1}}]
ANNS = [{"key": "AN1", "data": {"itemType": "annotation", "annotationType": "highlight", "annotationText": "x",
                                "annotationPageLabel": "3", "annotationPosition": '{"pageIndex":2}'}}]


ORIG_LIBVER = zot.library_version


def fake(item, children, anns):
    zot.library_version = lambda: 1
    zot.get = lambda path, **kw: item
    zot.get_all = lambda path, **kw: children if path.endswith("RKJEQMJ4/children") else anns


fake(ITEM, CHILDREN, ANNS)
base = zot.fingerprint("RKJEQMJ4")
for label, mutate in [
    ("venue change alters meta", lambda i, c, a: i["data"].update(publicationTitle="J. Chem. Phys.")),
    ("path change without MD5 alters pdf", lambda i, c, a: c[0]["data"].update(path="attachments:b.pdf")),
    ("attachment key change alters pdf", lambda i, c, a: c[0].update(key="ATT2")),
    ("moved highlight alters ann", lambda i, c, a: a[0]["data"].update(annotationPosition='{"pageIndex":5}')),
]:
    i, c, a = copy.deepcopy(ITEM), copy.deepcopy(CHILDREN), copy.deepcopy(ANNS)
    mutate(i, c, a)
    fake(i, c, a)
    after = zot.fingerprint("RKJEQMJ4")
    part = "biblio" if "meta" in label else "pdf" if "pdf" in label else "ann"
    check(label, after[part] != base[part])
check("v3 fingerprint round-trips", zot.fp_parse(zot.fp_string(base)) == base)
fake(ITEM, CHILDREN, ANNS)
v2_now = zot.fp_string(zot.fingerprint("RKJEQMJ4", "v2"), "v2")
check("v2 baseline compared with the v2 algorithm: unchanged -> ok", zot.compare(v2_now, "RKJEQMJ4")[0] == "ok")
i2 = copy.deepcopy(ITEM)
i2["data"]["abstractNote"] = "a changed abstract"
fake(i2, CHILDREN, ANNS)
st, diff, kind = zot.compare(v2_now, "RKJEQMJ4")
check("v2 baseline: an abstract change before migration is caught", st == "changed" and kind == "scientific re-read")
fake(ITEM, CHILDREN, ANNS)
check("incomplete baseline -> 'incomplete', treated as a scientific change",
      zot.compare("v3", "RKJEQMJ4") == ("incomplete", [], "scientific re-read"))

# ---- third review: quoting, invalid input, fences ------------------------------------------
check("'' decodes to one apostrophe", fm("title: 'O''Brien'")[0].get("title") == "O'Brien")
check("escaped quote + comma stays one list element", fm('tags: ["a \\" , b", c]')[0].get("tags") == ['a " , b', "c"])
check("unsupported escape rejected", fm('title: "bad \\q"')[2] != [])
check("stray quote in single-quoted string rejected", fm("title: 'a'b'")[2] != [])
e = []
wikilint.check_fields("x", {"type": ["source"]}, e)
check("type: [source] reported, not a crash", any("type" in m for _, m in e))
e = []
wikilint.check_fields("x", dict(BASE, read_depth=["full"]), e)
check("list-valued read_depth reported, not a crash", any("read_depth" in m for _, m in e))
td = "~~~\n[X ↗](zotero://select/library/items/LA52H69Y)\n~~~\n"
check("~~~ fence protected", relink.relink_text(td, KEYS)[1] == 0)
check("longer fence closes only on an equal-or-longer run",
      relink.relink_text("````\n```\n[X ↗](zotero://select/library/items/LA52H69Y)\n````\n", KEYS)[1] == 0)
check("unclosed fence protects to end of file", relink.relink_text("```\n[X ↗](zotero://select/library/items/LA52H69Y)\n", KEYS)[1] == 0)
check("double-backtick inline code protected", relink.relink_text("x ``[X ↗](zotero://select/library/items/LA52H69Y)`` y", KEYS)[1] == 0)

# ---- end-to-end update sequences (temp wiki + fake Zotero) -----------------------------------
import argparse  # noqa: E402
import contextlib  # noqa: E402
import io  # noqa: E402
import tempfile  # noqa: E402
import wikimeta  # noqa: E402

STATE = {}


def fake_zotero():
    """Fake Zotero: item SRCAAAA1 follows STATE; every other key returns a fixed item without PDFs."""
    item = {"data": {"title": "T", "creators": [], "date": "2021", "DOI": "d", "itemType": "journalArticle",
                     "abstractNote": STATE["abstract"], "publicationTitle": STATE["venue"]}}
    other = {"data": {"title": "Other", "creators": [], "date": "2020", "itemType": "journalArticle"}}
    kids = [{"key": "ATTAAAA1", "data": {"itemType": "attachment", "contentType": "application/pdf",
                                         "linkMode": "imported_file", "md5": STATE["md5"]}}]
    anns = [{"key": "ANNAAAA1", "data": {"itemType": "annotation", "annotationType": "highlight",
                                         "annotationText": "x", "annotationPageLabel": "3",
                                         "annotationPosition": STATE["pos"]}}]
    zot.library_version = lambda: STATE.get("libver", 1)
    zot.get = lambda path, **kw: item if "SRCAAAA1" in path else other
    zot.get_all = lambda path, **kw: (kids if path.endswith("SRCAAAA1/children") else
                                      anns if path.endswith("ATTAAAA1/children") else [])


def source_page(cite, key, body):
    return f"""---
type: source
title: "Source {cite}"
authors: ["Doe, J."]
year: 2021
venue: "J. Test"
item_type: article
library: user:1
zotero_key: {key}
citekey: {cite}
zotero_uri: zotero://select/library/items/{key}
attachment_key: ATTAAAA1
collections: ["C"]
read_depth: full
supplement: none
read_mode: rendered
ingested: 2026-10-18
updated: 2026-10-18
---
# {cite}
{body}
"""


S1 = source_page("s1", "SRCAAAA1", "## Results and claims\nOwn results.\n")
S2 = source_page("s2", "SRCAAAA2", "## Results and claims\nQuotes numbers from [[s1]] (Table 1).\n")   # evidence
S3 = source_page("s3", "SRCAAAA3", "## Results and claims\nOwn results.\n\n## Connections\n[[s1]]\n")  # related work only
S4 = source_page("s4", "SRCAAAA4", "## Results and claims\nRe-uses the [[s2]] numbers (Fig. 3).\n")    # chain s1 -> s2 -> s4
C2 = "---\ntype: concept\nsources: [s2]\ncreated: 2026-10-18\nupdated: 2026-10-18\n---\n# c2\nBuilds on [[s2]] §2.\n"
C3 = ("---\ntype: concept\nsources: [s3]\ncreated: 2026-10-18\nupdated: 2026-10-18\n---\n# c3\n"
      "Extends the idea of [[c1]]; data from [[s3]].\n")
CON = "---\ntype: concept\nsources: [s1]\ncreated: 2026-10-18\nupdated: 2026-10-18\n---\n# c1\nA claim ([[s1]] §1).\n"
TOP = ("---\ntype: topic\nzotero_collections: {CCCCCCC1: \"C\"}\nsources: [s1, s2, s3, s4]\ncreated: 2026-10-18\nupdated: 2026-10-18\n"
       "---\n# t1\nSynthesis ([[s1]], [[s2]], [[s3]], [[s4]]); see [[c1]], [[c2]], [[c3]] and [[a1]].\n")
ANA = ("---\ntype: analysis\nquestion: \"q?\"\nsources: [s1]\ncreated: 2026-10-18\n---\n# a1\n"
       "Answer resting on [[s1]] Fig. 2.\n")
DEPS = ["a1", "c1", "c2", "s2", "s4", "t1"]  # s1's reviews: direct (a1, c1, s2, t1) + via source s2 (s4, c2); not s3, not c3


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


def run(fn, **kw):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        fn(argparse.Namespace(**kw))
    return buf.getvalue()


def queued():
    return sorted(p for p, _ in wikimeta.pending_items())


def clear_queue():
    open(wikimeta.PENDING, "w").write(zot.PENDING_HEADER + "*(no open items)*\n")


def set_fingerprint(path, value):
    t = open(path).read()
    open(path, "w").write(re.sub(r'^zotero_fingerprint: .*$', f'zotero_fingerprint: "{value}"', t, count=1, flags=re.M))


import re  # noqa: E402
import subprocess  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    for d in ("sources", "concepts", "topics", "analyses"):
        os.makedirs(os.path.join(tmp, d))
    for rel, text in [("sources/s1.md", S1), ("sources/s2.md", S2), ("sources/s3.md", S3), ("sources/s4.md", S4),
                      ("concepts/c1.md", CON), ("concepts/c2.md", C2), ("concepts/c3.md", C3),
                      ("topics/t1.md", TOP), ("analyses/a1.md", ANA)]:
        open(os.path.join(tmp, rel), "w").write(text)
    open(os.path.join(tmp, "index.md"), "w").write("[[s1]] [[s2]] [[s3]] [[s4]] [[c1]] [[c2]] [[c3]] [[t1]] [[a1]]\n")
    open(os.path.join(tmp, "log.md"), "w").write("# Log\n")
    saved = (wikimeta.WIKI, wikimeta.PENDING, zot.PENDING, wikilint.WIKI, wikimeta.REVIEWED)
    wikimeta.WIKI = wikilint.WIKI = tmp
    wikimeta.PENDING = zot.PENDING = os.path.join(tmp, "pending.md")
    wikimeta.REVIEWED = os.path.join(tmp, "reviewed.md")
    try:
        STATE.update(abstract="abs", venue="J. Test", md5="m1", pos="p1")
        fake_zotero()
        clear_queue()
        run(zot.cmd_stamp, keys=["ALL"])
        pages = wikimeta.load_pages()
        check("deps: evidence citations count, Connections links don't, analyses count",
              wikimeta.dependents(pages, "s1") == ["a1", "c1", "s2", "t1"])
        check("propagation: follows source chains (s2 -> s4, c2) but not concept links (c3) or Connections (s3)",
              sorted(wikimeta.propagate(pages, "s1")) == DEPS)
        check("propagation: records the source it went through", wikimeta.propagate(pages, "s1")["s4"] == "s2")

        # ---- stamp resolves a page by filename, zotero_key or citekey, and never no-ops silently ----
        # (the page keeps its filename when a re-ingest changes the citekey, AGENTS.md §4)
        out = run(zot.cmd_stamp, keys=["SRCAAAA1"])
        check("stamp: resolves by zotero_key", "stamped s1" in out)
        s3p = os.path.join(tmp, "sources/s3.md")
        s3_before = open(s3p).read()
        open(s3p, "w").write(s3_before.replace("citekey: s3", "citekey: renamedAfterReingest2025"))
        out = run(zot.cmd_stamp, keys=["renamedAfterReingest2025"])
        check("stamp: resolves by a citekey that no longer matches the filename", "stamped s3" in out)
        open(s3p, "w").write(s3_before)
        refused = False
        try:
            run(zot.cmd_stamp, keys=["no-such-page"])
        except SystemExit:
            refused = True
        check("stamp: an argument naming no source page is an error, not a silent no-op", refused)
        refused = False
        try:
            run(zot.cmd_stamp, keys=["s1", "no-such-page"])
        except SystemExit:
            refused = True
        check("stamp: it still reports the unmatched one when another argument did match", refused)
        check("seq: first stamp queues nothing", queued() == [])
        check("seq: clean wiki passes the strict gate", lint_strict()[0] == 0)

        STATE["md5"] = "m2"  # PDF replaced in Zotero
        fake_zotero()
        out = run(zot.cmd_changed, queue=True)
        check("seq: PDF change detected as scientific re-read", "scientific re-read" in out)
        check("seq: queue holds the source and all evidence dependents", queued() == sorted(DEPS + ["s1"]))
        check("seq: strict gate fails while reviews are open", lint_strict()[0] == 1)
        run(zot.cmd_stamp, keys=["s1"])
        check("seq: re-stamping after queueing adds no duplicates", queued() == sorted(DEPS + ["s1"]))
        check("seq: changed is quiet after the stamp", "0 need attention" in run(zot.cmd_changed, queue=False))
        check("seq: but dependents stay queued (stamp does not clear them)", set(DEPS) <= set(queued()))
        clear_queue()
        check("seq: gate passes once reviews are done", lint_strict()[0] == 0)
        with open(wikimeta.REVIEWED, "a") as _f:
            _f.write("- 2026-10-26 not-affected (cause: wiki:s1@abcd1234) [[merged-away]] — page later merged into another\n")
        with open(os.path.join(tmp, "log.md"), "a") as _f:
            _f.write("\n## [2026-10-26] fix | Merged [[merged-away]] into another page\n- history\n")
        check("lint: links in reviewed.md and log.md to a removed page are history, not errors", lint_strict()[0] == 0)
        _idx = os.path.join(tmp, "index.md"); _old_idx = open(_idx).read()
        open(_idx, "a").write("- [[merged-away|Gone]] — stale line\n")
        _code, _out = lint_strict()
        check("lint: the same link in index.md is still a broken link", _code == 1 and "index -> [[merged-away]]" in _out)
        open(_idx, "w").write(_old_idx)

        STATE["pos"] = "p2"  # highlight moved; agent re-stamps WITHOUT running `changed --queue` first
        fake_zotero()
        out = run(zot.cmd_stamp, keys=["s1"])
        check("seq: interrupted path, stamp auto-queues dependents", queued() == DEPS and f"queued {len(DEPS)}" in out)
        check("seq: interrupted path, strict gate still fails", lint_strict()[0] == 1)
        clear_queue()

        STATE["abstract"] = "abs v2"  # abstract changed: content, not bibliography
        fake_zotero()
        out = run(zot.cmd_changed, queue=True)
        check("seq: abstract change is a scientific re-read", "abstract -> scientific re-read" in out)
        check("seq: abstract change queues dependents", queued() == sorted(DEPS + ["s1"]))
        run(zot.cmd_stamp, keys=["s1"])
        clear_queue()

        STATE["venue"] = "J. Test Lett."  # bibliographic only
        fake_zotero()
        out = run(zot.cmd_changed, queue=True)
        check("seq: venue change is a metadata refresh", "biblio -> metadata refresh" in out)
        check("seq: metadata refresh queues only the source", queued() == ["s1"])
        out = run(zot.cmd_stamp, keys=["s1"])
        check("seq: stamping a metadata refresh queues no dependents", "queued" not in out)
        clear_queue()

        # an incomplete baseline must never certify "unchanged"
        s1p = os.path.join(tmp, "sources/s1.md")
        set_fingerprint(s1p, "v3")
        code, out = lint_strict()
        check("incomplete: strict lint fails on a bare 'v3' fingerprint", code == 1 and "incomplete or malformed" in out)
        out = run(zot.cmd_changed, queue=False)
        check("incomplete: changed reports INCOMPLETE, not 0", "INCOMPLETE" in out and "0 need attention" not in out)
        out = run(zot.cmd_stamp, keys=["s1"])
        check("incomplete: stamping over it queues the dependents", queued() == DEPS)
        clear_queue()

        # format migration compares with the *old* algorithm before replacing the baseline
        v2_before = zot.fp_string(zot.fingerprint("SRCAAAA1", "v2"), "v2")
        set_fingerprint(s1p, v2_before)
        out = run(zot.cmd_stamp, keys=["s1"])
        check("migration: unchanged v2 baseline -> v3 without queueing", queued() == [] and "queued" not in out)
        set_fingerprint(s1p, v2_before)
        STATE["abstract"] = "abs v3"  # the item changed while the page still had a v2 stamp
        fake_zotero()
        out = run(zot.cmd_stamp, keys=["s1"])
        check("migration: change hidden behind a v2 baseline is caught and queued", queued() == DEPS)
        clear_queue()

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

        # ---- fifth review: snapshot race, causes, wiki-side propagation ----
        import review  # noqa: E402
        orig_collect = zot._collect

        # (a) Zotero changes right after the snapshot: the baseline is the snapshot, so the change is not lost
        def collect_then_change(key):
            raw = orig_collect(key)
            STATE["md5"] = "m-after"
            fake_zotero()
            return raw
        zot._collect = collect_then_change
        run(zot.cmd_stamp, keys=["s1"])
        zot._collect = orig_collect
        out = run(zot.cmd_changed, queue=False)
        check("race: a change landing right after the snapshot is still detected", "CHANGED" in out and "s1" in out)
        run(zot.cmd_stamp, keys=["s1"])
        clear_queue()

        # (b) Zotero changes *during* collection: the library version moves, so the read is retried
        calls = {"n": 0}

        def collect_during_change(key):
            calls["n"] += 1
            raw = orig_collect(key)
            if calls["n"] == 1:
                STATE["md5"] = "m-during"
                STATE["libver"] = STATE.get("libver", 1) + 1
                fake_zotero()
            return raw
        zot._collect = collect_during_change
        out = run(zot.cmd_stamp, keys=["s1"])
        zot._collect = orig_collect
        stored = wikimeta.parse_frontmatter(open(s1p).read())[0]["zotero_fingerprint"]
        check("race: a change during collection triggers a retry", calls["n"] == 2)
        check("race: the stored fingerprint is the post-change snapshot", stored == zot.fp_string(zot.fingerprint("SRCAAAA1")))
        check("race: and the change queued the dependents", queued() == DEPS)
        clear_queue()

        # (c) Zotero never settles: refuse rather than stamp an inconsistent snapshot
        def never_settles(key):
            STATE["libver"] = STATE.get("libver", 1) + 1
            fake_zotero()
            return orig_collect(key)
        zot._collect = never_settles
        try:
            run(zot.cmd_stamp, keys=["s1"])
            refused = False
        except SystemExit:
            refused = True
        zot._collect = orig_collect
        check("race: an item that never settles is not stamped", refused)

        # multiple causes on one page are all kept, and can be resolved one at a time
        STATE["md5"] = "m-cause-1"
        fake_zotero()
        run(zot.cmd_changed, queue=True)
        run(review.cmd_touched, pages=["s2"], reason="corrected a number")
        t1_causes = [c for p, _, c in wikimeta.pending_parse()[0] if p == "t1"]
        check("causes: a second reason for an already-queued page is kept", len(t1_causes) == 2 and len(set(t1_causes)) == 2)
        run(review.cmd_touched, pages=["s2"], reason="corrected a number")
        check("causes: the same cause is not duplicated",
              len([c for p, _, c in wikimeta.pending_parse()[0] if p == "t1"]) == 2)
        first = sorted(t1_causes)[0]
        run(review.cmd_done, pages=["t1"], cause=first, outcome="unchanged", basis="re-read t1 against s1 and s2")
        left = [c for p, _, c in wikimeta.pending_parse()[0] if p == "t1"]
        check("causes: done --cause resolves only that cause", left == [c for c in t1_causes if c != first])
        run(review.cmd_done, pages=["t1"], cause=None, outcome="unchanged", basis="re-read t1 against s1 and s2")
        check("causes: done without --cause resolves the rest", "t1" not in queued())
        run(zot.cmd_stamp, keys=["s1"])
        clear_queue()

        # wiki-side change: stepwise propagation (concept c1 changed -> its dependents c3 and t1)
        subprocess.run(["git", "init", "-q", tmp], check=True)
        subprocess.run(["git", "-C", tmp, "add", "-A"], check=True)
        subprocess.run(["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], check=True)
        c1p = os.path.join(tmp, "concepts/c1.md")
        c1_text = open(c1p).read()
        open(c1p, "w").write(c1_text.replace("updated: 2026-10-18", "updated: 2026-10-19"))
        out = run(review.cmd_since, rev="HEAD", queue=True)
        check("since: a frontmatter-only edit is not a content change", "0 existing page(s) with changed content" in out and queued() == [])
        open(c1p, "a").write("A corrected claim ([[s1]] §2).\n")
        out = run(review.cmd_since, rev="HEAD", queue=True)
        check("since: a body edit queues the page's dependents (stepwise); t1's 'see [[c1]]' pointer is not one", queued() == ["c3"])
        check("since: the cause names the revised page", all(c.startswith("wiki:c1@") for _, _, c in wikimeta.pending_parse()[0]))
        clear_queue()

        # ---- sixth review: resolutions are kept, so finished reviews are not queued again ----
        open(c1p, "a").write("Another corrected claim ([[s1]] §3).\n")
        run(review.cmd_since, rev="HEAD", queue=True)
        first_round = queued()
        ok = True
        try:
            wikimeta.resolve_reviews(first_round, None, "not-affected", "")
            ok = False
        except ValueError:
            pass
        check("ledger: a resolution without a basis is refused", ok and queued() == first_round)
        run(review.cmd_done, pages=first_round, cause=None, outcome="not-affected", basis="neither page uses the c1 claim that changed")
        recs, probs = wikimeta.ledger_parse()
        mine = [r for r in recs if r[2] and r[2].startswith("wiki:c1@")]
        check("ledger: done records outcome, cause and every page", not probs and
              sorted(p for r in mine for p in r[3]) == first_round and all(r[1] == "not-affected" for r in mine))
        out = run(review.cmd_since, rev="HEAD", queue=True)
        check("ledger: repeating since with the same revision queues nothing", queued() == [] and f"{len(first_round)} already resolved" in out)
        open(c1p, "a").write("A third change ([[s1]] §4).\n")
        run(review.cmd_since, rev="HEAD", queue=True)
        check("ledger: a new revision of the cause is queued again", queued() == first_round)
        check("ledger: strict lint passes with a valid ledger and fails with open items", lint_strict()[0] == 1)
        run(review.cmd_done, pages=first_round, cause=None, outcome="unchanged", basis="re-read both pages against the third change")
        check("ledger: gate passes after resolution", lint_strict()[0] == 0)
        with open(wikimeta.REVIEWED, "a") as f:
            f.write("- 2026-10-18 fine (cause: wiki:c1@x) [[t1]] — whatever was checked\n- 2026-10-18 unchanged (cause: wiki:c1@x) [[nope]] — basis long enough\n- garbage line\n")
        code, out = lint_strict()
        check("ledger: unknown outcome and malformed line are errors; a link to a missing page is history, not an error",
              code == 1 and "unknown outcome" in out and "not in the form" in out and "[[nope]]" not in out)
        open(wikimeta.REVIEWED, "w").write(wikimeta.LEDGER_HEADER)

        # ---- sixth review: a missing Last-Modified-Version must not pass as a consistent snapshot ----
        import urllib.request as _ur

        class _Resp:
            def __init__(self, h): self.headers = h
            def __enter__(self): return self
            def __exit__(self, *a): return False
        real_lv, real_open = zot.library_version, _ur.urlopen
        zot.library_version = ORIG_LIBVER
        for hdr, label in (({}, "missing"), ({"Last-Modified-Version": "abc"}, "non-integer")):
            _ur.urlopen = lambda *a, _h=hdr, **k: _Resp(_h)
            try:
                ORIG_LIBVER()
                refused = False
            except SystemExit:
                refused = True
            check(f"snapshot: a {label} library version is an error, not a value", refused)
        _ur.urlopen = lambda *a, **k: _Resp({"Last-Modified-Version": "42"})
        check("snapshot: a valid library version parses to an int", ORIG_LIBVER() == 42)
        _ur.urlopen = real_open
        zot.library_version = lambda: None
        try:
            zot.snapshot("SRCAAAA1")
            refused = False
        except SystemExit:
            refused = True
        check("snapshot: None == None is never accepted as consistent", refused)
        zot.library_version = real_lv

        # ---- seventh round: proportionate propagation and generated bookkeeping ----
        def fake_pages(**bodies):
            return {n: [dict(dir=d, body=b, fields={})] for n, (d, b) in bodies.items()}
        fp = fake_pages(c9=("concepts", "x"), s9=("sources", "Uses [[c9]] §2 as evidence."), t9=("topics", "Cites [[s9]] Fig. 1."),
                        e9=("entities", "→ [[c9]], [[s9]]"), a9=("analyses", "see [[c9]] Table 2"))
        check("pointers: '→ [[x]]' is navigation, 'see [[x]] Table 2' is a citation",
              wikimeta.dependents(fp, "c9") == ["a9", "s9"] and "e9" not in wikimeta.dependents(fp, "s9"))
        check("propagation: a concept change does not chain through the sources that cite it",
              sorted(wikimeta.propagate(fp, "c9")) == ["a9", "s9"])
        fp2 = fake_pages(s8=("sources", "x"), s9=("sources", "Quotes [[s8]] Table 1."), t9=("topics", "Cites [[s9]] Fig. 1."))
        check("propagation: a source change still chains through quoting sources", sorted(wikimeta.propagate(fp2, "s8")) == ["s9", "t9"])
        open(c1p, "a").write("A locator fix ([[s1]] §4.1).\n")
        out = run(review.cmd_since, rev="HEAD", queue=True, neutral=["c1"])
        check("since: a page named --neutral is listed but not propagated", queued() == [] and "claim-neutral" in out)
        import catalog  # noqa: E402
        c3p = os.path.join(tmp, "concepts/c3.md")
        c3_text = open(c3p).read()
        open(c3p, "w").write(c3_text.replace("sources: [s3]", "sources: [s3, s2]"))
        code, out = lint_strict()
        check("catalog: a stale sources: list is reported", code == 1 and "catalog" in out)
        with contextlib.redirect_stdout(io.StringIO()):
            sys.argv, old_argv = ["catalog.py", "--apply"], sys.argv
            catalog.main()
            sys.argv = old_argv
        check("catalog: --apply re-derives sources: from the body",
              wikimeta.parse_frontmatter(open(c3p).read())[0]["sources"] == ["s3"])
        check("catalog: abbreviations", catalog.abbrev("Force Fields/Machine Learning/Active learning") == "FF/ML/Active learning")

        # ---- version_of: the earlier version of a cited work is integrated, not unintegrated (AGENTS.md §4) ----
        vp = {"later": [dict(dir="sources", body="x", fields={"zotero_key": "VERKEYL1", "read_depth": "full"})],
              "early": [dict(dir="sources", body="x", fields={"zotero_key": "VERKEYE1", "read_depth": "full",
                                                              "version_of": "later"})],
              "lone": [dict(dir="sources", body="x", fields={"zotero_key": "VERKEYN1", "read_depth": "full",
                                                             "version_of": "absent"})],
              "c9v": [dict(dir="concepts", body="A claim ([[later]] §1).", fields={})]}
        vs = wikimeta.source_states(vp)
        check("version_of: an earlier version counts as integrated once the later one is cited",
              vs["VERKEYL1"][1] == "integrated" and vs["VERKEYE1"][1] == "integrated")
        check("version_of: it does not excuse a page whose target is uncited", vs["VERKEYN1"][1] == "read")

        # ---- restatements: a corrected claim repeated on pages that do not cite the corrected page ----
        rp = {"c9": [dict(dir="concepts", body="Fixed claim.", fields={})],
              "t9": [dict(dir="topics", body="Every universal model is\nshort-ranged here.", fields={})],
              "e9": [dict(dir="entities", body="Unrelated.\n\n## Related\nevery universal model is short-ranged", fields={})],
              "s9": [dict(dir="sources", body="`every universal model is short-ranged`", fields={})]}
        check("restated: phrase found across a line break, not in Related lists, code or the corrected page itself",
              review.restating_pages(rp, "c9", ["every universal model is short-ranged"]) == {"t9": "every universal model is short-ranged"})
        open(c1p, "a").write("Restated elsewhere.\n")
        open(os.path.join(tmp, "concepts/c3.md"), "a").write("A claim that was Restated Elsewhere here.\n")
        out = run(review.cmd_restated, page="c1", phrase=["restated elsewhere"], reason="test")
        check("restated: queues the restating page with a cause naming the corrected page",
              queued() == ["c3"] and all(c.startswith("wiki:c1@") for _, _, c in wikimeta.pending_parse()[0]))
        run(review.cmd_done, pages=["c3"], cause=None, outcome="corrected", basis="restatement brought in line with c1")

        with open(wikimeta.PENDING, "a") as f:
            f.write("- [ ] [[c1|Concept one]] aliased item\n")
        check("queue: aliased item is recognized", queued() == ["c1"])
        with open(wikimeta.PENDING, "a") as f:
            f.write("- [ ] c1 without a wikilink\n- [x] [[t1]] done\n")
        code, out = lint_strict()
        check("queue: malformed open item is an error", "open item not in the form" in out and code == 1)
        check("queue: completed item left in place is an error", "completed item left" in out)
    finally:
        wikimeta.WIKI, wikimeta.PENDING, zot.PENDING, wikilint.WIKI, wikimeta.REVIEWED = saved

# ---- rendering PDF pages to images ----------------------------------------------------------
check("page range: single page, span, open end, all", (zot.page_range("4", 9), zot.page_range("3-7", 9),
      zot.page_range("5-", 9), zot.page_range(None, 9)) == ((4, 4), (3, 7), (5, 9), (1, 9)))
for _bad in ("0", "8-3", "2-12", "a-b"):
    try:
        zot.page_range(_bad, 9)
        check(f"page range {_bad!r} is refused", False)
    except SystemExit:
        check(f"page range {_bad!r} is refused", True)
if shutil.which("pdftoppm") and shutil.which("pdfinfo"):
    def _tiny_pdf(path, pages):
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
        open(path, "wb").write(out)
    _t = tempfile.mkdtemp(prefix="wiki-render-test-")
    _saved = (zot.get, zot.TMP)
    try:
        _pdf = os.path.join(_t, "paper.pdf")
        _tiny_pdf(_pdf, 12)
        zot.get = lambda path, **kw: {"key": "ATTPDF01", "data": {"itemType": "attachment", "contentType": "application/pdf",
                                                                   "linkMode": "linked_file", "path": _pdf}}
        zot.TMP = os.path.join(_t, "tmp")
        _out = run(zot.cmd_render, key="ATTPDF01", pages="9-11", dpi=20)
        _rows = [l.split("\t") for l in _out.splitlines()[1:]]
        check("render: one PNG per requested page, numbered by PDF page index",
              [r[0] for r in _rows] == ["9", "10", "11"] and all(os.path.isfile(r[1]) for r in _rows))
        check("render: pages land in the temp dir, outside the wiki",
              all(r[1].startswith(zot.TMP + os.sep) and not r[1].startswith(zot.WIKI + os.sep) for r in _rows))
        _out = run(zot.cmd_render, key="ATTPDF01", pages="2", dpi=20)
        check("render: a later call lists only its own pages", [l.split("\t")[0] for l in _out.splitlines()[1:]] == ["2"])
        run(zot.cmd_clean)
        check("clean: removes the temp dir", not os.path.exists(zot.TMP))
    finally:
        zot.get, zot.TMP = _saved
        shutil.rmtree(_t, ignore_errors=True)
else:
    print("skip render tests: poppler (pdftoppm, pdfinfo) not installed")

# ---- search ranks pages for a query ----------------------------------------------------------
import search  # noqa: E402


def _page(d, text):
    fields, body, errors = parse_frontmatter(text)
    return dict(dir=d, path=f"{d}/x.md", fields=fields, body=body, errors=errors)


_mention = "Charge equilibration is mentioned here among many other things. " + "Filler words about other topics. " * 60
_PAGES = {
    "charge-equilibration": [_page("concepts", "---\ntype: concept\n---\n# Charge equilibration (Qeq)\n\nShort definition.\n")],
    "longSourceMentioning2020": [_page("sources", "---\ntype: source\ntitle: \"A long paper\"\nread_depth: full\n"
                                       "collections: [\"Force Fields/Machine Learning/_root\"]\n---\n# Long\n\n"
                                       + _mention * 3 + "\ncharge equilibration again, and charge-equilibration.\n")],
    "behlerFourGenerations2021": [_page("sources", "---\ntype: source\ntitle: \"Four generations\"\n"
                                        "authors: [\"Behler, J.\"]\ncitekey: behlerFourGenerations2021\nread_depth: partial\n"
                                        "collections: [\"Porous Materials/ML\"]\n---\n# Four generations\n\n"
                                        "Neural networks for potentials. Expected improvement is not discussed.\n"
                                        "```\nzeolitecodeword\n```\n")],
    "bayes-opt": [_page("concepts", "---\ntype: concept\n---\n# BO\n\nThe improvement expected from a sample.\n")],
}


def _hits(*terms, phrases=(), **flt):
    a = argparse.Namespace(type=flt.get("type"), collection=flt.get("collection"), depth=flt.get("depth"))
    return [h[2] for h in search.search(_PAGES, terms, phrases, a, 10)]


check("search: the page named after the query outranks a long page that mentions it more often",
      _hits("charge", "equilibration")[:1] == ["charge-equilibration"])
check("search: hyphenated words match their parts", "longSourceMentioning2020" in _hits("equilibration"))
check("search: plurals fold ('network' finds 'networks')", _hits("network") == ["behlerFourGenerations2021"])
check("search: citekey and author words are searchable", _hits("behler")[:1] == ["behlerFourGenerations2021"])
check("search: --phrase requires the words in order",
      _hits("improvement", phrases=["expected improvement"]) == ["behlerFourGenerations2021"])
check("search: words inside code blocks are not indexed", _hits("zeolitecodeword") == [])
check("search: --type keeps one page type", set(_hits("charge", type="concept")) == {"charge-equilibration"})
check("search: --collection keeps sources by collection prefix",
      _hits("generations", "charge", collection="Porous Materials") == ["behlerFourGenerations2021"])
check("search: --depth keeps sources read to that depth", _hits("charge", depth="full") == ["longSourceMentioning2020"])
check("search: matched-word count is reported",
      search.search(_PAGES, ["charge", "zzz"], (), None, 10)[0][1] == 1)
check("search: no query words, no results", search.search(_PAGES, [], (), None, 10) == [])
check("search: the snippet is the best-matching body line",
      "Expected improvement" in search.snippet(_PAGES["behlerFourGenerations2021"][0]["body"],
                                               {"expected", "improvement"}, ["expected improvement"]))
check("search: a page without a title field is titled by its first heading",
      search.title_of("bayes-opt", _PAGES["bayes-opt"][0]) == "BO")

# ---- tools are checked against the installed skill -------------------------------------------
_t = tempfile.mkdtemp(prefix="wiki-tools-test-")
try:
    _wiki, _tmpl = os.path.join(_t, "w"), os.path.join(_t, "skill", "assets", "wiki-template", "tools")
    os.makedirs(os.path.join(_wiki, "tools"))
    os.makedirs(_tmpl)
    for _n in wikilint.TOOLS:
        for _d in (os.path.join(_wiki, "tools"), _tmpl):
            open(os.path.join(_d, _n), "w").write(f"# {_n}\n")
    _w = []
    wikilint.check_tools(_wiki, _w, _tmpl)
    check("tools: identical to the installed skill, no warning", _w == [])
    open(os.path.join(_wiki, "tools", "zot.py"), "a").write("# local edit\n")
    _w = []
    wikilint.check_tools(_wiki, _w, _tmpl)
    check("tools: a tool edited in the wiki is flagged", [m for _, m in _w] and "tools/zot.py" in _w[0][1] and len(_w) == 1)
    _w = []
    wikilint.check_tools(_wiki, _w, os.path.join(_t, "missing"))
    check("tools: a missing skill is flagged", len(_w) == 1 and "not installed" in _w[0][1])
    _w = []
    wikilint.check_tools(os.path.join(_t, "skill", "assets", "wiki-template"), _w, _tmpl)
    check("tools: the skill's own template is not compared with itself", _w == [])
finally:
    shutil.rmtree(_t, ignore_errors=True)

print(f"\n{len(FAILS)} failed")
sys.exit(1 if FAILS else 0)
