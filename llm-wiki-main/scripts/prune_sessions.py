#!/usr/bin/env python3
"""List or delete the agent sessions that continue_ingestion.py started in a wiki, once they are old.

  python3 prune_sessions.py WIKI [WIKI ...]                 # dry run: loop sessions idle for over 24 hours
  python3 prune_sessions.py WIKI --agent claude --hours 48  # one agent only, a different age
  python3 prune_sessions.py WIKI --delete                   # delete them

A session is selected only if all of these hold:
  - it ran headless, as the loop runs it (`codex exec`, `claude -p`), never an interactive or app session,
  - its folder is one of the WIKI folders or inside one,
  - its first prompt starts with "Continue ingestion" or "Ingest " (the loop's prompt or its --start request),
  - neither it nor any of its subagents has written anything within --hours. Keep --hours above the loop's
    --max-wait-hours (default 6): a loop waiting for a usage limit to reset resumes the same session.

Codex: the session, its subagents and its auto-review threads are deleted with `codex delete --force`, children first.
The script reads ~/.codex/state_5.sqlite (or $CODEX_HOME) and the first line of each auto-review rollout.

Claude Code has no command to delete one session (`claude purge` deletes a whole project). The script deletes the
session's files under ~/.claude (or $CLAUDE_CONFIG_DIR): projects/<project>/<session>.jsonl, the projects/<project>/
<session>/ folder (subagents, tool results), and file-history/, session-env/ and tasks/ entries named after it.

Identical copies live in the llm-wiki-zotero, llm-wiki-main and llm-wiki-zotero-chatgpt skills: change all three.
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

CODEX_APP = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
PROMPTS = ("Continue ingestion", "Ingest ")


def is_loop_prompt(msg):
    return (msg or "").strip().startswith(PROMPTS)


def files_under(paths):
    for p in map(Path, paths):
        if p.is_dir():
            yield from (f for f in p.rglob("*") if f.is_file())
        elif p.exists():
            yield p


def size_of(paths):
    return sum(f.stat().st_size for f in files_under(paths))


def newest_mtime(paths):
    return max((f.stat().st_mtime for f in files_under(paths)), default=0)


class Session:
    def __init__(self, agent, sid, cwd, last, threads, paths, delete_ids=()):
        self.agent, self.sid, self.cwd, self.last = agent, sid, cwd, last
        self.threads, self.paths, self.delete_ids = threads, list(paths), list(delete_ids)


# ---------- Codex ----------

def first_line(path):
    p = Path(path)
    try:
        if p.exists():
            with open(p, "rb") as f:
                return f.readline()
        z = Path(str(p) + ".zst")
        if z.exists():
            from compression import zstd   # Python 3.14+
            with zstd.open(z, "rb") as f:
                return f.readline()
    except (OSError, ImportError):
        pass
    return b""


def guardian_parent(path):
    try:
        return json.loads(first_line(path) or b"{}").get("payload", {}).get("parent_thread_id")
    except ValueError:
        return None


def codex_sessions(in_wiki):
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    dbp = home / "state_5.sqlite"
    if not dbp.exists():
        return []
    db = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    rows = db.execute("select id, rollout_path, updated_at, source, cwd, first_user_message from threads").fetchall()
    info = {r[0]: r for r in rows}
    children = {}
    for parent, child in db.execute("select parent_thread_id, child_thread_id from thread_spawn_edges"):
        children.setdefault(parent, []).append(child)
    for tid, path, _, source, *_ in rows:
        if '"guardian"' in source:
            parent = guardian_parent(path)
            if parent:
                children.setdefault(parent, []).append(tid)
    db.close()

    def tree(tid):        # children before parents
        out = []
        for c in children.get(tid, []):
            if c in info:
                out += tree(c)
        return out + [tid]

    out = []
    for tid, _, _, source, cwd, msg in rows:
        if source != "exec" or not in_wiki(cwd) or not is_loop_prompt(msg):
            continue
        ids = tree(tid)
        paths = [p for i in ids for p in (info[i][1], info[i][1] + ".zst") if Path(p).exists()]
        out.append(Session("codex", tid, cwd, max(info[i][2] for i in ids), len(ids), paths, ids))
    return out


def codex_delete(s):
    codex = os.environ.get("CODEX_BIN") or shutil.which("codex") or CODEX_APP
    failed = 0
    for i in s.delete_ids:
        r = subprocess.run([codex, "delete", "--force", i], capture_output=True, text=True)
        if r.returncode:
            failed += 1
            print(f"failed {i}: {(r.stderr or r.stdout).strip()[:200]}", file=sys.stderr)
    return failed


# ---------- Claude Code ----------

def claude_first_prompt(path):
    """(entrypoint, cwd, first prompt) from the head of a transcript; entrypoint is "sdk-cli" for `claude -p`."""
    try:
        with open(path, errors="replace") as f:
            for n, line in enumerate(f):
                if n > 200:
                    break
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") != "user" or d.get("isMeta"):
                    continue
                c = (d.get("message") or {}).get("content")
                if isinstance(c, list):
                    c = next((x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"), "")
                return d.get("entrypoint"), d.get("cwd") or "", c if isinstance(c, str) else ""
    except OSError:
        pass
    return None, "", ""


def claude_sessions(in_wiki):
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    out = []
    for t in glob.glob(str(home / "projects" / "*" / "*.jsonl")):
        entry, cwd, prompt = claude_first_prompt(t)
        if entry != "sdk-cli" or not in_wiki(cwd) or not is_loop_prompt(prompt):
            continue
        sid, folder = Path(t).stem, t[:-len(".jsonl")]
        paths = [t, folder] + [str(home / d / sid) for d in ("file-history", "session-env", "tasks")]
        paths = [p for p in paths if Path(p).exists()]
        threads = 1 + len(glob.glob(os.path.join(folder, "subagents", "*.jsonl")))
        out.append(Session("claude", sid, cwd, newest_mtime([t, folder]), threads, paths))
    return out


def claude_delete(s):
    failed = 0
    for p in s.paths:
        try:
            shutil.rmtree(p) if Path(p).is_dir() else os.remove(p)
        except OSError as e:
            failed += 1
            print(f"failed {p}: {e}", file=sys.stderr)
    return failed


# ---------- main ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wiki", nargs="+", help="wiki folder whose loop sessions to prune")
    ap.add_argument("--agent", choices=["codex", "claude", "all"], default="all")
    ap.add_argument("--hours", type=float, default=24, help="minimum idle time (default: %(default)s)")
    ap.add_argument("--delete", action="store_true", help="delete; without it, only list what would be deleted")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every session, not only the totals")
    a = ap.parse_args(argv)

    roots = [os.path.realpath(os.path.expanduser(w)) for w in a.wiki]

    def in_wiki(cwd):
        if not cwd:
            return False
        cwd = os.path.realpath(cwd)
        return any(cwd == r or cwd.startswith(r + os.sep) for r in roots)

    found = []
    if a.agent in ("codex", "all"):
        found += codex_sessions(in_wiki)
    if a.agent in ("claude", "all"):
        found += claude_sessions(in_wiki)
    cutoff = time.time() - a.hours * 3600
    selected = sorted((s for s in found if s.last < cutoff), key=lambda s: s.last)

    groups = {}
    for s in selected:
        g = groups.setdefault((s.agent, os.path.realpath(s.cwd)), [0, 0, 0])
        g[0] += 1
        g[1] += s.threads
        g[2] += size_of(s.paths)
    for (agent, w), (n, m, b) in sorted(groups.items()):
        print(f"{agent:6s} {n:5d} sessions {m:6d} threads {b / 1e9:6.2f} GB  {w}")
    print(f"Total: {len(selected)} loop sessions idle over {a.hours:g} h, "
          f"{sum(g[2] for g in groups.values()) / 1e9:.2f} GB. Kept {len(found) - len(selected)} recent loop sessions.")
    if a.verbose:
        for s in selected:
            t = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.last))
            print(f"  {s.agent:6s} {s.sid}  last write {t}  {s.threads:4d} threads  {s.cwd}")
    if not a.delete:
        print("Dry run. Add --delete to delete them.")
        return 0

    failed = 0
    for n, s in enumerate(selected, 1):
        failed += codex_delete(s) if s.agent == "codex" else claude_delete(s)
        if n % 20 == 0:
            print(f"  {n}/{len(selected)} sessions done", flush=True)
    print(f"Deleted {len(selected)} sessions, {failed} items failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
