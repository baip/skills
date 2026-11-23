"""Tests for continue_ingestion.py (no network, no real agent): python3 -I test_continue_ingestion.py"""
import datetime as dt, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continue_ingestion as ci

EST = dt.timezone(dt.timedelta(hours=-5))


class ResetText(unittest.TestCase):
    now = dt.datetime(2026, 11, 3, 1, 31, tzinfo=EST)

    def at(self, text):
        e = ci.parse_reset_text(text, self.now)
        return None if e is None else dt.datetime.fromtimestamp(e, EST)

    def test_clock_times(self):
        self.assertEqual(self.at("You've hit your limit · resets 2am").hour, 2)
        self.assertEqual(self.at("limit reached, resets 6:40pm").strftime("%H:%M"), "18:40")
        self.assertEqual(self.at("resets 1am").date(), dt.date(2026, 11, 4))      # already past today
        self.assertEqual(self.at("Try again at 12:15 AM").strftime("%d %H:%M"), "04 00:15")

    def test_zone_and_epoch_and_duration(self):
        t = self.at("resets 7am (America/Chicago)")
        self.assertEqual(t.astimezone(dt.timezone(dt.timedelta(hours=-6))).hour, 7)
        self.assertEqual(ci.parse_reset_text("Claude AI usage limit reached|1793700000", self.now), 1793700000)
        self.assertEqual(self.at("try again in 2 hours 5 minutes"), self.now + dt.timedelta(hours=2, minutes=5))
        self.assertIsNone(self.at("you have reached the end of the queue"))


