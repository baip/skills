#!/usr/bin/env python3
"""Run "Continue ingestion" sessions back to back, one batch phase per session, without a person at the keyboard.

  python3 continue_ingestion.py WIKI --agent codex|claude [--max-phases N] [--max-wait-hours H]
  python3 continue_ingestion.py WIKI --stop        # end the loop after the current phase

Each run starts a fresh headless session (`codex exec`, `claude -p`) with the prompt "Continue ingestion" in WIKI. The
wiki's schema makes every phase end with a commit, so a new commit means the phase finished and the next one starts.
A run without a new commit is classified:

  - usage limit: wait until the limit resets (Codex logs the reset time with every model call, Claude Code prints it in
    its final message), then resume the same session with the same prompt. If the reset is more than --max-wait-hours
    away (a weekly limit), stop. At most 2 waits in a row without a commit.
  - anything else (nothing pending, the agent asked a question, a check failed, an error): stop and notify.

The loop also stops when a phase leaves uncommitted changes (the schema asks the user before committing someone else's
work), when the agent exits with an error, after --max-phases commits, or when `--stop` was run. A lock file in the
repository's common git directory keeps two loops from running in worktrees of one repository at once. It does not see
interactive sessions: do not work in the same repository while the loop runs.

Raw output of every run goes to ~/.cache/continue-ingestion/<wiki folder>/, with a summary in loop.log.
Identical copies live in the zotero-llm-wiki, project-llm-wiki and zotero-wiki-chatgpt skills: change all three.
"""
import argparse, datetime as dt, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

PROMPT = "Continue ingestion"
CODEX_APP = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
LIMIT_WORDS = re.compile(r"usage limit|rate limit|limit reached|hit your limit|limit.{0,40}reset", re.I)


def git(wiki, *args):
    return subprocess.run(["git", "-C", str(wiki), *args], capture_output=True, text=True, check=True).stdout.strip()


def git_path(wiki, flag):
    p = Path(git(wiki, "rev-parse", flag))
    return p if p.is_absolute() else (Path(wiki) / p).resolve()


def notify(msg):
    print(msg, flush=True)
    if sys.platform == "darwin" and not os.environ.get("CONTINUE_INGESTION_QUIET"):
        subprocess.run(["osascript", "-e", f"display notification {json.dumps(msg[:200])} with title \"Continue ingestion\""],
                       capture_output=True)


# ---- reset times ----------------------------------------------------------------------------------------------

def parse_reset_text(text, now):
    """Epoch seconds of the reset named in a limit message, or None. `now` is an aware datetime."""
    m = re.search(r"\|(\d{10})\b", text)
    if m:
        return int(m.group(1))
    m = re.search(r"\bin\s+(?:(\d+)\s*h(?:ours?)?)?\s*(?:(\d+)\s*m(?:in(?:utes?)?)?)?", text, re.I)
    if m and (m.group(1) or m.group(2)):
        return int(now.timestamp()) + 3600 * int(m.group(1) or 0) + 60 * int(m.group(2) or 0)
    m = re.search(r"(?:resets?|try again)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?(?:\s*\(([\w+-]+/[\w+/-]+)\))?",
                  text, re.I)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower().replace(".", "")
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    local = now
    if m.group(4):
        try:
            from zoneinfo import ZoneInfo
            local = now.astimezone(ZoneInfo(m.group(4)))
        except Exception:
            pass
    t = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if t <= local:
        t += dt.timedelta(days=1)
    return int(t.timestamp())


def codex_limit(since, sessions=Path.home() / ".codex/sessions", threshold=99.0):
    """(exhausted, reset epoch) from the newest rate-limit reading in Codex logs written since `since` (epoch)."""
    newest = None
    for day in sorted(sessions.glob("*/*/*")):
        try:
            if day.stat().st_mtime < since - 86400:
                continue
        except OSError:
            continue
        for f in day.glob("rollout-*.jsonl"):
            if f.stat().st_mtime < since:
                continue
            with open(f, errors="replace") as fh:
                for line in fh:
                    if '"rate_limits"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                        r = d["payload"]["rate_limits"]
                    except (ValueError, KeyError, TypeError):
                        continue
                    if r and (newest is None or d.get("timestamp", "") > newest[0]):
                        newest = (d.get("timestamp", ""), r)
    if newest is None:
        return False, None
    resets = [w.get("resets_at") for w in (newest[1].get("primary"), newest[1].get("secondary"))
              if w and (w.get("used_percent") or 0) >= threshold]
    resets = [r for r in resets if r]
    return bool(resets), (max(resets) if resets else None)


# ---- agents ---------------------------------------------------------------------------------------------------

def codex_bin():
    return os.environ.get("CODEX_BIN") or shutil.which("codex") or CODEX_APP


def command(agent, wiki, session, prompt):
    if agent == "codex":
        if session:
            return [codex_bin(), "exec", "resume", "--json", "-c", 'approvals_reviewer="auto_review"',
                    "-c", 'sandbox_mode="workspace-write"', session, prompt]
        return [codex_bin(), "exec", "--json", "--cd", str(wiki), "--approve-for-me", prompt]
    if agent == "claude":
        cmd = [os.environ.get("CLAUDE_BIN") or "claude", "-p", prompt, "--output-format", "json", "--permission-mode", "auto"]
        return cmd + (["--resume", session] if session else [])
    return os.environ["CONTINUE_INGESTION_CMD"].split() + [prompt]   # agent "custom": tests and other agents


