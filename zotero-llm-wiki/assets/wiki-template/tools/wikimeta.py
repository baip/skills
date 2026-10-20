"""Shared helpers: a strict parser for the wiki's YAML-frontmatter subset, protected text spans,
page loading, the derived ingestion state of each source page, and the pending.md review queue
(AGENTS.md §2.6, §2.9, §4, §8.2).

Frontmatter subset: `key: value` lines whose value is a plain scalar, a quoted scalar, a flow list
`[a, "b, c"]` or a flow map `{K: "v"}`. Quoted scalars follow YAML: `''` is an escaped quote inside single
quotes, and double quotes accept the escapes in DQ_ESCAPES. Anything else (block lists, multi-line values,
other escapes) is reported as an error rather than guessed.
"""
import contextlib
import fcntl
import hashlib
import os
import re
import tempfile

WIKI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ["sources", "concepts", "entities", "topics", "analyses"]
LINK = re.compile(r"\[\[([^\]|#\\]+)(?:#[^\]|]*)?(?:\\?\|[^\]]*)?\]\]")
PENDING = os.path.join(WIKI, "pending.md")
REVIEWED = os.path.join(WIKI, "reviewed.md")

# ---------------------------------------------------------------- frontmatter parsing

DQ_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t", "r": "\r", "0": "\0"}


def _starts_quote(s, i):
    """A quote opens a quoted scalar only at the start of a value or element."""
    return s[i] in "\"'" and (i == 0 or s[i - 1] in " \t[{,:")


def _quoted_end(s, i):
    """Index just past the quoted scalar that starts at s[i]. Raises on an unterminated quote."""
    q, j = s[i], i + 1
    while j < len(s):
        if q == '"' and s[j] == "\\":
            j += 2
            continue
        if s[j] == q:
            if q == "'" and j + 1 < len(s) and s[j + 1] == "'":
                j += 2
                continue
            return j + 1
        j += 1
    raise ValueError("unterminated quote")


def _split_flow(s):
    """Split the inside of a flow collection on top-level commas, respecting quotes and nesting."""
    out, cur, depth, i = [], "", 0, 0
    while i < len(s):
        ch = s[i]
        if ch in "\"'" and (not cur.strip() or cur.rstrip().endswith(":")):  # an element, or a map value after "key:"
            j = _quoted_end(s, i)
            cur += s[i:j]
            i = j
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip():
        out.append(cur)
    return [x.strip() for x in out]


def _scalar(v):
    v = v.strip()
    if v[:1] == "'":
        if len(v) < 2 or _quoted_end(v, 0) != len(v):
            raise ValueError("text after a closing quote, or malformed single-quoted string")
        return v[1:-1].replace("''", "'")
    if v[:1] == '"':
        if len(v) < 2 or _quoted_end(v, 0) != len(v):
            raise ValueError("text after a closing quote, or malformed double-quoted string")
        out, i, inner = [], 0, v[1:-1]
        while i < len(inner):
            if inner[i] == "\\":
                esc = inner[i + 1] if i + 1 < len(inner) else ""
                if esc not in DQ_ESCAPES:
                    raise ValueError(f"unsupported escape \\{esc} in a double-quoted string")
                out.append(DQ_ESCAPES[esc])
                i += 2
            else:
                out.append(inner[i])
                i += 1
        return "".join(out)
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _split_comment(raw):
    """Strip a trailing comment. ' #' starts a comment only outside quoted scalars and flow collections.
    Raises on unbalanced quotes or brackets."""
    depth, i = 0, 0
    while i < len(raw):
        ch = raw[i]
        if _starts_quote(raw, i):
            i = _quoted_end(raw, i)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced brackets")
        elif ch == "#" and i > 0 and raw[i - 1] in " \t" and depth == 0:
            return raw[:i].rstrip()
        i += 1
    if depth:
        raise ValueError("unbalanced brackets")
    return raw.rstrip()


def parse_value(v):
    v = _split_comment(v.strip())
    if v.startswith("["):
        if not v.endswith("]"):
            raise ValueError("text after a closing ']'")
        return [_scalar(x) for x in _split_flow(v[1:-1])]
    if v.startswith("{"):
        if not v.endswith("}"):
            raise ValueError("text after a closing '}'")
        out = {}
        for x in _split_flow(v[1:-1]):
            k, sep, val = x.partition(":")
            if not sep:
                raise ValueError(f"map entry without ':' ({x})")
            out[_scalar(k)] = _scalar(val)
        return out
    return _scalar(v)


