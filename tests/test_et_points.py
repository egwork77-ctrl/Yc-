import tempfile
import unittest
from pathlib import Path

from faultdetect import engine
from faultdetect.sample import write_et_points


class EtPointsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pts.csv"
            write_et_points(p)
            cls.r = {m["machine_id"]: m for m in engine.run(p)}

    def symptoms(self, mid):
        return {f["symptom"] for f in self.r[mid]["findings"]}

    def test_fixture_problem_found_on_both_machines(self):
        for mid in ("ET1", "ET6"):
            self.assertIn("fixture_wide", self.symptoms(mid))
            self.assertEqual(self.r[mid]["diagnosis"][0]["id"], "et_fixture")
        msg = next(f["message"] for f in self.r["ET1"]["findings"] if f["symptom"] == "repeat_pin")
        self.assertIn("P-0456", msg)

    def test_machine_problem_on_et5(self):
        self.assertTrue({"machine_wide", "region_edge"} <= self.symptoms("ET5"))
        self.assertEqual(self.r["ET5"]["diagnosis"][0]["id"], "et_machine_align")


if __name__ == "__main__":
    unittest.main()
