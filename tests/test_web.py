import json
import shutil
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from faultdetect.web import App, make_handler

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class WebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        for f in ("machines.json", "d8_history.csv", "d8_maintenance_log.csv",
                  "f22_history.csv", "f22_maintenance_log.csv", "spares.csv"):
            shutil.copy(SAMPLES / f, cls.tmp)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(cls.tmp)))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp)

    def get(self, path):
        return json.load(urllib.request.urlopen(self.base + path))

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode())
        return json.load(urllib.request.urlopen(req))

    def test_overview_five_machines(self):
        ov = self.get("/api/overview")
        self.assertEqual([m["machine_id"] for m in ov["machines"]],
                         ["DIS8-1", "DIS8-2", "DIS8-3", "FUS22-1", "FUS22-2"])
        self.assertEqual(ov["errors"], [])
        self.assertTrue(ov["contacts"])

    def test_faults(self):
        ids = [f["id"] for f in self.get("/api/faults?profile=fusion22")]
        self.assertIn("light_channel", ids)

    def test_repair_roundtrip(self):
        self.post("/api/repairs", {"machine_id": "DIS8-1", "fault_id": "vacuum_leak",
                                   "fault_name": "平台真空不足", "result": "未解決", "note": "幫浦異音"})
        rs = self.get("/api/repairs")
        self.assertEqual(rs[0]["note"], "幫浦異音")
        self.assertTrue(rs[0]["time"])

    def test_inspection_appends_and_warns(self):
        r = self.post("/api/inspection", {"machine_id": "DIS8-3",
                                          "values": {"vacuum_kpa": "55", "air_pressure": "6.1", "bogus": "1"}})
        self.assertTrue(any("平台真空" in w for w in r["warnings"]))
        self.assertNotIn("bogus", r["saved"])
        form = self.get("/api/form?machine_id=DIS8-3")
        last = {f["key"]: f["last"] for f in form["fields"]}
        self.assertEqual(float(last["vacuum_kpa"]), 55.0)

    def test_spares_adjust(self):
        before = {p["part_id"]: p for p in self.get("/api/spares")}["air_filter"]["stock"]
        self.post("/api/spares", {"part_id": "air_filter", "delta": 2})
        after = {p["part_id"]: p for p in self.get("/api/spares")}["air_filter"]["stock"]
        self.assertEqual(after, before + 2)

    def test_maintenance_resets_life_and_uses_stock(self):
        def lamp(ov):
            m = next(x for x in ov["machines"] if x["machine_id"] == "DIS8-2")
            return next(p for p in m["parts"] if p["part_id"] == "lamp")
        self.post("/api/spares", {"part_id": "lamp", "stock": 3})
        self.assertLess(lamp(self.get("/api/overview"))["due_days"], 14)
        r = self.post("/api/maintenance", {"machine_id": "DIS8-2", "item": "照明燈管更換", "part_id": "lamp"})
        self.assertEqual(r["spare"]["stock"], 2)
        self.assertIn("lamp_hours", r["saved"])
        sched = next(x for x in self.get("/api/overview")["machines"] if x["machine_id"] == "DIS8-2")["schedule"]
        item = next(x for x in sched if x["item"] == "照明燈管更換")
        self.assertGreater(item["due_days"], 50)


if __name__ == "__main__":
    unittest.main()
