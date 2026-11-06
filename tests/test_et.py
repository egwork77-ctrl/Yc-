import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from faultdetect import detector, diagnosis, predict
from faultdetect.live import Live
from faultdetect.sample import write_et_history, write_et_log


class EtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        h, l = Path(self.tmp.name) / "h.csv", Path(self.tmp.name) / "l.csv"
        write_et_history(h)
        write_et_log(l)
        self.r = {m["machine_id"]: m for m in predict.run(h, "et_precise", l)}

    def tearDown(self):
        self.tmp.cleanup()

    def test_pin_wear_detected(self):
        pins = {p["part_id"]: p for p in self.r["ET1"]["parts"]}["et_pins"]
        self.assertLessEqual(pins["due_days"], 3)

    def test_falling_air_pressure(self):
        air = next(p for p in self.r["ET5"]["predictions"] if p["sensor"] == "air_pressure")
        self.assertEqual(air["faults"][0]["name"], "壓合壓力不足 / 氣壓異常")

    def test_external_calibration_overdue(self):
        cal = next(s for s in self.r["ET3"]["schedule"] if s["item"] == "外部校正(ATT)")
        self.assertEqual(cal["level"], "overdue")

    def test_pin_mark_event_suggests_alignment(self):
        live = Live(self.tmp.name, {}, lambda m: "et_precise", lambda: datetime(2026, 1, 1, 9))
        s = live.start("ET2")
        for _ in range(3):
            live.add_event(s["session_id"], "fixture_offset")
        sug = live.live(s["session_id"])["alerts"][0]["suggestions"][0]
        self.assertEqual(sug["id"], "et_alignment")
        self.assertIn("PAD", "".join(sug["steps"]))

    def test_every_event_maps_to_a_fault(self):
        syms = {s for f in diagnosis.load_kb(profile="et_precise") for s in f["symptoms"]}
        for e in detector.load_config(profile="et_precise")["events"]:
            if e["symptoms"]:
                self.assertTrue(set(e["symptoms"]) & syms, e["id"])


if __name__ == "__main__":
    unittest.main()
