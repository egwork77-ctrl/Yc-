import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from faultdetect import diagnosis, predict
from faultdetect.live import Live
from faultdetect.sample import write_vrs_history, write_vrs_log


class VrsTest(unittest.TestCase):
    def test_predict(self):
        with tempfile.TemporaryDirectory() as d:
            h, l = Path(d) / "h.csv", Path(d) / "l.csv"
            write_vrs_history(h)
            write_vrs_log(l)
            r = {m["machine_id"]: m for m in predict.run(h, "vrs", l)}
        self.assertEqual(len(r), 6)
        parts = {p["part_id"]: p for p in r["VRS-5"]["parts"]}
        self.assertLess(parts["vrs_gantry"]["due_days"], 3)
        self.assertEqual(r["VRS-5"]["predictions"][3]["faults"][0]["name"], "橋架導軌 / 皮帶 / 馬達磨耗")
        self.assertEqual({p["part_id"]: p for p in r["VRS-2"]["parts"]}["vrs_light"]["status"], "order_now")

    def test_live_coord_offset(self):
        with tempfile.TemporaryDirectory() as d:
            live = Live(d, {}, lambda m: "vrs", lambda: datetime(2026, 1, 1, 9, 0))
            s = live.start("VRS-1")
            for _ in range(3):
                live.add_event(s["session_id"], "coord_offset")
            a = live.live(s["session_id"])["alerts"][0]
        self.assertEqual(a["suggestions"][0]["id"], "vrs_coord")
        self.assertTrue(a["suggestions"][0]["improve"])

    def test_every_event_maps_to_a_fault(self):
        from faultdetect import detector
        kb = diagnosis.load_kb(profile="vrs")
        syms = {s for f in kb for s in f["symptoms"]}
        for e in detector.load_config(profile="vrs")["events"]:
            if e["symptoms"]:
                self.assertTrue(set(e["symptoms"]) & syms, e["id"])


if __name__ == "__main__":
    unittest.main()