def parse_output(agent, out):
    """(session id, final message, error text) from an agent's stdout."""
    session, final, errors = None, "", []
    if agent == "codex":
        for line in out.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "thread.started":
                session = e.get("thread_id")
            item = e.get("item") or {}
            if item.get("type") == "agent_message":
                final = item.get("text", "")
            err = e.get("error") or (e if e.get("type") == "error" else None)
            if err:
                errors.append(err.get("message", "") if isinstance(err, dict) else str(err))
    elif agent == "claude":
        try:
            d = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
        except ValueError:
            d = {}
        session, final = d.get("session_id"), d.get("result") or ""
        if d.get("is_error") or d.get("api_error_status"):
            errors.append(f"{d.get('api_error_status') or ''} {final}".strip())
    else:
        final = out.strip().splitlines()[-1] if out.strip() else ""
    return session, final, " | ".join(x for x in errors if x)


# ---- loop -----------------------------------------------------------------------------------------------------

def acquire_lock(path):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            pid = int(path.read_text().strip())
            os.kill(pid, 0)
            sys.exit(f"another loop (pid {pid}) holds {path}")
        except (ValueError, ProcessLookupError):
            path.unlink()          # stale lock of a loop that died
            return acquire_lock(path)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)


def sleep_until(epoch, stop_file):
    while time.time() < epoch:
        if stop_file.exists():
            return False
        time.sleep(min(60, max(1, epoch - time.time())))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("wiki", type=Path)
    ap.add_argument("--agent", choices=["codex", "claude", "custom"], default="codex")
    ap.add_argument("--max-phases", type=int, default=20, help="stop after this many committed phases")
    ap.add_argument("--max-wait-hours", type=float, default=6, help="stop instead of waiting longer for a reset")
    ap.add_argument("--fallback-wait-hours", type=float, default=5, help="wait when a limit's reset time is unknown")
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--reset-margin", type=int, default=120, help="seconds to wait past a reset")
    ap.add_argument("--log-dir", type=Path)
    ap.add_argument("--stop", action="store_true", help="ask a running loop to stop after its current phase")
    a = ap.parse_args(argv)
    wiki = a.wiki.expanduser().resolve()
    stop_file = git_path(wiki, "--git-dir") / "continue-ingestion.stop"
    if a.stop:
        stop_file.write_text(dt.datetime.now().isoformat())
        print(f"stop requested: {stop_file}")
        return 0
    if stop_file.exists():
        stop_file.unlink()
    if git(wiki, "status", "--porcelain"):
        sys.exit("the wiki has uncommitted changes: commit or resolve them first (AGENTS.md, pre-existing changes)")
    lock = git_path(wiki, "--git-common-dir") / "continue-ingestion.lock"
    acquire_lock(lock)
    log_dir = (a.log_dir or Path.home() / ".cache/continue-ingestion" / wiki.name).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    def log(msg):
        line = f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}"
        print(line, flush=True)
        with open(log_dir / "loop.log", "a") as fh:
            fh.write(line + "\n")

    phases = waits = runs = 0
    session = None
    reason = ""
    try:
        while phases < a.max_phases:
            if stop_file.exists():
                reason = "stop requested"
                break
            before, start = git(wiki, "rev-parse", "HEAD"), time.time()
            runs += 1
            cmd = command(a.agent, wiki, session, a.prompt)
            log(f"run {runs}: {'resume ' + session if session else 'new session'} ({a.agent})")
            out_path = log_dir / f"{dt.datetime.now():%Y%m%d-%H%M%S}-run{runs}.out"
            with open(out_path, "w") as fh:
                proc = subprocess.run(cmd, cwd=wiki, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT)
            out = out_path.read_text(errors="replace")
            sid, final, error = parse_output(a.agent, out)
            session_used, session = session, None
            after, dirty = git(wiki, "rev-parse", "HEAD"), git(wiki, "status", "--porcelain")

            limited, reset = False, None
            if after == before:
                if a.agent == "codex":
                    limited, reset = codex_limit(start)
                text = f"{error} {final}"
                if not limited and LIMIT_WORDS.search(text):
                    limited = True
                if limited and reset is None:
                    reset = parse_reset_text(text, dt.datetime.now().astimezone())
            if after != before and not dirty:
                phases, waits = phases + 1, 0
                log(f"phase committed: {git(wiki, 'log', '-1', '--format=%h %s')}")
                continue
            if limited:
                waits += 1
                if waits > 2:
                    reason = "usage limit again after 2 waits without a commit"
                    break
                if reset is None:
                    reset = int(time.time() + 3600 * a.fallback_wait_hours)
                    log(f"usage limit, reset time unknown: waiting {a.fallback_wait_hours} h")
                if reset - time.time() > 3600 * a.max_wait_hours:
                    reason = f"usage limit resets {dt.datetime.fromtimestamp(reset):%a %H:%M}, beyond --max-wait-hours"
                    break
                log(f"usage limit: waiting until {dt.datetime.fromtimestamp(reset + a.reset_margin):%a %H:%M}, then resuming")
                if not sleep_until(reset + a.reset_margin, stop_file):
                    reason = "stop requested while waiting"
                    break
                session = sid or session_used if a.agent != "custom" else None
                continue
            if dirty:
                reason = f"uncommitted changes after run {runs} ({len(dirty.splitlines())} paths)"
            elif proc.returncode:
                reason = f"agent exited with {proc.returncode}: {error or final}"[:300]
            else:
                reason = f"no new commit and no usage limit: {final}"[:300]
            break
        else:
            reason = f"{phases} phases committed (--max-phases)"
    finally:
        lock.unlink(missing_ok=True)
    log(f"stopped: {reason}")
    notify(f"{wiki.name}: stopped after {phases} phases. {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
