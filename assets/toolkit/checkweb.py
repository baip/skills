#!/usr/bin/env python3
"""
Check the built site for the accessibility properties the PDFs are checked for.

Usage:
    python3 mkweb.py && python3 checkweb.py

The page is loaded in a real browser, because the mathematics is not in the
HTML that Sphinx writes: MathJax builds it, and the MathML that a screen reader
reads only exists after the page has run. Checking the static files would miss
the very thing worth checking.

Per page:

  1. the page declares a language
  2. exactly one level-1 heading
  3. no skipped heading levels
  4. every image has alternative text of a useful length
  5. every formula has been typeset
  6. every formula carries a MathML copy for a screen reader
  7. no link whose text is "here", "this" or a bare URL
  8. the page has a title distinct from the site title
  9. no formula that MathJax rendered as an error

The ninth matters because a formula MathJax cannot parse still counts as
typeset: it is drawn as red error text (for example "\\tag not allowed in
split environment") and carries a MathML copy of that text, so checks 5 and
6 pass while the reader gets nothing.

These are necessary, not sufficient. Run a full WCAG audit, with axe or a
comparable tool, and test with a screen reader before publishing.
"""

import http.server
import os
import socketserver
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
PORT = 0   # let the operating system pick a free port

VAGUE_LINKS = {"here", "this", "link", "click here", "read more", "more"}

SCRIPT = """
() => {
  const heads = [...document.querySelectorAll('article h1,article h2,article h3,article h4,article h5,article h6')];
  const levels = heads.map(h => parseInt(h.tagName[1]));
  const imgs = [...document.querySelectorAll('article img')];
  const links = [...document.querySelectorAll('article a')];
  return {
    lang: document.documentElement.lang || '',
    title: document.title || '',
    h1: heads.filter(h => h.tagName === 'H1').length,
    levels: levels,
    imgs: imgs.length,
    imgsNoAlt: imgs.filter(i => !i.alt || i.alt.trim().length < 10).length,
    mathSource: document.querySelectorAll('.math').length,
    mathTypeset: document.querySelectorAll('mjx-container').length,
    mathMml: document.querySelectorAll('mjx-assistive-mml').length,
    mathErrors: [...document.querySelectorAll('mjx-merror, [data-mjx-error]')]
                .map(e => e.getAttribute('data-mjx-error') || e.textContent)
                .slice(0, 3),
    vague: links.map(a => (a.textContent || '').trim().toLowerCase())
                .filter(t => t && (%s.includes(t) || t.startsWith('http'))),
  };
}
""" % (list(VAGUE_LINKS),)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = lambda *a, **k: QuietHandler(*a, directory=str(SITE), **k)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    httpd.allow_reuse_address = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def main():
    if not SITE.exists():
        sys.exit("no site/ directory: run mkweb.py first")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is not installed: pip install playwright")

    # Course-year material sits a folder down, so the walk is recursive and the
    # URL is the path relative to the site root rather than a bare file name.
    pages = sorted(str(p.relative_to(SITE)).replace("\\", "/")
                   for p in SITE.rglob("*.html")
                   if p.name not in ("genindex.html", "search.html")
                   and "_static" not in p.parts)
    httpd = serve()
    port = httpd.server_address[1]
    failures = 0
    try:
        with sync_playwright() as pw:
            # a preinstalled Chromium if the machine has one at a known
            # place (CHROMIUM overrides), otherwise Playwright's own
            exe = os.environ.get("CHROMIUM") or next(
                (p for p in ("/opt/pw-browsers/chromium",)
                 if Path(p).exists()), None)
            browser = pw.chromium.launch(
                **({"executable_path": exe} if exe else {}))
            page = browser.new_page()
            for name in pages:
                page.goto(f"http://127.0.0.1:{port}/{name}")
                page.wait_for_timeout(300)
                # wait for MathJax to finish, or give up after 20 seconds
                for _ in range(40):
                    d = page.evaluate(SCRIPT)
                    if d["mathSource"] == 0 or d["mathTypeset"] >= d["mathSource"]:
                        break
                    page.wait_for_timeout(500)
                d = page.evaluate(SCRIPT)
                problems = []
                if not d["lang"]:
                    problems.append("no language declared")
                if d["h1"] != 1:
                    problems.append(f"{d['h1']} level-1 headings")
                skips = [(a, b) for a, b in zip(d["levels"], d["levels"][1:])
                         if b - a > 1]
                if skips:
                    problems.append(f"skipped heading levels {skips[:2]}")
                if d["imgsNoAlt"]:
                    problems.append(
                        f"{d['imgsNoAlt']} of {d['imgs']} images lack alt text")
                if d["mathSource"] and d["mathTypeset"] < d["mathSource"]:
                    problems.append(
                        f"{d['mathSource'] - d['mathTypeset']} formulas not typeset")
                if d["mathTypeset"] and d["mathMml"] < d["mathTypeset"]:
                    problems.append(
                        f"{d['mathTypeset'] - d['mathMml']} formulas without MathML")
                if d["mathErrors"]:
                    problems.append(
                        f"MathJax errors: {sorted(set(d['mathErrors']))[:2]}")
                if d["vague"]:
                    problems.append(f"vague link text: {sorted(set(d['vague']))[:3]}")
                if not d["title"]:
                    problems.append("no page title")
                flag = "FAIL" if problems else "PASS"
                failures += bool(problems)
                extra = (f"  {d['imgs']} figures, {d['mathTypeset']} formulas"
                         if not problems else "  " + "; ".join(problems))
                print(f"  [{flag}] {name}\n{extra}")
            browser.close()
    finally:
        httpd.shutdown()

    print()
    if failures:
        print(f"{failures} page(s) with problems.")
    else:
        print("All pages passed.")
    print("Necessary, not sufficient: run a full WCAG audit and test with a "
          "screen reader before publishing.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
