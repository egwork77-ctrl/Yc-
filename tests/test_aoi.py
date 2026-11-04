import io
import tempfile
import unittest
from pathlib import Path

from faultdetect import aoi, detector, engine
from faultdetect.sample import write_aoi_results, write_aoi_sensors

HEADER = "timestamp,machine_id,board_id,result,defect_type,component,verdict\n"


def ids(report, mid):
    return [d["id"] for m in report if m["machine_id"] == mid for d in m["diagnosis"]]


class AoiResultsTest(unittest.TestCase):
    def setUp(self):
        self.cfg = detector.load_config(profile="aoi")

    def test_detect_results_csv(self):
        rows = detector.read_rows(io.StringIO(HEADER + "t,A,B1,PASS,,,\n"))
        self.assertTrue(aoi.is_results(rows))

    def test_false_call_rate(self):
        lines = [f"t,A,B{i},NG,shift,C1,{'false' if i < 8 else 'real'}" for i in range(10)]
        rows = detector.read_rows(io.StringIO(HEADER + "\n".join(lines)))
        symptoms = [f.symptom for f in aoi.analyze_results(rows, self.cfg)["A"]]
        self.assertIn("false_call_high", symptoms)
        self.assertIn("false_call_concentrated", symptoms)

    def test_fiducial_fail(self):
        lines = [f"t,A,B{i},{'NG,fiducial,,false' if i < 5 else 'PASS,,,'}" for i in range(100)]
        rows = detector.read_rows(io.StringIO(HEADER + "\n".join(lines)))
        symptoms = [f.symptom for f in aoi.analyze_results(rows, self.cfg)["A"]]
        self.assertIn("fiducial_fail_high", symptoms)

    def test_sample_results(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.csv"
            write_aoi_results(p)
            report = engine.run(p)
        status = {m["machine_id"]: m["status"] for m in report}
        self.assertEqual(status["AOI1"], "ok")
        self.assertEqual(ids(report, "AOI2")[0], "program_too_strict")
        self.assertEqual(ids(report, "AOI3")[0], "stencil_clog")


class AoiSensorsTest(unittest.TestCase):
    def test_sample_sensors(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.csv"
            write_aoi_sensors(p)
            report = engine.run(p, profile="aoi")
        status = {m["machine_id"]: m["status"] for m in report}
        self.assertEqual(status["AOI1"], "ok")
        self.assertEqual(ids(report, "AOI2")[0], "light_aging")
        self.assertEqual(ids(report, "AOI3")[0], "lens_dirty")


if __name__ == "__main__":
    unittest.main()
