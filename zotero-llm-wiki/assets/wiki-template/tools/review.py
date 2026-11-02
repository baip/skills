#!/usr/bin/env python3
"""Review queue for wiki-side changes (AGENTS.md §4). `zot.py changed` handles changes that come from
Zotero; this tool handles changes made *in the wiki*, such as a corrected source page, a claim-audit fix, or a
revised concept, whose dependents may now be stale.

Propagation is stepwise. Changing a page queues its evidence dependents; navigation pointers (`→ [[x]]`,
"See [[x]]") do not count. A changed *source* page also reaches, through chains of source pages that quote
each other, their dependents. A queued page propagates further only if reviewing it actually changes it,
which you then report with `touched` or `since`. Measured 2026-10-18: a full transitive closure queues a
median of 136 of 139 pages; these rules give a median of 15 for a source change and 5 for a synthesis page.

`since` does not propagate an *additive* edit: one that only inserts whole lines and keeps every existing
non-blank line, in order (blank lines are ignored). Dependents rest on the existing sentences, which are intact.
An inserted [!contradiction] or [!stale] callout line still propagates, because it questions existing content.
An insertion that narrows an existing claim must also edit that claim (AGENTS.md §6.8), and that edit propagates.

Usage:
  review.py touched PAGE... [--reason TEXT]   queue the dependents of pages whose content you changed
  review.py since REV [--queue] [--neutral PAGE...]
                                              pages whose body changed since git REV, and their dependents;
                                              additive edits (inserted lines only) are listed but not
                                              propagated; --neutral names claim-neutral edits (locators,
                                              typos, wording that keeps the meaning), also not propagated
  review.py restated PAGE --phrase TEXT... [--reason TEXT]
                                              after correcting a claim on PAGE, queue every other page whose
                                              body still contains one of the phrases (case-insensitive), so
                                              restatements that do not cite PAGE are re-checked too
  review.py done PAGE... --outcome O --basis TEXT [--cause ID]
                                              resolve open items (all causes, or one) and record them in
                                              reviewed.md; O = corrected | unchanged | not-affected
  review.py list [--context]                  open items, grouped by page; --context also prints, for each
                                              item, the lines of the page that cite the changed page (or its
                                              part notes), which is what a review reads first

Review a dependent by reading the sentences that cite the changed page (`list --context`), and open the whole
page only when those sentences use the changed content; this keeps each review item's cost independent of page
and wiki size. A (page, cause) already recorded in reviewed.md is not queued again, so `since` can be repeated until it
queues nothing new. Record the basis honestly: *not-affected* means you checked that the page does not use the
part that changed, not merely that a keyword search found nothing.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True  # no __pycache__ inside the wiki, which may be cloud-synced
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wikimeta  # noqa: E402

HEADER = """# Pending review

Pages whose synthesis must be re-checked against their sources. Items are added by
`zot.py changed --queue`, `zot.py stamp`, `review.py touched|since`, or by hand. Resolve an item with
`review.py done PAGE --outcome O --basis TEXT [--cause ID]` only after re-reading the page against its sources;
the resolution is kept in reviewed.md. If that review changed the page, run `review.py touched PAGE` so its own
dependents are queued. `wikilint.py --strict` fails while items remain.

