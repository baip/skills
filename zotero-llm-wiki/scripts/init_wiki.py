#!/usr/bin/env python3
"""Create a Zotero-backed LLM wiki from this skill's template, or upgrade the tools of an existing one.

New wiki:
  python3 init_wiki.py DEST --audience "TEXT" [--library user:12345] [--git inside|separate[:PATH]|none]
                       [--next "TEXT"] [--date YYYY-MM-DD] [--trailer "LINE" ...]

  - DEST must not exist yet, or be an empty directory.
  - --audience is one sentence describing the reader, used in the schema's writing-style rule
    (e.g. "a hydrologist who models groundwater flow and reads the field's primary literature").
  - --next is free text for the `next:` line of the first log entry (default: ask the user for a collection and a paper).
  - --library is the Zotero library id. Left out, it is read from the running Zotero (local API).
  - --git: inside (a normal .git folder, the default), separate[:PATH] (the git directory outside the wiki, for wikis
    in Google Drive, Dropbox, OneDrive or iCloud, which corrupt .git folders; PATH defaults to
    ~/.local/share/zotero-llm-wiki/<folder name>.git), or none.
  - --trailer adds a line to the end of the commit message (repeatable), e.g. the attribution line your host asks
    for ("Co-Authored-By: ..."), so the commit never needs amending. It applies to --upgrade-tools too.
  Everything is checked before anything is written; if setup still fails, the half-built DEST is removed.

Upgrade the tools of an existing wiki (pages and AGENTS.md are never touched):
  python3 init_wiki.py --upgrade-tools DEST

  Replaces the Python tools, runs the checks, appends a `fix` entry to log.md and, in a git repository, commits the
  changed tools and log.md (only if log.md had no uncommitted edits). Outside git, the previous tools are copied to a
  temp folder first. It prints the template's tools/README.md rows for the tools that changed, to compare by hand.

The skill must be installed (~/.claude/skills/zotero-llm-wiki, a link to it, or the folder named by
$ZOTERO_LLM_WIKI_SKILL), and this script must run from there: the wiki's rule is that tools are changed in the
installed skill and reach the wiki only through --upgrade-tools, and its linter compares tools/ with that copy.

Both modes run the bundled tool tests and the linter in DEST (strict for a new wiki; errors only for an upgrade,
so that open review items from unrelated work do not block it). Only the Python standard library is used.
Nothing is written to Zotero: the only Zotero access is one read of the local API for the library id.
"""
import argparse
import datetime
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), "assets", "wiki-template")
TOOLS = ["zot.py", "wikimeta.py", "wikilint.py", "review.py", "catalog.py", "relink.py", "test_tools.py"]
DIRS = ["sources", "concepts", "entities", "topics", "analyses", os.path.join("analyses", "assets")]
FILLED = ["AGENTS.md", "index.md", "log.md", os.path.join("tools", "README.md")]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
DEFAULT_INSTALL = os.path.join("~", ".claude", "skills", "zotero-llm-wiki")


def installed_skill():
    """The installed skill folder, or exit with install advice if this script is not running from it."""
    here = os.path.dirname(HERE)
    want = os.path.expanduser(os.environ.get("ZOTERO_LLM_WIKI_SKILL") or DEFAULT_INSTALL)
    if not os.path.isdir(want) or os.path.realpath(want) != os.path.realpath(here):
        sys.exit(f"This skill must be installed before it creates or upgrades a wiki, because the wiki's tools are\n"
                 f"maintained in the installed skill. Expected it at {want}, but this script runs from {here}.\n"
                 f"Install it there (e.g. ln -s \"{here}\" {DEFAULT_INSTALL}, or copy the folder), or set\n"
                 f"ZOTERO_LLM_WIKI_SKILL to the folder where it is installed, then run the installed copy.")
    home = os.path.expanduser("~")
    return "~" + want[len(home):] if want.startswith(home + os.sep) else want


