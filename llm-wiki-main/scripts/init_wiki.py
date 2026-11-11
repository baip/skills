#!/usr/bin/env python3
"""Create an LLM wiki over the user's own project documents from this skill's template, or upgrade the tools of an
existing one.

New wiki:
  python3 init_wiki.py DEST --audience "TEXT" --raw-root PATH [--git inside|separate[:PATH]|worktree:REPO[:BRANCH]|none]
                       [--next "TEXT"] [--date YYYY-MM-DD] [--trailer "LINE" ...]

  - DEST must not exist yet, or be an empty directory.
  - --audience is one sentence describing the reader, used in the schema's writing-style rule
    (e.g. "a chemical engineering professor who writes NSF and DOE proposals on molecular simulation").
  - --raw-root is the folder that holds the documents (proposals, reports, presentations). The wiki reads it and
    never writes there. It is stored in tools/config.json, with ~ kept so the wiki moves between machines.
  - --next is free text for the `next:` line of the first log entry (default: ask the user what to ingest first).
  - --git: inside (a normal .git folder, the default), separate[:PATH] (the git directory outside the wiki, for wikis
    in Google Drive, Dropbox, OneDrive or iCloud, which corrupt .git folders; PATH defaults to
    ~/.local/share/llm-wiki-main/<folder name>.git), worktree:REPO[:BRANCH] (DEST becomes a linked worktree of the
    existing repository REPO, on a new branch with no history, named BRANCH or after DEST; the git data stays in REPO,
    which also suits synced folders), or none.
  - --trailer adds a line to the end of the commit message (repeatable), e.g. the attribution line your host asks
    for ("Co-Authored-By: ..."), so the commit never needs amending. It applies to --upgrade-tools too.
  Everything is checked before anything is written; if setup still fails, the half-built DEST is removed.

Upgrade the tools of an existing wiki (pages and AGENTS.md are never touched):
  python3 init_wiki.py --upgrade-tools DEST

  Replaces the Python tools, runs the checks, appends a `fix` entry to log.md and, in a git repository, commits the
  changed tools and log.md (only if log.md had no uncommitted edits). Outside git, the previous tools are copied to a
  temp folder first. It prints the template's tools/README.md rows for the tools that changed, to compare by hand.

The skill must be installed (~/.claude/skills/llm-wiki-main, a link to it, or the folder named by
$PROJECT_LLM_WIKI_SKILL), and this script must run from there: the wiki's rule is that tools are changed in the
installed skill and reach the wiki only through --upgrade-tools, and its linter compares tools/ with that copy.

Both modes run the bundled tool tests and the linter in DEST (strict for a new wiki; errors only for an upgrade,
so that open review items from unrelated work do not block it). Only the Python standard library is used.
Nothing is written to the raw root.
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

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), "assets", "wiki-template")
TOOLS = ["docs.py", "wikimeta.py", "wikilint.py", "review.py", "catalog.py", "relink.py", "search.py", "split.py", "test_tools.py"]
DIRS = ["sources", "projects", "concepts", "entities", "topics", "analyses", os.path.join("analyses", "assets")]
FILLED = ["AGENTS.md", "index.md", "log.md", os.path.join("tools", "README.md")]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
DEFAULT_INSTALL = os.path.join("~", ".claude", "skills", "llm-wiki-main")


def installed_skill():
    """The installed skill folder, or exit with install advice if this script is not running from it."""
    here = os.path.dirname(HERE)
    want = os.path.expanduser(os.environ.get("PROJECT_LLM_WIKI_SKILL") or DEFAULT_INSTALL)
    if not os.path.isdir(want) or os.path.realpath(want) != os.path.realpath(here):
        sys.exit(f"This skill must be installed before it creates or upgrades a wiki, because the wiki's tools are\n"
                 f"maintained in the installed skill. Expected it at {want}, but this script runs from {here}.\n"
                 f"Install it there (e.g. ln -s \"{here}\" {DEFAULT_INSTALL}, or copy the folder), or set\n"
                 f"PROJECT_LLM_WIKI_SKILL to the folder where it is installed, then run the installed copy.")
    home = os.path.expanduser("~")
    return "~" + want[len(home):] if want.startswith(home + os.sep) else want


def raw_root_arg(value):
    """(text for config.json and the schema, absolute path) of --raw-root, or exit. ~ is kept in the stored form."""
    path = os.path.realpath(os.path.expanduser(value))
    if not os.path.isdir(path):
        sys.exit(f"--raw-root {value} is not a folder (is the cloud drive mounted?).")
    home = os.path.expanduser("~")
    shown = value if value.startswith("~") else ("~" + os.path.abspath(value)[len(home):]
                                                  if os.path.abspath(value).startswith(home + os.sep) else os.path.abspath(value))
    return shown.replace(os.sep, "/") if os.name != "nt" else shown, path


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
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
            "~", ".local", "share", "llm-wiki-main", os.path.basename(dest.rstrip(os.sep)) + ".git")
        gitdir = os.path.abspath(os.path.expanduser(path))
        if os.path.exists(gitdir) and os.listdir(gitdir):
            sys.exit(f"{gitdir} exists and is not empty; choose a new path for the git directory.")
        if os.path.commonpath([gitdir, dest]) == dest:
            sys.exit(f"The git directory {gitdir} would be inside the wiki; choose a path outside it.")
        return "separate", gitdir
    if mode.startswith("worktree:"):
        if shutil.which("git") is None:
            sys.exit("git is not installed; install it or pass --git none.")
        rest = mode[len("worktree:"):]
        repo, _, branch = rest.partition(":") if not re.match(r"^[A-Za-z]:\\", rest) else (rest, "", "")
        repo = os.path.abspath(os.path.expanduser(repo))
        branch = branch or os.path.basename(dest.rstrip(os.sep))
        code, top = run(["git", "-C", repo, "rev-parse", "--git-common-dir"], repo if os.path.isdir(repo) else ".")
        if code:
            sys.exit(f"{repo} is not a git repository: {top}")
        if run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch], repo)[0] == 0:
            sys.exit(f"Branch {branch} already exists in {repo}; choose another with worktree:{repo}:<branch>.")
        if run(["git", "check-ref-format", "--branch", branch], repo)[0]:
            sys.exit(f"{branch!r} is not a valid branch name.")
        if run(["git", "-C", repo, "worktree", "add", "-h"], repo)[1].find("--orphan") < 0:
            sys.exit("This git is too old for orphan worktrees (git 2.42+ needed); upgrade git or use --git separate.")
        return "worktree", (repo, branch)
    sys.exit("--git must be inside, separate, separate:PATH, worktree:REPO[:BRANCH] or none")


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


def worktree_setup(dest, repo, branch):
    """Make DEST a linked worktree of REPO on a new orphan BRANCH (before any file is written into DEST)."""
    code, text = run(["git", "-C", repo, "worktree", "add", "-q", "--orphan", "-b", branch, dest], repo)
    if code:
        raise RuntimeError(f"git worktree add failed: {text}")
    return (f"branch `{branch}` of the repository `{repo}`, checked out here as a linked worktree",
            f"- This folder is a linked worktree of `{repo}` on branch `{branch}` (`git worktree add --orphan`). Its\n"
            f"  `.git` is a one-line pointer file; the object store stays in `{repo}`, outside any synced folder, and the\n"
            f"  other branches there are other wikis or tools, unrelated to this one.\n"
            f"- If this folder moves, run `git -C {repo} worktree repair <new path>`. On another machine the synced\n"
            f"  pointer leads nowhere: edit there without git and commit from this machine, or clone the branch outside\n"
            f"  the synced folder. Never let a sync service create a real `.git/` here.\n"
            f"- `git -C {repo} worktree list` shows every wiki that shares the repository.")


def create(a):
    skill_dir = installed_skill()
    dest = os.path.abspath(os.path.expanduser(a.dest))
    existed = os.path.exists(dest)
    if existed and (not os.path.isdir(dest) or os.listdir(dest)):
        sys.exit(f"{dest} exists and is not empty. Use --upgrade-tools to refresh the tools of an existing wiki.")
    raw_shown, raw_path = raw_root_arg(a.raw_root)
    if os.path.commonpath([raw_path, os.path.realpath(dest) if existed else os.path.abspath(dest)]) == raw_path:
        sys.exit(f"The wiki {dest} would be inside the raw root {raw_path}, which the wiki never writes to; choose a folder outside it.")
    kind, gitdir = plan_git(dest, a.git)
    audience = a.audience.strip().rstrip(".") + "."
    date = a.date or datetime.date.today().isoformat()
    try:
        if kind == "worktree":
            git_location, git_details = worktree_setup(dest, *gitdir)
        shutil.copytree(TEMPLATE, dest, dirs_exist_ok=True, copy_function=shutil.copyfile,  # fresh modes from the umask
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        os.replace(os.path.join(dest, "gitignore"), os.path.join(dest, ".gitignore"))  # shipped without the dot
        os.replace(os.path.join(dest, "gitattributes"), os.path.join(dest, ".gitattributes"))
        with open(os.path.join(dest, "tools", "config.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"raw_root": raw_shown}, f, indent=2)
            f.write("\n")
        for d in DIRS:
            os.makedirs(os.path.join(dest, d), exist_ok=True)
        if kind != "worktree":
            git_location, git_details = git_setup(dest, kind, gitdir)
        env = f"{platform.system()} {platform.release()}, Python {platform.python_version()}"
        values = {"{{RAW_ROOT}}": raw_shown, "{{AUDIENCE}}": audience, "{{DATE}}": date, "{{GIT_LOCATION}}": git_location,
                  "{{GIT_DETAILS}}": git_details, "{{ENVIRONMENT}}": env, "{{SKILL_DIR}}": skill_dir,
                  "{{NEXT}}": a.next or "ask the user which documents to ingest first (a project folder or a few files), and ingest one in guided mode (AGENTS.md §8.2)."}
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
        if kind == "worktree":
            run(["git", "-C", gitdir[0], "worktree", "remove", "--force", dest], gitdir[0])
            run(["git", "-C", gitdir[0], "worktree", "prune"], gitdir[0])
            run(["git", "-C", gitdir[0], "branch", "-D", gitdir[1]], gitdir[0])
        if existed:
            for name in os.listdir(dest):
                p = os.path.join(dest, name)
                shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
        else:
            shutil.rmtree(dest, ignore_errors=True)
        if kind == "separate" and gitdir and os.path.isdir(gitdir):
            shutil.rmtree(gitdir, ignore_errors=True)
        sys.exit(f"Setup failed and was rolled back: {e}")

    results = check(dest)
    print(f"Created {dest}")
    print(f"  raw root {raw_shown} (read only); revision history: {git_location}")
    for label, ok, line in results:
        print(f"  {label}: {'OK' if ok else 'FAILED'} ({line})")
    if kind != "none" and all(ok for _, ok, _ in results):
        run(["git", "add", "-A"], dest)  # the brand-new wiki holds only files this script wrote
        code, text = run(["git", "commit", "-q", "-m", message("setup | Project-document LLM wiki created", a)], dest)
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
        sys.exit(f"{dest} does not look like a project-document LLM wiki (no AGENTS.md or tools/).")
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
    entry = (f"\n## [{date}] fix | Tool upgrade from the llm-wiki-main skill\n"
             f"- ~ tools/{', tools/'.join(changed)} replaced with the skill's current versions; pages and AGENTS.md untouched.\n"
             f"- Checks after the upgrade: {results[0][2]}; {results[1][2]}.\n"
             + (f"- tools/README.md rows to compare with the template: {', '.join(differ)}.\n" if differ else ""))
    with open(log, "a", encoding="utf-8") as f:
        f.write(entry)
    print("  log.md: fix entry appended")
    if in_git and not log_dirty:
        paths = [os.path.join("tools", n) for n in changed] + ["log.md"]
        run(["git", "add", "--", *paths], dest)
        code, text = run(["git", "commit", "-q", "-m", message("fix | Tool upgrade from the llm-wiki-main skill", a),
                          "--", *paths], dest)
        print("  commit: " + ("made (tools and log.md only)" if code == 0 else f"not made ({text.splitlines()[-1] if text else 'git error'})"))
    elif in_git:
        print("  commit: not made, because log.md had uncommitted edits before the upgrade; commit the tools and the log entry by hand")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dest")
    p.add_argument("--upgrade-tools", action="store_true")
    p.add_argument("--audience")
    p.add_argument("--raw-root")
    p.add_argument("--git", default="inside")
    p.add_argument("--next")
    p.add_argument("--date")
    p.add_argument("--trailer", action="append", default=[])
    a = p.parse_args()
    if a.upgrade_tools:
        upgrade(a)
    elif not a.audience or not a.raw_root:
        p.error("--audience and --raw-root are required for a new wiki")
    else:
        create(a)


if __name__ == "__main__":
    main()
