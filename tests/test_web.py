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
                  "f22_history.csv", "f22_maintenance_log.csv"):
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


if __name__ == "__main__":
    unittest.main()