def zotero_library():
    """'user:<id>' of the local Zotero library, read from the local API, or exit with advice."""
    try:
        with urllib.request.urlopen("http://localhost:23119/api/users/0/items/top?limit=1", timeout=10) as r:
            items = json.load(r)
    except OSError as e:
        sys.exit(f"Could not reach Zotero's local API ({e}). Start Zotero 7+ and enable Settings → Advanced → "
                 "'Allow other applications on this computer to communicate with Zotero', or pass --library user:<id> "
                 "(the number in https://www.zotero.org/settings/keys).")
    if not items:
        sys.exit("The Zotero library is empty, so its id cannot be read. Pass --library user:<id>.")
    lib = items[0]["library"]
    return f"{lib['type']}:{lib['id']}"


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=ENV)
    return p.returncode, (p.stdout + p.stderr).strip()


def check(dest, strict=True):
    """Run the tool tests and the linter (strict by default); return a list of (label, ok, summary)."""
    out = []
    code, text = run([sys.executable, "-I", "-B", os.path.join("tools", "test_tools.py")], dest)
    n_ok = sum(1 for l in text.splitlines() if l.startswith("ok "))
    out.append(("tool tests", code == 0, f"{n_ok} passed, {text.splitlines()[-1] if text else 'no output'}"))
    code, text = run([sys.executable, "-I", "-B", os.path.join("tools", "wikilint.py")] + (["--strict"] if strict else []), dest)
    out.append(("strict lint" if strict else "lint (errors only)", code == 0, text.splitlines()[0] if text else "no output"))
    return out


def plan_git(dest, mode):
    """Validate the git choice before anything is written. Returns (kind, gitdir or None)."""
    if mode in ("none", "inside"):
        if mode == "inside" and shutil.which("git") is None:
            sys.exit("git is not installed; install it or pass --git none.")
        return mode, None
    if mode == "separate" or mode.startswith("separate:"):
        if shutil.which("git") is None:
            sys.exit("git is not installed; install it or pass --git none.")
        path = mode.split(":", 1)[1] if ":" in mode else os.path.join(
            "~", ".local", "share", "zotero-llm-wiki", os.path.basename(dest.rstrip(os.sep)) + ".git")
        gitdir = os.path.abspath(os.path.expanduser(path))
        if os.path.exists(gitdir) and os.listdir(gitdir):
            sys.exit(f"{gitdir} exists and is not empty; choose a new path for the git directory.")
        if os.path.commonpath([gitdir, dest]) == dest:
            sys.exit(f"The git directory {gitdir} would be inside the wiki; choose a path outside it.")
        return "separate", gitdir
    sys.exit("--git must be inside, separate, separate:PATH or none")


def git_setup(dest, kind, gitdir):
    """Initialise revision history. Returns (description for the schema, details for tools/README.md)."""
    if kind == "none":
        return ("no revision history yet; propose setting up git before the first large ingest",
                "- Not set up yet. `git init` here, or `git init --separate-git-dir <path outside cloud sync>` if this folder\n"
                "  is synced by Google Drive, Dropbox, OneDrive or iCloud.")
    if kind == "inside":
        code, text = run(["git", "init", "-q"], dest)
        if code:
            raise RuntimeError(f"git init failed: {text}")
        return ("git repository in this folder", "- A normal git repository (`.git/` in this folder).")
    os.makedirs(os.path.dirname(gitdir), exist_ok=True)
    code, text = run(["git", "init", "-q", "--separate-git-dir", gitdir], dest)
    if code:
        raise RuntimeError(f"git init failed: {text}")
    run(["git", "config", "core.worktree", dest], dest)
    return (f"git directory `{gitdir}`, outside this folder, which is its work tree",
            f"- The git directory is `{gitdir}` (`git init --separate-git-dir`); this folder's `.git` is a one-line\n"
            f"  pointer file to it, so cloud sync copies only the pointer, never the object store. `core.worktree`\n"
            f"  points back here, so `git --git-dir {gitdir} …` works from anywhere. If this folder moves, run\n"
            f"  `git --git-dir {gitdir} config core.worktree <new path>`.\n"
            f"- On another machine the synced pointer leads nowhere, so git fails in this folder there. Do not replace the\n"
            f"  pointer on that machine: the sync service would copy the replacement back and break this machine's link.\n"
            f"  Edit there without git and commit from this machine (the edits then show up as pre-existing changes,\n"
            f"  AGENTS.md §2.10), or work in a clone outside the synced folder that never touches it. Never let the sync\n"
            f"  service create a real `.git/`.")


