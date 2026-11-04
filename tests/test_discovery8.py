import tempfile
import unittest
from pathlib import Path

from faultdetect import engine, predict
from faultdetect.sample import write_d8_history, write_d8_log, write_d8_results


class Discovery8Test(unittest.TestCase):
    def test_predict(self):
        with tempfile.TemporaryDirectory() as d:
            h, l = Path(d) / "h.csv", Path(d) / "l.csv"
            write_d8_history(h)
            write_d8_log(l)
            r = {m["machine_id"]: m for m in predict.run(h, "discovery8", l)}
        vac = next(p for p in r["DIS8-1"]["predictions"] if p["sensor"] == "vacuum_kpa")
        self.assertLess(vac["due_days"], 7)
        self.assertEqual(vac["faults"][0]["name"], "平台真空不足(板翹、失焦)")
        lamp = next(s for s in r["DIS8-2"]["schedule"] if s["item"] == "照明燈管更換")
        self.assertTrue(0 < lamp["due_days"] < 14)
        self.assertGreaterEqual(r["DIS8-3"]["health"], 90)

    def test_results(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.csv"
            write_d8_results(p)
            report = {m["machine_id"]: m for m in engine.run(p, "discovery8")}
        self.assertEqual(report["DIS8-1"]["status"], "ok")
        self.assertEqual(report["DIS8-2"]["diagnosis"][0]["id"], "artwork_defect")
        self.assertEqual(report["DIS8-3"]["diagnosis"][0]["id"], "under_etch")


if __name__ == "__main__":
    unittest.main()
