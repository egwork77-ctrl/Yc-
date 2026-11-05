import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from faultdetect.live import Live, LogWatcher

META = {"machines": [{"id": "DIS8-1", "profile": "discovery8"}, {"id": "FUS22-1", "profile": "fusion22"}]}


class FakeClock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, 8, 0)

    def __call__(self):
        return self.t


def profile_of(mid):
    return next(m["profile"] for m in META["machines"] if m["id"] == mid)


class LiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.live = Live(self.tmp.name, META, profile_of, self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def tick(self, minutes):
        self.clock.t += timedelta(minutes=minutes)

    def test_alert_after_repeats_with_suggestions(self):
        s = self.live.start("DIS8-1", "小王")
        for _ in range(2):
            self.live.add_event(s["session_id"], "board_not_held")
            self.tick(5)
        self.assertEqual(self.live.live(s["session_id"])["alerts"], [])
        self.live.add_event(s["session_id"], "board_not_held")
        d = self.live.live(s["session_id"])
        self.assertEqual(d["alerts"][0]["count"], 3)
        top = d["alerts"][0]["suggestions"][0]
        self.assertEqual(top["id"], "vacuum_leak")
        self.assertTrue(top["improve"])

    def test_window_expires(self):
        s = self.live.start("DIS8-1")
        for _ in range(3):
            self.live.add_event(s["session_id"], "image_blur")
            self.tick(20)
        self.assertEqual(self.live.live(s["session_id"])["alerts"], [])   # 40 分鐘內才 3 次,超過 30 分鐘視窗

    def test_machine_stop_alerts_once(self):
        s = self.live.start("FUS22-1")
        self.live.add_event(s["session_id"], "machine_stop")
        self.assertEqual(len(self.live.live(s["session_id"])["alerts"]), 1)

    def test_resume_and_report(self):
        s = self.live.start("DIS8-1")
        self.assertEqual(self.live.start("DIS8-1")["session_id"], s["session_id"])  # 進行中場次可接續
        self.live.add_event(s["session_id"], "note", "幫浦有異音")
        self.live.add_event(s["session_id"], "board_not_held")
        self.tick(90)
        r = self.live.end(s["session_id"], "下班前更換密封條")
        self.assertEqual(r["duration_min"], 90)
        self.assertEqual(r["session"]["note"], "下班前更換密封條")
        self.assertEqual(r["overall"][0]["id"], "vacuum_leak")
        with self.assertRaises(ValueError):
            self.live.add_event(s["session_id"], "board_not_held")

    def test_overall_ranked_by_event_count(self):
        s = self.live.start("DIS8-1")
        for _ in range(3):
            self.live.add_event(s["session_id"], "board_not_held")
        self.live.add_event(s["session_id"], "registration_fail")
        self.assertEqual(self.live.live(s["session_id"])["overall"][0]["id"], "vacuum_leak")

    def test_unknown_event_rejected(self):
        s = self.live.start("DIS8-1")
        with self.assertRaises(ValueError):
            self.live.add_event(s["session_id"], "nope")

    def test_log_watcher(self):
        log = Path(self.tmp.name) / "machine.log"
        log.write_text("old line Registration failed\n", encoding="utf-8")
        machines = [{"id": "DIS8-1", "profile": "discovery8", "live_log": {
            "path": str(log), "patterns": [{"regex": "registration fail", "event": "registration_fail"}]}}]
        w = LogWatcher(self.live, machines)
        s = self.live.start("DIS8-1")
        w.poll_once()                                    # 第一次從檔尾開始,不重讀舊資料
        with open(log, "a", encoding="utf-8") as f:
            f.write("10:01 Registration FAILED on panel 12\n10:02 ok\n")
        w.poll_once()
        ev = self.live.live(s["session_id"])["events"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["source"], "log")
        self.assertIn("panel 12", ev[0]["note"])


if __name__ == "__main__":
    unittest.main()