def create(a):
    skill_dir = installed_skill()
    dest = os.path.abspath(os.path.expanduser(a.dest))
    existed = os.path.exists(dest)
    if existed and (not os.path.isdir(dest) or os.listdir(dest)):
        sys.exit(f"{dest} exists and is not empty. Use --upgrade-tools to refresh the tools of an existing wiki.")
    library = a.library or zotero_library()
    if not re.fullmatch(r"(user|group):\d+", library):
        sys.exit(f"--library must look like user:12345 or group:12345, not {library!r}")
    kind, gitdir = plan_git(dest, a.git)
    audience = a.audience.strip().rstrip(".") + "."
    date = a.date or datetime.date.today().isoformat()
    try:
        shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True, copy_function=shutil.copyfile,  # fresh modes from the umask
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        os.replace(os.path.join(dest, "gitignore"), os.path.join(dest, ".gitignore"))  # shipped without the dot
        for d in DIRS:
            os.makedirs(os.path.join(dest, d), exist_ok=True)
        git_location, git_details = git_setup(dest, kind, gitdir)
        env = f"{platform.system()} {platform.release()}, Python {platform.python_version()}"
        values = {"{{LIBRARY}}": library, "{{AUDIENCE}}": audience, "{{DATE}}": date, "{{GIT_LOCATION}}": git_location,
                  "{{GIT_DETAILS}}": git_details, "{{ENVIRONMENT}}": env, "{{SKILL_DIR}}": skill_dir,
                  "{{NEXT}}": a.next or "ask the user for the first Zotero collection and paper, and ingest it in guided mode (AGENTS.md §8.2)."}
        for rel in FILLED:
            p = os.path.join(dest, rel)
            text = open(p, encoding="utf-8").read()
            for k, v in values.items():
                text = text.replace(k, v)
            left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", text)))
            if left:
                raise RuntimeError(f"unfilled placeholders in {rel}: {left}")
            open(p, "w", encoding="utf-8").write(text)
    except Exception as e:  # leave nothing half-built behind
        if existed:
            for name in os.listdir(dest):
                p = os.path.join(dest, name)
                shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
        else:
            shutil.rmtree(dest, ignore_errors=True)
        if gitdir and os.path.isdir(gitdir):
            shutil.rmtree(gitdir, ignore_errors=True)
        sys.exit(f"Setup failed and was rolled back: {e}")

    results = check(dest)
    print(f"Created {dest}")
    print(f"  library {library}; revision history: {git_location}")
    for label, ok, line in results:
        print(f"  {label}: {'OK' if ok else 'FAILED'} ({line})")
    if kind != "none" and all(ok for _, ok, _ in results):
        run(["git", "add", "-A"], dest)  # the brand-new wiki holds only files this script wrote
        code, text = run(["git", "commit", "-q", "-m", message("setup | Zotero-backed LLM wiki created", a)], dest)
        print("  initial commit: " + ("made" if code == 0 else f"not made ({text.splitlines()[-1] if text else 'git error'}); "
                                       "set user.name and user.email, then commit"))
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)


def message(subject, a):
    """A commit message: the subject, then any --trailer lines after a blank line."""
    return subject + ("\n\n" + "\n".join(a.trailer) if a.trailer else "")


def readme_rows(text):
    """Table rows of tools/README.md keyed by their first cell (a tool or a command, e.g. `zot.py` or `pdfpath KEY`)."""
    rows = {}
    for line in text.splitlines():
        m = re.match(r"^\| `([^`]+)`", line)
        if m:
            rows[m.group(1)] = line
    return rows


