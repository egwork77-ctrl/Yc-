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
        vac = next(p for p in r["D83"]["predictions"] if p["sensor"] == "vacuum_kpa")
        self.assertLess(vac["due_days"], 7)
        self.assertEqual(vac["faults"][0]["name"], "平台真空不足(板翹、失焦)")
        lamp = next(s for s in r["D85"]["schedule"] if s["item"] == "照明燈管更換")
        self.assertTrue(0 < lamp["due_days"] < 14)
        self.assertGreaterEqual(r["D88"]["health"], 90)

    def test_results(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.csv"
            write_d8_results(p)
            report = {m["machine_id"]: m for m in engine.run(p, "discovery8")}
        self.assertEqual(report["D83"]["status"], "ok")
        self.assertEqual(report["D85"]["diagnosis"][0]["id"], "artwork_defect")
        self.assertEqual(report["D88"]["diagnosis"][0]["id"], "under_etch")


if __name__ == "__main__":
    unittest.main()


class PartsTest(unittest.TestCase):
    def test_parts_and_spares(self):
        import io
        with tempfile.TemporaryDirectory() as d:
            h, l = Path(d) / "h.csv", Path(d) / "l.csv"
            write_d8_history(h)
            write_d8_log(l)
            spares = io.StringIO("machine_id,part_id,part_no,stock,lead_days\n*,lamp,P-1,0,14\nD83,vacuum_pump,P-2,1,21\n")
            r = {m["machine_id"]: m for m in predict.run(h, "discovery8", l, spares_source=spares)}
        parts = {p["part_id"]: p for p in r["D85"]["parts"]}
        lamp = parts["lamp"]
        self.assertEqual(lamp["status"], "order_now")          # 6 天內壞、交期 14 天、無庫存
        self.assertEqual(lamp["part_no"], "P-1")
        vac = {p["part_id"]: p for p in r["D83"]["parts"]}["vacuum_pump"]
        self.assertEqual(vac["status"], "stocked")
        self.assertLess(vac["due_days"], 7)
