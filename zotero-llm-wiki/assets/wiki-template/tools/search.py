#!/usr/bin/env python3
"""Ranked search over the wiki's pages (AGENTS.md §8.3), so a query reads the pages it needs instead of the
whole index.

  python3 -I tools/search.py TERM… [--phrase TEXT]… [--type source|concept|entity|topic|analysis]
                             [--collection PREFIX] [--depth full|partial|abstract|metadata-only] [-n 15]

Ranking is BM25 over each page's words, with the title, aliases, tags, authors, citekey, filename and headings
counted extra. Every TERM argument is split into words; a page needs only some of them, and the count of query
words a page matched is printed (e.g. 3/4). `--phrase` (repeatable) requires its words in that order, case- and
whitespace-insensitively, and also ranks by them. Words are lowercased, split at hyphens, and plurals folded
('networks' finds 'network'); there is no other stemming and no embedding, so try synonyms and abbreviations.

Filters: `--type` keeps one page type; `--collection` keeps sources whose `collections:` (or topics whose
`zotero_collections:`) contain a path starting with PREFIX; `--depth` keeps sources read to that depth.

Output: one line per page (score, path, type, title; for sources the read depth), then the line that matches
best. Read-only; standard library only.
"""
import argparse
import math
import os
import re
import sys
from collections import Counter

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wikimeta  # noqa: E402

TYPES = {"source": "sources", "concept": "concepts", "entity": "entities", "topic": "topics",
         "analysis": "analyses"}
DEPTHS = ("full", "partial", "abstract", "metadata-only")
WORD = re.compile(r"[^\W_]+")
CAMEL = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
WEIGHTS = {"title": 3, "head": 2, "meta": 2, "body": 1}  # repeats per occurrence (BM25F-lite)
K1, B = 1.2, 0.75
TITLE_BOOST = 1.5  # weight of the title-only BM25 term added to the whole-page one


def fold(w):
    """Lowercase plural folding, applied to pages and queries alike."""
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def words(text):
    return [fold(w) for w in WORD.findall(text.lower())]


def camel_words(name):
    """'behlerFourGenerations2021' -> behler, four, generations, 2021 (plus the whole key)."""
    return [fold(w.lower()) for w in CAMEL.findall(name)] + [name.lower()]


def flat(v):
    if isinstance(v, dict):
        return " ".join(str(x) for x in list(v.keys()) + list(v.values()))
    if isinstance(v, list):
        return " ".join(str(x) for x in v)
    return "" if v is None else str(v)


def squash(text):
    return " ".join(text.lower().split())


def heading(body):
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def title_of(name, page):
    return flat(page["fields"].get("title")) or heading(page["body"]) or name


def page_terms(name, fields, body):
    """(weighted term counts of the whole page, its weighted length, term counts of the title alone, its length).
    The title (title, aliases, first heading, filename) is also ranked on its own, so that a page named after the
    query outranks long pages that only mention it."""
    tf = Counter()
    title = (words(flat(fields.get("title"))) + words(flat(fields.get("aliases"))) + words(heading(body))
             + camel_words(name))
    meta = (words(flat(fields.get("tags"))) + words(flat(fields.get("authors"))) + words(flat(fields.get("venue")))
            + camel_words(flat(fields.get("citekey"))) + words(flat(fields.get("zotero_key"))))
    heads, rest = [], []
    for line in wikimeta.strip_code(body).splitlines():
        (heads if line.lstrip().startswith("#") else rest).append(line)
    for part, ws in (("title", title), ("meta", meta), ("head", words("\n".join(heads))),
                     ("body", words("\n".join(rest)))):
        for w in ws:
            tf[w] += WEIGHTS[part]
    tt = Counter(title)
    return tf, sum(tf.values()), tt, sum(tt.values())


def collections_of(page):
    f = page["fields"]
    v = f.get("collections") if page["dir"] == "sources" else f.get("zotero_collections")
    if isinstance(v, dict):
        return [str(x) for x in v.values()]
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)] if v else []


