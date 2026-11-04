import io
import tempfile
import unittest
from pathlib import Path

from faultdetect import detector, diagnosis
from faultdetect.sample import write_sample


class DetectorTest(unittest.TestCase):
    def setUp(self):
        self.cfg = detector.load_config()

    def test_threshold_alarm(self):
        f = detector.analyze_sensor("M", "vibration", [2, 2, 8], self.cfg)
        self.assertIn(("vibration_high", "alarm"), [(x.symptom, x.level) for x in f])

    def test_low_threshold(self):
        f = detector.analyze_sensor("M", "pressure", [6, 5, 3.5], self.cfg)
        self.assertIn(("pressure_low", "warn"), [(x.symptom, x.level) for x in f])

    def test_rising_trend(self):
        f = detector.analyze_sensor("M", "temperature", [50 + i for i in range(10)], self.cfg)
        self.assertIn("temperature_rising", [x.symptom for x in f])

    def test_missing_values(self):
        f = detector.analyze_sensor("M", "rpm", [None, None, 1450], self.cfg)
        self.assertIn("sensor_missing", [x.symptom for x in f])

    def test_normal_no_findings(self):
        f = detector.analyze_sensor("M", "temperature", [55, 55.2, 54.9, 55.1, 55], self.cfg)
        self.assertEqual(f, [])

    def test_load_csv_stream(self):
        data = detector.load_csv(io.StringIO("machine_id,temperature\nA,50\nA,\nB,60\n"))
        self.assertEqual(data["A"]["temperature"], [50.0, None])
        self.assertEqual(data["B"]["temperature"], [60.0])


class DiagnosisTest(unittest.TestCase):
    def test_pressure_leak(self):
        self.assertEqual(diagnosis.diagnose(["pressure_low"])[0]["id"], "pressure_leak")

    def test_unknown_symptom(self):
        self.assertEqual(diagnosis.diagnose(["foo"]), [])

    def test_sample_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.csv"
            write_sample(p)
            report = {m["machine_id"]: m for m in
                      diagnosis.build_report(detector.analyze(detector.load_csv(p)))}
        self.assertEqual(report["M01"]["status"], "ok")
        self.assertEqual(report["M02"]["status"], "alarm")
        ids = lambda m: [d["id"] for d in report[m]["diagnosis"]]
        self.assertIn("bearing_wear", ids("M02"))
        self.assertEqual(ids("M03")[0], "cooling_failure")
        self.assertEqual(ids("M04")[0], "pressure_leak")


if __name__ == "__main__":
    unittest.main()
