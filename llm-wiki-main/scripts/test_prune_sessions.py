"""Tests for prune_sessions.py on fake Codex and Claude Code homes (no real agent): python3 -I test_prune_sessions.py

Identical copies live in the llm-wiki-zotero, llm-wiki-main and llm-wiki-zotero-chatgpt skills: change all three.
"""
import contextlib, io, json, os, sqlite3, sys, tempfile, time, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prune_sessions as ps

OLD = time.time() - 3 * 86400


class Prune(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.wiki, self.other = t / "wiki", t / "elsewhere"
        self.wiki.mkdir()
        self.other.mkdir()
        self.codex, self.claude = t / "codex", t / "claude"
        self.log = t / "deleted.txt"
        fake = t / "codex-bin"
        fake.write_text(f"#!/bin/sh\necho \"$3\" >> '{self.log}'\n")
        fake.chmod(0o755)
        self.env = {"CODEX_HOME": str(self.codex), "CLAUDE_CONFIG_DIR": str(self.claude), "CODEX_BIN": str(fake)}
        self.saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.make_codex()
        self.make_claude()

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def make_codex(self):
        rollouts = self.codex / "sessions"
        rollouts.mkdir(parents=True)
        db = sqlite3.connect(self.codex / "state_5.sqlite")
        db.execute("create table threads (id text, rollout_path text, updated_at int, source text, cwd text, "
                   "first_user_message text)")
        db.execute("create table thread_spawn_edges (parent_thread_id text, child_thread_id text)")

        def thread(tid, source, cwd, msg, updated, parent=None):
            p = rollouts / f"rollout-{tid}.jsonl"
            p.write_text(json.dumps({"type": "session_meta", "payload": {"id": tid, "parent_thread_id": parent}}) + "\n")
            db.execute("insert into threads values (?,?,?,?,?,?)", (tid, str(p), int(updated), source, str(cwd), msg))

        thread("loop", "exec", self.wiki, "Continue ingestion", OLD)                 # old loop session
        thread("reader", '{"subagent":{"thread_spawn":{}}}', self.wiki, "", OLD)
        db.execute("insert into thread_spawn_edges values ('loop', 'reader')")
        thread("guard", '{"subagent":{"other":"guardian"}}', self.wiki, "", OLD, parent="loop")
        thread("fresh", "exec", self.wiki, "Continue ingestion", OLD)                # loop whose subagent is recent
        thread("fresh-r", '{"subagent":{"thread_spawn":{}}}', self.wiki, "", time.time())
        db.execute("insert into thread_spawn_edges values ('fresh', 'fresh-r')")
        thread("tui", "cli", self.wiki, "Continue ingestion", OLD)                   # interactive
        thread("ask", "exec", self.wiki, "What is in this wiki?", OLD)               # other prompt
        thread("away", "exec", self.other, "Continue ingestion", OLD)                # other folder
        db.commit()
        db.close()

    def make_claude(self):
        proj = self.claude / "projects" / "-wiki"
        proj.mkdir(parents=True)

        def session(sid, entry, cwd, prompt, mtime, subagent=True):
            t = proj / f"{sid}.jsonl"
            t.write_text(json.dumps({"type": "user", "entrypoint": entry, "cwd": str(cwd),
                                     "message": {"role": "user", "content": prompt}}) + "\n")
            files = [t]
            if subagent:
                s = proj / sid / "subagents" / "agent-a.jsonl"
                s.parent.mkdir(parents=True)
                s.write_text("{}\n")
                files.append(s)
            for d in ("file-history", "session-env"):
                (self.claude / d / sid).mkdir(parents=True)
            for f in files:
                os.utime(f, (mtime, mtime))

        session("c-loop", "sdk-cli", self.wiki, "Continue ingestion, but use 2 subagents", OLD)
        session("c-start", "sdk-cli", self.wiki / "sub", "Ingest the Zotero collection X", OLD, subagent=False)
        session("c-new", "sdk-cli", self.wiki, "Continue ingestion", time.time())
        session("c-tui", "cli", self.wiki, "Continue ingestion", OLD)
        session("c-away", "sdk-cli", self.other, "Continue ingestion", OLD)

    def run_prune(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ps.main([str(self.wiki), *args])
        return code, out.getvalue()

    def test_dry_run_selects_only_old_headless_loop_sessions(self):
        code, out = self.run_prune("-v")
        self.assertEqual(code, 0)
        self.assertIn("Total: 3 loop sessions", out)
        self.assertIn("Kept 2 recent", out)
        for sid in ("loop", "c-loop", "c-start"):
            self.assertIn(f" {sid} ", out)
        for sid in ("fresh", "tui", "ask", "away", "c-new", "c-tui", "c-away"):
            self.assertNotIn(f" {sid} ", out)
        self.assertFalse(self.log.exists())
        self.assertTrue((self.claude / "projects" / "-wiki" / "c-loop.jsonl").exists())

    def test_delete(self):
        code, _ = self.run_prune("--delete")
        self.assertEqual(code, 0)
        self.assertEqual(self.log.read_text().split(), ["reader", "guard", "loop"])    # children first
        proj = self.claude / "projects" / "-wiki"
        for sid in ("c-loop", "c-start"):
            self.assertFalse((proj / f"{sid}.jsonl").exists())
            self.assertFalse((proj / sid).exists())
            self.assertFalse((self.claude / "file-history" / sid).exists())
            self.assertFalse((self.claude / "session-env" / sid).exists())
        for sid in ("c-new", "c-tui", "c-away"):
            self.assertTrue((proj / f"{sid}.jsonl").exists())
            self.assertTrue((self.claude / "session-env" / sid).exists())

    def test_agent_filter(self):
        _, out = self.run_prune("--agent", "claude", "-v")
        self.assertIn("Total: 2 loop sessions", out)
        self.assertNotIn("codex", out)


if __name__ == "__main__":
    unittest.main()