def keep(page, a):
    if a.type and page["dir"] != TYPES[a.type]:
        return False
    if a.collection and not any(c.startswith(a.collection) for c in collections_of(page)):
        return False
    if a.depth and (page["dir"] != "sources" or page["fields"].get("read_depth") != a.depth):
        return False
    return True


def snippet(body, qwords, phrases, width=160):
    """The body line with the most distinct query words (a phrase counts double), trimmed around the first hit."""
    best, best_score = "", 0
    for line in wikimeta.strip_code(body).splitlines():
        s = line.strip()
        if not s or s.startswith("---") or s.startswith("# "):
            continue
        lw = set(words(s))
        score = len(lw & qwords) + 2 * sum(p in squash(s) for p in phrases)
        if score > best_score:
            best, best_score = s, score
    if len(best) <= width:
        return best
    low = best.lower()
    hits = [low.find(p) for p in phrases if p in squash(best)] + \
        [m.start() for m in WORD.finditer(low) if fold(m.group()) in qwords]
    start = max(0, min(hits) - width // 4) if hits else 0
    return ("…" if start else "") + best[start:start + width].strip() + "…"


def search(pages, terms, phrases=(), a=None, limit=15):
    """[(score, matched, name, page)] best first. pages: wikimeta.load_pages() output."""
    phrases = [squash(p) for p in phrases if p.strip()]
    query = words(" ".join(list(terms) + phrases))
    qset = set(query)
    docs = []
    for name, vs in pages.items():
        for page in vs:
            if a is None or keep(page, a):
                docs.append((name, page) + page_terms(name, page["fields"], page["body"]))
    if not docs or not qset:
        return []
    avg = sum(d[3] for d in docs) / len(docs)
    avg_t = sum(d[5] for d in docs) / len(docs) or 1
    df = Counter(w for d in docs for w in qset if d[2][w])

    def bm25(f, length, mean, idf):
        return idf * f * (K1 + 1) / (f + K1 * (1 - B + B * length / mean))

    out = []
    for name, page, tf, length, tt, tlen in docs:
        if phrases:
            text = squash(flat(page["fields"].get("title")) + " " + page["body"])
            if not all(p in text for p in phrases):
                continue
        score, matched = 0.0, 0
        for w in qset:
            if not tf[w]:
                continue
            matched += 1
            idf = math.log(1 + (len(docs) - df[w] + 0.5) / (df[w] + 0.5))
            score += bm25(tf[w], length, avg, idf) + (TITLE_BOOST * bm25(tt[w], tlen, avg_t, idf) if tt[w] else 0)
        if matched:
            out.append((score, matched, name, page))
    out.sort(key=lambda r: (-r[0], r[2]))
    return out[:limit]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("terms", nargs="*", help="search words (any order; a page needs only some)")
    ap.add_argument("--phrase", action="append", default=[], help="exact phrase the page must contain")
    ap.add_argument("--type", choices=sorted(TYPES))
    ap.add_argument("--collection", help="Zotero collection path prefix")
    ap.add_argument("--depth", choices=DEPTHS)
    ap.add_argument("-n", type=int, default=15, help="results to show (default 15)")
    a = ap.parse_args()
    if not a.terms and not a.phrase:
        ap.error("give search words or --phrase")
    pages = wikimeta.load_pages()
    hits = search(pages, a.terms, a.phrase, a, a.n)
    nq = len(set(words(" ".join(a.terms + a.phrase))))
    if not hits:
        print("no matches")
        return 1
    for score, matched, name, page in hits:
        f = page["fields"]
        kind = page["dir"][:-1] if page["dir"] != "entities" else "entity"
        kind = "analysis" if page["dir"] == "analyses" else kind
        depth = f" · {f.get('read_depth')}" if page["dir"] == "sources" and f.get("read_depth") else ""
        title = title_of(name, page)
        print(f"{score:6.1f}  {page['dir']}/{name}.md  [{kind}{depth}] {title}  ({matched}/{nq})")
        snip = snippet(page["body"], set(words(" ".join(a.terms + a.phrase))), [squash(p) for p in a.phrase])
        if snip:
            print(f"        {snip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