class Outputs(unittest.TestCase):
    def test_codex(self):
        out = "\n".join(json.dumps(e) for e in [
            {"type": "thread.started", "thread_id": "abc"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "phase done"}},
            {"type": "turn.failed", "error": {"message": "You've hit your usage limit"}}])
        self.assertEqual(ci.parse_output("codex", out), ("abc", "phase done", "You've hit your usage limit"))

    def test_claude(self):
        out = json.dumps({"type": "result", "session_id": "s1", "result": "hit your limit · resets 2am",
                          "is_error": True, "api_error_status": 429})
        sid, final, err = ci.parse_output("claude", out)
        self.assertEqual((sid, final), ("s1", "hit your limit · resets 2am"))
        self.assertIn("429", err)

    def test_codex_limit_reading(self):
        with tempfile.TemporaryDirectory() as d:
            day = Path(d, "2026/11/04"); day.mkdir(parents=True)
            rows = [{"timestamp": "2026-11-04T10:00:00Z", "payload": {"type": "token_count", "rate_limits": {
                        "primary": {"used_percent": 40, "resets_at": 1}, "secondary": {"used_percent": 50, "resets_at": 2}}}},
                    {"timestamp": "2026-11-04T11:00:00Z", "payload": {"type": "token_count", "rate_limits": {
                        "primary": {"used_percent": 100, "resets_at": 1793800000}, "secondary": {"used_percent": 60}}}}]
            (day / "rollout-x.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            self.assertEqual(ci.codex_limit(0, Path(d)), (True, 1793800000))
            tie = dict(rows[1]); tie["payload"] = {"type": "token_count", "rate_limits": {
                "primary": {"used_percent": 97, "resets_at": 1793800000}, "secondary": {"used_percent": 60}}}
            (day / "rollout-y.jsonl").write_text(json.dumps(tie))     # same second, lower percentage
            self.assertEqual(ci.codex_limit(0, Path(d)), (True, 1793800000))
            (day / "rollout-y.jsonl").unlink()
            rows[1]["payload"]["rate_limits"]["primary"]["used_percent"] = 92
            (day / "rollout-x.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            self.assertEqual(ci.codex_limit(0, Path(d)), (False, None))
            self.assertEqual(ci.codex_limit(0, Path(d), threshold=90), (True, 1793800000))


FAKE = r'''#!/bin/sh
# fake agent: the script in $PLAN lists one action per run (commit, limit, dirty, idle)
n=$(cat "$STATE" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$STATE"; echo "$*" >> "$STATE.prompts"
act=$(sed -n "${n}p" "$PLAN")
case "$act" in
  commit) echo $n > page$n.md; git add -A; git commit -qm "phase $n"; echo "committed";;
  limit) echo "You've hit your usage limit. Try again in 0h 0m";;
  interrupt) echo '{"type":"thread.started","thread_id":"T9"}'; sleep 0.2; kill -INT $PPID; sleep 1;;
  credits) echo x > stray.md; echo "Your workspace is out of credits. Add credits to continue.";;
  dirty) echo x > stray.md; echo "left a file";;
  *) echo "nothing pending";;
esac
'''


LOG = """2026-11-20T10:00:00 run 1: new session (codex, open-file limit 61440)
2026-11-20T10:00:01 session A1
2026-11-20T11:00:00 phase committed: abc1234 Read batch 7
\u2713 Done! Embedded 453 chunks from 44 documents in 22s
2026-11-20T11:00:30 after-phase 'qmd embed': ok
2026-11-20T11:00:31 run 2: new session (claude, open-file limit 61440)
2026-11-20T11:00:31 session B2
2026-11-20T12:00:00 usage limit: waiting until Fri 13:00, then resuming
2026-11-20T13:00:00 run 3: resume B2 (claude, open-file limit 61440)
2026-11-20T13:00:00 session B2
2026-11-20T13:30:00 stopped: uncommitted changes after run 3 (4 paths). Uncommitted work belongs to session B2
"""


class LastIncomplete(unittest.TestCase):
    def test_finds_newest_uncommitted_session(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "loop.log")
            self.assertIsNone(ci.last_incomplete(f))                  # no log yet
            f.write_text(LOG)
            self.assertEqual(ci.last_incomplete(f), ("B2", "claude", "2026-11-20T13:00:00"))
            f.write_text(LOG + "2026-11-20T14:00:00 phase committed: def5678 Integrate batch 7\n")
            self.assertIsNone(ci.last_incomplete(f))
            f.write_text(LOG.split("2026-11-20T11:00:31")[0])
            self.assertIsNone(ci.last_incomplete(f))


class Locks(unittest.TestCase):
    def test_one_loop_per_worktree(self):
        with tempfile.TemporaryDirectory() as d:
            main, other = Path(d, "main"), Path(d, "other"); main.mkdir()
            for c in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                      ["commit", "-q", "--allow-empty", "-m", "start"], ["worktree", "add", "-q", "-b", "o", str(other)]):
                subprocess.run(["git", "-C", str(main), *c], check=True)
            a, b = ci.lock_path(main), ci.lock_path(other)
            self.assertNotEqual(a, b)
            ci.acquire_lock(a)
            ci.acquire_lock(b)                     # a loop in another worktree of the same repository may start
            with self.assertRaises(SystemExit):
                ci.acquire_lock(a)                 # a second loop in the same worktree may not
            a.unlink(); b.unlink()


class OpenFiles(unittest.TestCase):
    def test_raises_soft_limit(self):
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (256, hard))
            self.assertGreaterEqual(ci.raise_open_file_limit(), 4096)
        finally:
            resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