"""


def entries_for(pages, page, cause, reason):
    today = datetime.date.today().isoformat()
    out = []
    for d, via in sorted(wikimeta.propagate(pages, page).items()):
        how = f"uses [[{page}]] as evidence" if via is None else f"uses [[{via}]], which quotes [[{page}]]"
        out.append((d, cause, f"{how}; [[{page}]] changed in the wiki ({reason}): re-check · {today}"))
    return out


def cmd_touched(a):
    pages = wikimeta.load_pages()
    entries = []
    for page in a.pages:
        if page not in pages:
            sys.exit(f"unknown page {page}")
        cause = f"wiki:{page}@{wikimeta.body_hash(open(pages[page][0]['path']).read())}"
        entries += entries_for(pages, page, cause, a.reason)
    report(entries)


def report(entries):
    stats = {}
    n = wikimeta.queue_reviews(entries, HEADER, stats)
    print(f"queued {n} item(s)" + (f"; {stats['resolved']} already resolved in reviewed.md" if stats.get("resolved") else ""))


def restating_pages(pages, page, phrases):
    """Pages other than `page` whose body (outside code and link-list sections) contains any phrase, as
    {name: phrase}. Matching ignores case and collapses whitespace, so a phrase split across a line still matches."""
    norm = lambda s: " ".join(s.lower().split())
    want = [norm(x) for x in phrases if norm(x)]
    out = {}
    for name, vs in pages.items():
        if name == page:
            continue
        body = norm(wikimeta.strip_code(wikimeta.synthesis_body(vs[0]["body"])))
        hit = next((x for x in want if x in body), None)
        if hit:
            out[name] = hit
    return out


def cmd_restated(a):
    pages = wikimeta.load_pages()
    if a.page not in pages:
        sys.exit(f"unknown page {a.page}")
    cause = f"wiki:{a.page}@{wikimeta.body_hash(open(pages[a.page][0]['path']).read())}"
    today = datetime.date.today().isoformat()
    hits = restating_pages(pages, a.page, a.phrase)
    entries = [(d, cause, f"restates a claim corrected on [[{a.page}]] ({a.reason}; phrase \"{ph}\"): re-check · {today}")
               for d, ph in sorted(hits.items())]
    print(f"{len(hits)} page(s) still contain a corrected phrase: {', '.join(sorted(hits)) or 'none'}")
    report(entries)


FLAG_CALLOUT = re.compile(r"\[!(?:contradiction|stale)\b", re.I)


def additive(old_text, new_text):
    """True when the new body only inserts lines into the old one: every non-blank old line survives unchanged
    and in order, and no [!contradiction] or [!stale] callout was added."""
    old = [ln.rstrip() for ln in wikimeta.parse_frontmatter(old_text)[1].splitlines() if ln.strip()]
    new = [ln.rstrip() for ln in wikimeta.parse_frontmatter(new_text)[1].splitlines() if ln.strip()]
    rest = iter(new)
    if not all(any(ln == n for n in rest) for ln in old):  # greedy subsequence test
        return False
    count = lambda lines: sum(1 for ln in lines if FLAG_CALLOUT.search(ln))
    return count(new) <= count(old)


def git(*args):
    return subprocess.run(["git", "-C", wikimeta.WIKI, *args], capture_output=True, text=True)


def cmd_since(a):
    pages = wikimeta.load_pages()
    diff = git("diff", "--name-only", a.rev, "--", *wikimeta.DIRS)
    if diff.returncode:
        sys.exit(diff.stderr.strip())
    changed, new, added = [], [], []
    for rel in diff.stdout.split():
        name = os.path.basename(rel)[:-3] if rel.endswith(".md") else None
        if not name or name not in pages:
            continue  # deleted or not a page: lint reports broken links
        old = git("show", f"{a.rev}:{rel}")
        if old.returncode:
            new.append(name)  # new page: nothing could have relied on it yet
            continue
        now = open(pages[name][0]["path"]).read()
        if wikimeta.body_hash(old.stdout) != wikimeta.body_hash(now):
            (added if additive(old.stdout, now) else changed).append(name)
    neutral = [n for n in changed if n in (getattr(a, "neutral", None) or [])]
    changed = [n for n in changed if n not in neutral]
    if neutral:
        print(f"claim-neutral, not propagated (list them in the log): {', '.join(neutral)}")
    if added:
        print(f"{len(added)} additive edit(s), only inserted lines, not propagated (count them in the log): {', '.join(added)}")
    entries = []
    for name in changed:
        cause = f"wiki:{name}@{wikimeta.body_hash(open(pages[name][0]['path']).read())}"
        entries += entries_for(pages, name, cause, f"body changed since {a.rev}")
    print(f"{len(changed)} existing page(s) with changed content since {a.rev}: {', '.join(changed) or 'none'}")
    if new:
        print(f"{len(new)} new page(s), not propagated because nothing can depend on them yet: {', '.join(new)}")
    print("(pages created since REV, committed or not, never propagate; uncommitted new files are not listed)")
    print(f"{len({e[0] for e in entries})} dependent page(s) to review")
    if a.queue:
        report(entries)


def cmd_done(a):
    try:
        n = wikimeta.resolve_reviews(a.pages, a.cause, a.outcome, a.basis)
    except ValueError as e:
        sys.exit(str(e))
    print(f"resolved {n} item(s) on {len(a.pages)} page(s) as {a.outcome}" + (f" (cause {a.cause})" if a.cause else ""))


CAUSE_PAGE = re.compile(r"^(?:wiki|zotero):([^@]+)@")


def citing_lines(pages, page, target, width=320):
    """Lines of `page` (outside link-list sections and code) that link to `target` or to its part notes."""
    if page not in pages:
        return []
    names = wikimeta.source_group(pages, target)
    out = []
    for line in wikimeta.strip_code(wikimeta.synthesis_body(pages[page][0]["body"])).split("\n"):
        if names & set(wikimeta.links(line)):
            out.append(line.strip()[:width])
    return out


def cmd_list(a):
    items, problems = wikimeta.pending_parse()
    by = {}
    for page, note, cause in items:
        by.setdefault(page, []).append(cause or "(no cause)")
    pages = wikimeta.load_pages() if getattr(a, "context", False) else None
    for page in sorted(by):
        print(f"{page}: {', '.join(by[page])}")
        for cause in by[page] if pages else []:
            m = CAUSE_PAGE.match(cause)
            if m:
                for line in citing_lines(pages, page, m.group(1)) or ["(no citing line found: read the page)"]:
                    print(f"    {line}")
    for p in problems:
        print("PROBLEM", p)
    print(f"{len(items)} open item(s) on {len(by)} page(s)")
    records, problems = wikimeta.ledger_parse()
    for p in problems:
        print("LEDGER PROBLEM", p)
    if records:
        counts = {}
        for _, outcome, _, ps, _ in records:
            counts[outcome] = counts.get(outcome, 0) + len(ps)
        print("resolved so far: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("touched"); s.add_argument("pages", nargs="+"); s.add_argument("--reason", default="content revised")
    s = sub.add_parser("since"); s.add_argument("rev"); s.add_argument("--queue", action="store_true")
    s.add_argument("--neutral", nargs="+", default=[], metavar="PAGE")
    s = sub.add_parser("restated"); s.add_argument("page"); s.add_argument("--phrase", nargs="+", required=True)
    s.add_argument("--reason", default="claim corrected")
    s = sub.add_parser("done"); s.add_argument("pages", nargs="+"); s.add_argument("--cause")
    s.add_argument("--outcome", required=True, choices=wikimeta.OUTCOMES); s.add_argument("--basis", required=True)
    s = sub.add_parser("list"); s.add_argument("--context", action="store_true")
    a = p.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