def parse_frontmatter(text):
    """Return (fields, body, errors)."""
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text, ["no frontmatter block"]
    fields, errors = {}, []
    for n, line in enumerate(m.group(1).splitlines(), 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kv = re.match(r"^([a-z_]+):(?:\s(.*)|)$", line)
        if not kv:
            errors.append(f"line {n}: not a 'key: value' line (block lists and multi-line values are unsupported)")
            continue
        key, raw = kv.group(1), kv.group(2) or ""
        if key in fields:
            errors.append(f"duplicate key {key}")
        try:
            fields[key] = parse_value(raw)
        except ValueError as e:
            errors.append(f"{key}: {e}")
    return fields, text[m.end():], errors


# ---------------------------------------------------------------- protected text (§2.9)

FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def fenced_blocks(text):
    """(start, end) spans of fenced code blocks per CommonMark: an opening run of >= 3 backticks or
    tildes indented <= 3 spaces, closed by a run of the same character at least as long. An unclosed
    fence runs to the end of the document."""
    lines = text.splitlines(keepends=True)
    starts, pos = [], 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln)
    spans, i = [], 0
    while i < len(lines):
        m = FENCE_OPEN.match(lines[i])
        if not m or (m.group(1)[0] == "`" and "`" in lines[i][m.end():]):  # a backtick info string may not hold `
            i += 1
            continue
        fence = m.group(1)
        close = re.compile(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*\r?\n?$")
        j = i + 1
        while j < len(lines) and not close.match(lines[j]):
            j += 1
        spans.append((starts[i], starts[j] + len(lines[j]) if j < len(lines) else len(text)))
        i = j + 1
    return spans


def protected_spans(text):
    """(start, end) character spans that rewriting tools must never change: fenced code blocks
    (``` or ~~~), inline code spans (equal backtick runs), and `> [!user]` callouts (header plus the
    following `>` lines)."""
    spans = fenced_blocks(text)

    def inside(p):
        return any(a <= p < b for a, b in spans)
    for m in re.finditer(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", text, re.S):
        if not inside(m.start()) and "\n\n" not in m.group(2):
            spans.append(m.span())
    for m in re.finditer(r"^> \[!user\][^\n]*\n?(?:>[^\n]*\n?)*", text, re.M):
        spans.append(m.span())
    return sorted(spans)


def in_spans(pos, spans):
    return any(a <= pos < b for a, b in spans)


def protected_text(text):
    return [text[a:b] for a, b in protected_spans(text)]


def strip_code(text):
    """Text with fenced and inline code removed (for link extraction)."""
    spans = [s for s in protected_spans(text) if not text[s[0]:s[1]].startswith("> [!user]")]
    out, last = [], 0
    for a, b in spans:
        if a >= last:
            out.append(text[last:a])
            last = b
    out.append(text[last:])
    return "".join(out)


def links(body):
    return {t.strip() for t in LINK.findall(strip_code(body))}


# ---------------------------------------------------------------- pages and states

def load_pages():
    """name -> list of dict(dir, path, fields, body, errors)."""
    pages = {}
    for d in DIRS:
        p = os.path.join(WIKI, d)
        for f in sorted(os.listdir(p)) if os.path.isdir(p) else []:
            if f.endswith(".md"):
                path = os.path.join(p, f)
                text = open(path).read()
                fields, body, errors = parse_frontmatter(text)
                pages.setdefault(f[:-3], []).append(dict(dir=d, path=path, fields=fields, body=body, errors=errors))
    return pages


LIST_SECTIONS = ("Related", "Sources", "Connections")


def synthesis_body(body):
    """The body without its link-list sections (## Related, ## Sources, ## Connections). A link there
    is related-work context; a citation anywhere else uses the target as evidence."""
    out, skip = [], False
    for line in body.splitlines():
        h = re.match(r"^##\s+(.*?)\s*$", line)
        if h:
            skip = h.group(1) in LIST_SECTIONS
        if not skip:
            out.append(line)
    return "\n".join(out)


def source_states(pages=None):
    """zotero_key -> (citekey, state):
    metadata   - page exists but read_depth is abstract or metadata-only
    read       - read (full/partial) but cited in no concept/entity/topic text
    integrated - read, and cited in the body text (not just a Related/Sources list) of at least one
                 concept, entity or topic page. A structural proxy: the source is used somewhere, not
                 proof that every claim it bears on has been synthesized.
    """
    pages = pages or load_pages()
    cited = set()
    for name, versions in pages.items():
        for pg in versions:
            if pg["dir"] in ("concepts", "entities", "topics"):
                cited |= links(synthesis_body(pg["body"]))
    out = {}
    for name, versions in pages.items():
        for pg in versions:
            f = pg["fields"]
            if pg["dir"] != "sources" or not f.get("zotero_key"):
                continue
            depth = f.get("read_depth")
            state = "metadata" if depth in ("abstract", "metadata-only") else "integrated" if name in cited else "read"
            out[f["zotero_key"]] = (name, state)
    return out


EVIDENCE_DIRS = ("sources", "concepts", "entities", "topics", "analyses")


POINTER_RUN = re.compile(r"(?:→|\b[Ss]ee(?: also)?\b|\bcf\.)\s*((?:\[\[[^\]]+\]\](?:\s*(?:,|·|;|and|or)\s*)?)+)")
LOCATOR_AFTER = re.compile(r"\s*\(?(?:§|Figs?\.|Tables?|eqs?\b|pp?\.|SI\b|App\.)")


def evidence_links(body):
    """Pages a body uses as evidence: its links outside the link-list sections, minus *navigation pointers*.
    A pointer is a link in a run introduced by "→", "See" or "cf." (`→ [[x]], [[y]]`), unless a locator
    follows it (`see [[x]] Table 2` is a citation). Pointers say where to read more, not what a claim rests
    on, so a change to their target does not make this page stale. Lint's `sources:` check still counts
    every link (wikimeta.links)."""
    text = strip_code(synthesis_body(body))
    keep = []
    last = 0
    for run in POINTER_RUN.finditer(text):
        keep.append(text[last:run.start(1)])
        for m in LINK.finditer(run.group(1)):
            if LOCATOR_AFTER.match(text, run.start(1) + m.end()):
                keep.append(" " + m.group(0) + " ")
        last = run.end(1)
    keep.append(text[last:])
    return {t.strip() for t in LINK.findall("".join(keep))}


def evidence_index(pages):
    """target -> set of pages that cite it as evidence: any source, concept, entity, topic or analysis
    page citing it outside its link-list sections and not merely as a navigation pointer (evidence_links).
    Built in one pass."""
    rev = {}
    for n, vs in pages.items():
        if vs[0]["dir"] in EVIDENCE_DIRS:
            for t in evidence_links(vs[0]["body"]):
                if t != n:
                    rev.setdefault(t, set()).add(n)
    return rev


def dependents(pages, name, index=None):
    """Pages that use page `name` as evidence (direct only)."""
    return sorted((index or evidence_index(pages)).get(name, ()))


def propagate(pages, start, index=None):
    """Pages to review when `start` changes: its direct dependents. When `start` is a *source* page, also
    (transitively) the dependents of every source page that cites it, because a source page that quotes
    another source's results re-states them. A change to a concept, entity, topic or analysis page queues
    only its direct dependents: a source page citing a concept does not re-state it. Synthesis pages
    propagate further only when a review actually changes them (tools/review.py touched/since).
    Cycle-safe. Returns {page: via}, where via is the source page through which it was reached (None = direct)."""
    index = index or evidence_index(pages)
    chain = pages[start][0]["dir"] == "sources" if start in pages else False
    out, frontier, seen = {}, [(start, None)], {start}
    while frontier:
        node, via = frontier.pop()
        for d in sorted(index.get(node, ())):
            if d in seen:
                continue
            seen.add(d)
            out[d] = via
            if chain and pages[d][0]["dir"] == "sources":
                frontier.append((d, d))
    return out


# ---------------------------------------------------------------- fingerprints (§4)

FP_VERSION = "v3"
FP_PARTS = {"v3": ("biblio", "abstract", "pdf", "notes", "ann"), "v2": ("meta", "pdf", "notes", "ann")}
FP_HASH = re.compile(r"^([0-9a-f]{8}|none)$")


def parse_fingerprint(s):
    """(version, {part: hash}) for a complete, well-formed fingerprint, else None. A fingerprint with a
    missing, extra, duplicated or malformed part is *incomplete*: it can certify nothing."""
    toks = str(s or "").split()
    if not toks or toks[0] not in FP_PARTS:
        return None
    parts = {}
    for t in toks[1:]:
        k, sep, v = t.partition(":")
        if not sep or k in parts or not FP_HASH.match(v):
            return None
        parts[k] = v
    if set(parts) != set(FP_PARTS[toks[0]]):
        return None
    return toks[0], parts


# ---------------------------------------------------------------- safe file writes

def atomic_write(path, text):
    """Write via a temp file in the same directory and os.replace, so readers never see a partial file."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix="." + os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def locked(path):
    """Exclusive inter-process lock for read-modify-write of `path`. The lock file lives in the system temp
    directory (not in the Drive-synced wiki), keyed by the file's absolute path."""
    key = hashlib.sha1(os.path.abspath(path).encode()).hexdigest()[:12]
    lock = os.path.join(tempfile.gettempdir(), f"zotero-wiki-{key}.lock")
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------- review queue (§4)
# Line format:  - [ ] [[page]] note (cause: <id>)
# One page may carry several open items, one per cause, so a later reason is never swallowed by an earlier
# one. A cause id names what is being reviewed and its revision, e.g. `zotero:<citekey>@<fp-hash>` or
# `wiki:<page>@<body-hash>`. Hand-written items may omit the cause.
#
# Resolving an item moves it to the append-only ledger reviewed.md, with an outcome and its basis, so a
# completed review is never queued again for the same cause and the clearance stays auditable:
#   - YYYY-MM-DD <outcome> (cause: <id>) [[page]], [[page]] — <basis>
# One line may resolve several pages for the same cause, outcome and basis. Causeless items are recorded with
# `(cause: none)`; that never suppresses a later item.

PENDING_ITEM = re.compile(r"^\s*[-*+] \[ \] \[\[([^\]|#\\]+)(?:\\?\|[^\]]*)?\]\]\s*(.*?)\s*$")
CHECKBOX = re.compile(r"^\s*[-*+] \[([ xX])\]")
CAUSE = re.compile(r"\(cause: ([^\s()]+)\)\s*$")


def pending_parse():
    """(items, problems) from pending.md. items: (page, note, cause or None). problems: checkbox lines the
    reader cannot interpret, and checked items that should have been deleted. A completion gate must treat
    problems as failures, never as an empty queue."""
    if not os.path.exists(PENDING):
        return [], []
    items, problems = [], []
    for n, line in enumerate(open(PENDING).read().splitlines(), 1):
        box = CHECKBOX.match(line)
        if not box:
            continue
        m = PENDING_ITEM.match(line)
        if m:
            c = CAUSE.search(m.group(2))
            items.append((m.group(1).strip(), m.group(2).strip(), c.group(1) if c else None))
        elif box.group(1) in "xX":
            problems.append(f"line {n}: completed item left in the queue (delete it): {line.strip()[:80]}")
        else:
            problems.append(f"line {n}: open item not in the form '- [ ] [[page]] note': {line.strip()[:80]}")
    return items, problems


def pending_items():
    """Open items as (page, note)."""
    return [(p, n) for p, n, _ in pending_parse()[0]]


def queue_reviews(entries, header, stats=None):
    """Append review items to pending.md. entries: (page, cause, note) or legacy (page, note). An item is
    skipped if the same (page, cause) is already open, or was already resolved (reviewed.md), so every
    distinct cause is kept and no finished review is redone. Returns the count queued; `stats`, if given,
    receives the number skipped as already resolved. Safe under concurrency: the read-modify-write holds an
    exclusive lock, with atomic replace."""
    with locked(PENDING):
        existing = {(p, c) for p, _, c in pending_parse()[0]}
        done = resolved_keys()
        lines, seen, skipped = [], set(), 0
        for e in entries:
            page, cause, note = e if len(e) == 3 else (e[0], None, e[1])
            if (page, cause) in existing or (page, cause) in seen:
                continue
            if cause and (page, cause) in done:
                skipped += 1
                continue
            seen.add((page, cause))
            lines.append(f"- [ ] [[{page}]] {note}" + (f" (cause: {cause})" if cause else "") + "\n")
        if stats is not None:
            stats["resolved"] = skipped
        if not lines:
            return 0
        text = open(PENDING).read() if os.path.exists(PENDING) else header
        text = text.replace("*(no open items)*\n", "")
        if not text.endswith("\n"):
            text += "\n"
        atomic_write(PENDING, text + "".join(lines))
        return len(lines)


OUTCOMES = ("corrected", "unchanged", "not-affected")
LEDGER_HEADER = """# Review ledger

Append-only record of resolved review items (AGENTS.md §4), written by `review.py done`. Each line gives the
date, the outcome, the cause that was reviewed, the pages, and the basis for the outcome:

* *corrected*: the page was changed to fit the revised evidence (and reported with `review.py touched`);
* *unchanged*: the page uses the revised content, was re-read against it, and still holds;
* *not-affected*: the page depends on the changed page, but not on the part that changed.

A (page, cause) recorded here is never queued again. A new revision of the cause is a new cause.

"""
LEDGER_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (\S+) \(cause: ([^\s()]+)\) ((?:\[\[[^\]|#\\]+\]\](?:, )?)+) — (.+)$")


def ledger_parse():
    """(records, problems) from reviewed.md. records: (date, outcome, cause or None, [pages], basis)."""
    if not os.path.exists(REVIEWED):
        return [], []
    records, problems = [], []
    for n, line in enumerate(open(REVIEWED).read().splitlines(), 1):
        if not line.startswith("- "):
            continue
        m = LEDGER_LINE.match(line)
        if not m:
            problems.append(f"line {n}: not in the form '- DATE OUTCOME (cause: ID) [[page]], … — basis': {line[:80]}")
            continue
        date, outcome, cause, plist, basis = m.groups()
        if outcome not in OUTCOMES:
            problems.append(f"line {n}: unknown outcome {outcome!r} (use {', '.join(OUTCOMES)})")
        if len(basis.strip()) < 10:
            problems.append(f"line {n}: the basis is missing or too short")
        records.append((date, outcome, None if cause == "none" else cause, LINK.findall(plist), basis.strip()))
    return records, problems


def resolved_keys():
    """(page, cause) pairs already resolved; causeless records never count."""
    return {(p, c) for _, _, c, ps, _ in ledger_parse()[0] if c for p in ps}


def resolve_reviews(pages, cause=None, outcome=None, basis=None, date=None):
    """Resolve the open items of `pages` (all causes, or only `cause`): record them in reviewed.md with the
    outcome and its basis, one line per cause, then delete them from pending.md. Returns the count resolved.
    The ledger is written first, so an interruption can leave an item open but never lose a resolution."""
    import datetime
    if isinstance(pages, str):
        pages = [pages]
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(OUTCOMES)}")
    if not basis or len(basis.strip()) < 10 or "\n" in basis:
        raise ValueError("give the basis for the outcome in one line (at least 10 characters)")
    date = date or datetime.date.today().isoformat()
    with locked(PENDING), locked(REVIEWED):
        if not os.path.exists(PENDING):
            return 0
        by_cause, kept = {}, []
        for line in open(PENDING).read().splitlines(keepends=True):
            m = PENDING_ITEM.match(line.rstrip("\n"))
            if m and m.group(1).strip() in pages:
                c = CAUSE.search(m.group(2))
                c = c.group(1) if c else None
                if cause is None or c == cause:
                    by_cause.setdefault(c, []).append(m.group(1).strip())
                    continue
            kept.append(line)
        n = sum(len(v) for v in by_cause.values())
        if not n:
            return 0
        ledger = open(REVIEWED).read() if os.path.exists(REVIEWED) else LEDGER_HEADER
        if not ledger.endswith("\n"):
            ledger += "\n"
        for c in sorted(by_cause, key=lambda x: x or ""):
            plist = ", ".join(f"[[{p}]]" for p in dict.fromkeys(by_cause[c]))
            ledger += f"- {date} {outcome} (cause: {c or 'none'}) {plist} — {basis.strip()}\n"
        atomic_write(REVIEWED, ledger)
        text = "".join(kept)
        if not any(PENDING_ITEM.match(l) for l in text.splitlines()) and "*(no open items)*" not in text:
            text = text.rstrip("\n") + "\n\n*(no open items)*\n"
        atomic_write(PENDING, text)
        return n


def body_hash(text):
    """Hash of a page's body (frontmatter excluded): the revision id of its substantive content."""
    return hashlib.sha1(parse_frontmatter(text)[1].encode()).hexdigest()[:8]