class Loop(unittest.TestCase):
    def run_plan(self, plan, *extra, seed_log=None):
        with tempfile.TemporaryDirectory() as d:
            wiki, aux = Path(d, "wiki"), Path(d, "aux"); wiki.mkdir(); aux.mkdir()
            for c in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                      ["commit", "-q", "--allow-empty", "-m", "start"]):
                subprocess.run(["git", "-C", str(wiki), *c], check=True)
            (aux / "agent.sh").write_text(FAKE); os.chmod(aux / "agent.sh", 0o755)
            if plan and plan[0] == "dirty-start":
                (wiki / "pending.md").write_text("x"); plan = plan[1:]
            (aux / "plan").write_text("\n".join(plan) + "\n")
            if seed_log:
                (aux / "log").mkdir(); (aux / "log/loop.log").write_text(seed_log)
            env = {"CONTINUE_INGESTION_CMD": str(aux / "agent.sh"), "PLAN": str(aux / "plan"),
                   "STATE": str(aux / "state"), "CONTINUE_INGESTION_QUIET": "1"}
            old = {k: os.environ.get(k) for k in env}; os.environ.update(env)
            try:
                agent = [] if "--continue" in extra else ["--agent", "custom"]
                ci.main([str(wiki), *agent, "--reset-margin", "0", "--log-dir", str(aux / "log"), *extra])
            finally:
                for k, v in old.items():
                    os.environ.pop(k) if v is None else os.environ.__setitem__(k, v)
            commits = int(subprocess.run(["git", "-C", str(wiki), "rev-list", "--count", "HEAD"],
                                         capture_output=True, text=True).stdout) - 1
            self.prompts = (aux / "state.prompts").read_text().splitlines()
            return commits, (aux / "log/loop.log").read_text()

    def test_commits_until_idle(self):
        commits, log = self.run_plan(["commit", "commit", "idle"])
        self.assertEqual(commits, 2)
        self.assertIn("no new commit and no usage limit: nothing pending", log)

    def test_limit_waits_then_continues(self):
        commits, log = self.run_plan(["commit", "limit", "commit", "idle"])
        self.assertEqual(commits, 2)
        self.assertIn("usage limit: waiting until", log)

    def test_repeated_limits_stop(self):
        commits, log = self.run_plan(["limit", "limit", "limit", "commit"])
        self.assertEqual(commits, 0)
        self.assertIn("after 2 waits", log)

    def test_dirty_stops(self):
        commits, log = self.run_plan(["commit", "dirty", "commit"])
        self.assertEqual(commits, 1)
        self.assertIn("uncommitted changes", log)

    def test_after_phase(self):
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d, "hook")
            commits, log = self.run_plan(["commit", "commit", "idle"], "--after-phase", f"echo x >> {marker}",
                                         "--after-phase", "false")
            self.assertEqual(marker.read_text().count("x"), 2)
        self.assertEqual(commits, 2)
        self.assertIn("failed with 1, continuing", log)

    def test_after_phase_dirty_stops(self):
        commits, log = self.run_plan(["commit", "commit"], "--after-phase", "echo x > stray.md")
        self.assertEqual(commits, 1)
        self.assertIn("--after-phase command left uncommitted changes", log)

    def test_out_of_credits_stops(self):
        commits, log = self.run_plan(["commit", "credits", "commit"])
        self.assertEqual(commits, 1)
        self.assertIn("stopped: out of credits", log)

    def test_resume_allows_dirty_start(self):
        commits, log = self.run_plan(["dirty-start", "commit", "idle"], "--resume", "S1")
        self.assertEqual(commits, 1)

    def test_continue_resumes_last_session(self):
        seed = LOG.replace("(claude,", "(custom,")
        commits, log = self.run_plan(["dirty-start", "commit", "idle"], "--continue", seed_log=seed)
        self.assertEqual(commits, 1)
        self.assertIn("run 1: resume B2 (custom", log.split("stopped: uncommitted")[1])

    def test_continue_checks_agent_and_log(self):
        with self.assertRaises(SystemExit) as e:
            self.run_plan(["commit"], "--continue", "--agent", "codex", seed_log=LOG)
        self.assertIn("ran with --agent claude", str(e.exception))
        with self.assertRaises(SystemExit) as e:
            self.run_plan(["commit"], "--continue", seed_log=LOG.split("2026-11-20T11:00:31")[0])
        self.assertIn("nothing to continue", str(e.exception))
        with self.assertRaises(SystemExit):
            ci.main([".", "--continue", "--resume", "S1"])

    def test_ctrl_c_logs_session(self):
        commits, log = self.run_plan(["commit", "interrupt", "commit"])
        self.assertEqual(commits, 1)
        self.assertIn("session T9", log)
        self.assertIn("stopped: interrupted (Ctrl-C)", log)

    def test_start_prompt_only_first(self):
        commits, log = self.run_plan(["limit", "commit", "commit", "idle"], "--start", "Ingest the collection X")
        self.assertEqual(commits, 2)
        self.assertEqual(self.prompts, ["Ingest the collection X"] + ["Continue ingestion"] * 3)
        self.assertIn("prompt 'Ingest the collection X'", log)

    def test_start_with_resume_refused(self):
        with self.assertRaises(SystemExit):
            ci.main([".", "--start", "x", "--resume", "S1"])

    def test_max_phases(self):
        commits, log = self.run_plan(["commit"] * 5, "--max-phases", "3")
        self.assertEqual(commits, 3)


if __name__ == "__main__":
    unittest.main()
