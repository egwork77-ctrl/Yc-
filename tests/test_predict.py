import io
import tempfile
import unittest
from pathlib import Path

from faultdetect import predict
from faultdetect.sample import write_aoi_history, write_maintenance_log


def history(values, sensor="light_intensity", hours=6):
    lines = ["timestamp,machine_id," + sensor]
    for i, v in enumerate(values):
        h = i * hours
        lines.append(f"2026-01-{1 + h // 24:02d}T{h % 24:02d}:00,A,{v}")
    return io.StringIO("\n".join(lines))


class PredictTest(unittest.TestCase):
    def test_eta_linear_decline(self):
        # 每天 -1,從 95 開始 → 10 天後 85(warn)
        vals = [95 - i * 0.25 for i in range(41)]  # 10 天
        p = predict.run(history(vals))[0]["predictions"][0]
        self.assertAlmostEqual(p["slope_per_day"], -1.0, places=2)
        self.assertAlmostEqual(p["eta"]["warn"], 0.0, places=1)
        self.assertEqual(p["level"], "overdue")

    def test_eta_future(self):
        vals = [100 - i * 0.25 for i in range(21)]  # 5 天後現值 95, 每天 -1
        p = predict.run(history(vals))[0]["predictions"][0]
        self.assertAlmostEqual(p["eta"]["warn"], 10.0, places=1)
        self.assertAlmostEqual(p["eta"]["alarm"], 20.0, places=1)
        self.assertEqual(p["level"], "warn")  # 10 天內 (soon_days=14)

    def test_stable_no_eta(self):
        vals = [97, 97.2, 96.9, 97.1, 97, 96.8, 97.2, 97]
        p = predict.run(history(vals))[0]["predictions"][0]
        self.assertEqual(p["eta"], {})
        self.assertEqual(p["level"], "ok")

    def test_schedule_by_hours(self):
        csv = io.StringIO("timestamp,machine_id,run_hours\n2026-01-01T00:00,A,1000\n2026-01-11T00:00,A,1200\n")
        log = io.StringIO("date,machine_id,item,run_hours\n2026-01-01,A,XY 軸線軌 / 導螺桿潤滑,0\n")
        s = {x["item"]: x for x in predict.run(csv, "aoi", log)[0]["schedule"]}
        lube = s["XY 軸線軌 / 導螺桿潤滑"]
        # 已用 1200h,剩 800h,每天 20h → 40 天
        self.assertAlmostEqual(lube["due_days"], 40.0, places=1)

    def test_missing_log_flagged(self):
        r = predict.run(history([97] * 8))[0]
        self.assertTrue(all(x["last"] is None for x in r["schedule"]))

    def test_sample(self):
        with tempfile.TemporaryDirectory() as d:
            h, l = Path(d) / "h.csv", Path(d) / "l.csv"
            write_aoi_history(h)
            write_maintenance_log(l)
            report = {m["machine_id"]: m for m in predict.run(h, "aoi", l)}
        self.assertEqual(report["AOI1"]["health"], 100)
        light = next(p for p in report["AOI2"]["predictions"] if p["sensor"] == "light_intensity")
        self.assertLess(light["due_days"], 7)
        focus = next(p for p in report["AOI3"]["predictions"] if p["sensor"] == "focus_score")
        self.assertTrue(10 < focus["due_days"] < 30)


if __name__ == "__main__":
    unittest.main()
