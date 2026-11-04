import tempfile
import unittest
from pathlib import Path

from faultdetect import detector, diagnosis, predict
from faultdetect.sample import write_f22_history, write_f22_log


class Fusion22Test(unittest.TestCase):
    def test_inherits_discovery8(self):
        cfg = detector.load_config(profile="fusion22")
        self.assertIn("vacuum_kpa", cfg["sensors"])          # 繼承
        self.assertIn("light_ch2", cfg["sensors"])           # 新增
        self.assertNotIn("lamp_intensity", cfg["sensors"])   # null 移除
        ids = [f["id"] for f in diagnosis.load_kb(profile="fusion22")]
        self.assertIn("vacuum_leak", ids)
        self.assertIn("light_channel", ids)
        self.assertNotIn("lamp_aging", ids)

    def test_predict(self):
        with tempfile.TemporaryDirectory() as d:
            h, l = Path(d) / "h.csv", Path(d) / "l.csv"
            write_f22_history(h)
            write_f22_log(l)
            r = {m["machine_id"]: m for m in predict.run(h, "fusion22", l)}
        ch2 = next(p for p in r["FUS22-1"]["predictions"] if p["sensor"] == "light_ch2")
        self.assertEqual(ch2["faults"][0]["name"], "照明光源衰減(多影像其中一組)")
        stage = next(p for p in r["FUS22-2"]["predictions"] if p["sensor"] == "stage_error_um")
        self.assertLess(stage["due_days"], 7)


if __name__ == "__main__":
    unittest.main()