def upgrade(a):
    installed_skill()
    dest = os.path.abspath(os.path.expanduser(a.dest))
    tdir = os.path.join(dest, "tools")
    if not os.path.isfile(os.path.join(dest, "AGENTS.md")) or not os.path.isdir(tdir):
        sys.exit(f"{dest} does not look like a Zotero LLM wiki (no AGENTS.md or tools/).")
    in_git = run(["git", "rev-parse", "--is-inside-work-tree"], dest)[0] == 0 if shutil.which("git") else False
    changed = [n for n in TOOLS if not os.path.exists(os.path.join(tdir, n)) or
               open(os.path.join(TEMPLATE, "tools", n), "rb").read() != open(os.path.join(tdir, n), "rb").read()]
    if not changed:
        print(f"Tools in {tdir} are already current.")
        for label, ok, line in check(dest, strict=False):
            print(f"  {label}: {'OK' if ok else 'FAILED'} ({line})")
        return
    backup = None
    if not in_git:  # git keeps the old versions otherwise; never leave copies inside the wiki
        backup = tempfile.mkdtemp(prefix="wiki-tools-backup-")
        for n in changed:
            if os.path.exists(os.path.join(tdir, n)):
                shutil.copy2(os.path.join(tdir, n), backup)
    for n in changed:
        shutil.copyfile(os.path.join(TEMPLATE, "tools", n), os.path.join(tdir, n))
    shutil.rmtree(os.path.join(tdir, "__pycache__"), ignore_errors=True)
    print(f"Upgraded {len(changed)} tool(s): {', '.join(changed)}" + (f"; previous versions in {backup}" if backup else ""))
    results = check(dest, strict=False)
    for label, ok, line in results:
        print(f"  {label}: {'OK' if ok else 'FAILED'} ({line})")
    ok_all = all(ok for _, ok, _ in results)

    mine = readme_rows(open(os.path.join(tdir, "README.md"), encoding="utf-8").read()) \
        if os.path.exists(os.path.join(tdir, "README.md")) else {}
    tmpl = readme_rows(open(os.path.join(TEMPLATE, "tools", "README.md"), encoding="utf-8").read())
    differ = [k for k in tmpl if mine.get(k) != tmpl[k]]
    if differ:
        print("  tools/README.md table rows (tools and commands) that differ from the template; the README is yours, so")
        print("  show these to the user and update the rows they agree with:")
        for k in differ:
            print(f"    yours:    {mine.get(k, '(no row)')}\n    template: {tmpl[k]}")

    if not ok_all:
        print("  Checks failed: no log entry or commit was made. Fix the failure, or restore the previous tools.")
        sys.exit(1)
    log = os.path.join(dest, "log.md")
    log_dirty = in_git and bool(run(["git", "status", "--porcelain", "--", "log.md"], dest)[1])
    date = datetime.date.today().isoformat()
    entry = (f"\n## [{date}] fix | Tool upgrade from the zotero-llm-wiki skill\n"
             f"- ~ tools/{', tools/'.join(changed)} replaced with the skill's current versions; pages and AGENTS.md untouched.\n"
             f"- Checks after the upgrade: {results[0][2]}; {results[1][2]}.\n"
             + (f"- tools/README.md rows to compare with the template: {', '.join(differ)}.\n" if differ else ""))
    with open(log, "a", encoding="utf-8") as f:
        f.write(entry)
    print("  log.md: fix entry appended")
    if in_git and not log_dirty:
        paths = [os.path.join("tools", n) for n in changed] + ["log.md"]
        run(["git", "add", "--", *paths], dest)
        code, text = run(["git", "commit", "-q", "-m", message("fix | Tool upgrade from the zotero-llm-wiki skill", a),
                          "--", *paths], dest)
        print("  commit: " + ("made (tools and log.md only)" if code == 0 else f"not made ({text.splitlines()[-1] if text else 'git error'})"))
    elif in_git:
        print("  commit: not made, because log.md had uncommitted edits before the upgrade; commit the tools and the log entry by hand")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dest")
    p.add_argument("--upgrade-tools", action="store_true")
    p.add_argument("--audience")
    p.add_argument("--library")
    p.add_argument("--git", default="inside")
    p.add_argument("--next")
    p.add_argument("--date")
    p.add_argument("--trailer", action="append", default=[])
    a = p.parse_args()
    if a.upgrade_tools:
        upgrade(a)
    elif not a.audience:
        p.error("--audience is required for a new wiki")
    else:
        create(a)


if __name__ == "__main__":
    main()
