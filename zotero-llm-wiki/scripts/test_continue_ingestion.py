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
            rows[1]["payload"]["rate_limits"]["primary"]["used_percent"] = 70
            (day / "rollout-x.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            self.assertEqual(ci.codex_limit(0, Path(d)), (False, None))


FAKE = r'''#!/bin/sh
# fake agent: the script in $PLAN lists one action per run (commit, limit, dirty, idle)
n=$(cat "$STATE" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$STATE"
act=$(sed -n "${n}p" "$PLAN")
case "$act" in
  commit) echo $n > page$n.md; git add page$n.md; git commit -qm "phase $n"; echo "committed";;
  limit) echo "You've hit your usage limit. Try again in 0h 0m";;
  dirty) echo x > stray.md; echo "left a file";;
  *) echo "nothing pending";;
esac
'''


class Loop(unittest.TestCase):
    def run_plan(self, plan, *extra):
        with tempfile.TemporaryDirectory() as d:
            wiki, aux = Path(d, "wiki"), Path(d, "aux"); wiki.mkdir(); aux.mkdir()
            for c in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                      ["commit", "-q", "--allow-empty", "-m", "start"]):
                subprocess.run(["git", "-C", str(wiki), *c], check=True)
            (aux / "agent.sh").write_text(FAKE); os.chmod(aux / "agent.sh", 0o755)
            (aux / "plan").write_text("\n".join(plan) + "\n")
            env = {"CONTINUE_INGESTION_CMD": str(aux / "agent.sh"), "PLAN": str(aux / "plan"),
                   "STATE": str(aux / "state"), "CONTINUE_INGESTION_QUIET": "1"}
            old = {k: os.environ.get(k) for k in env}; os.environ.update(env)
            try:
                ci.main([str(wiki), "--agent", "custom", "--reset-margin", "0", "--log-dir", str(aux / "log"), *extra])
            finally:
                for k, v in old.items():
                    os.environ.pop(k) if v is None else os.environ.__setitem__(k, v)
            commits = int(subprocess.run(["git", "-C", str(wiki), "rev-list", "--count", "HEAD"],
                                         capture_output=True, text=True).stdout) - 1
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

    def test_max_phases(self):
        commits, log = self.run_plan(["commit"] * 5, "--max-phases", "3")
        self.assertEqual(commits, 3)


if __name__ == "__main__":
    unittest.main()
