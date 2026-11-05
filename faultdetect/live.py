"""即時監看:作業中記錄事件(手動或從機台 Log 自動擷取),短時間重複發生即警示並提出改善建議。

資料檔(在資料目錄):
  sessions.csv  監看場次
  events.csv    事件
"""
import csv
import os
import re
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import detector, diagnosis

SESSION_FIELDS = ["session_id", "machine_id", "operator", "start", "end", "note"]
EVENT_FIELDS = ["time", "session_id", "machine_id", "event", "source", "note"]


def _now():
    return datetime.now().replace(microsecond=0)


class Live:
    def __init__(self, data_dir, meta, profile_of, clock=_now):
        self.dir = Path(data_dir)
        self.meta = meta
        self.profile_of = profile_of          # machine_id -> profile
        self.clock = clock
        self.lock = threading.Lock()

    # ---------- 檔案 ----------
    def _read(self, name):
        p = self.dir / name
        return detector.read_rows(p) if p.exists() else []

    def _append(self, name, fields, row):
        p = self.dir / name
        with self.lock:
            new = not p.exists()
            with open(p, "a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                if new:
                    w.writeheader()
                w.writerow(row)

    def _rewrite_sessions(self, rows):
        with self.lock, open(self.dir / "sessions.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=SESSION_FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    # ---------- 設定 ----------
    def config(self, mid):
        prof = self.profile_of(mid)
        cfg = detector.load_config(profile=prof)
        return prof, cfg.get("events", []), cfg.get("event_rules", {"count": 3, "minutes": 30})

    def events_config(self, mid):
        return self.config(mid)[1]

    # ---------- 場次 ----------
    def session(self, sid):
        s = next((r for r in self._read("sessions.csv") if r["session_id"] == sid), None)
        if not s:
            raise ValueError("找不到監看場次")
        return s

    def active(self, mid):
        return next((r for r in reversed(self._read("sessions.csv"))
                     if r["machine_id"] == mid and not r.get("end")), None)

    def start(self, mid, operator=""):
        self.profile_of(mid)  # 驗證機台
        if (s := self.active(mid)):
            return s
        s = {"session_id": uuid.uuid4().hex[:10], "machine_id": mid, "operator": operator[:50],
             "start": self.clock().isoformat(), "end": "", "note": ""}
        self._append("sessions.csv", SESSION_FIELDS, s)
        return s

    def end(self, sid, note=""):
        rows = self._read("sessions.csv")
        for r in rows:
            if r["session_id"] == sid and not r.get("end"):
                r["end"], r["note"] = self.clock().isoformat(), note[:2000]
        self._rewrite_sessions(rows)
        return self.report(sid)

    def add_event(self, sid, event, note="", source="manual"):
        s = self.session(sid)
        if s.get("end"):
            raise ValueError("此場次已結束")
        ids = {e["id"] for e in self.events_config(s["machine_id"])}
        if event not in ids and event != "note":
            raise ValueError(f"未知事件 {event}")
        row = {"time": self.clock().isoformat(), "session_id": sid, "machine_id": s["machine_id"],
               "event": event, "source": source, "note": note[:1000]}
        self._append("events.csv", EVENT_FIELDS, row)
        return row

    def log_event(self, mid, event, note):
        """從 Log 擷取的事件:有進行中場次就記到該場次,否則記為未分場次。"""
        s = self.active(mid)
        row = {"time": self.clock().isoformat(), "session_id": s["session_id"] if s else "",
               "machine_id": mid, "event": event, "source": "log", "note": note[:300]}
        self._append("events.csv", EVENT_FIELDS, row)

    # ---------- 分析 ----------
    def _analyze(self, mid, events, now):
        prof, ecfg, rule = self.config(mid)
        names = {e["id"]: e for e in ecfg}
        window = now - timedelta(minutes=rule["minutes"])
        recent = Counter(e["event"] for e in events if datetime.fromisoformat(e["time"]) >= window)
        total = Counter(e["event"] for e in events)
        kb = diagnosis.load_kb(profile=prof)
        alerts = []
        for ev, n in recent.items():
            conf = names.get(ev)
            if not conf or n < conf.get("alert_count", rule["count"]):
                continue
            sym = {s: "alarm" for s in conf.get("symptoms", [])}
            alerts.append({"event": ev, "name": conf["name"], "count": n, "minutes": rule["minutes"],
                           "suggestions": diagnosis.diagnose(sym, kb, min_score=0.2)[:2] if sym else []})
        # 整場綜合:依各事件次數加權推論
        sym = {}
        for ev, n in total.items():
            for s in names.get(ev, {}).get("symptoms", []):
                sym[s] = "alarm" if n >= rule["count"] else "warn"
        # 依「支持這個原因的事件次數」排序,次數相同再看信心
        by_sym = Counter()
        for ev, n in total.items():
            for s in names.get(ev, {}).get("symptoms", []):
                by_sym[s] += n
        overall = diagnosis.diagnose(sym, kb, min_score=0.3) if sym else []
        for d in overall:
            d["support"] = max((by_sym[s] for s in d["matched"]), default=0)
        overall = sorted(overall, key=lambda d: (-d["support"], -d["confidence"]))[:3]
        counts = [{"event": ev, "name": names.get(ev, {}).get("name", ev), "count": n} for ev, n in total.most_common()]
        return alerts, overall, counts

    def live(self, sid):
        s = self.session(sid)
        events = [e for e in self._read("events.csv") if e["session_id"] == sid]
        alerts, overall, counts = self._analyze(s["machine_id"], events, self.clock())
        return {"session": s, "events": events[::-1], "alerts": alerts, "overall": overall, "counts": counts}

    def report(self, sid):
        d = self.live(sid)
        s = d["session"]
        end = datetime.fromisoformat(s["end"]) if s.get("end") else self.clock()
        d["duration_min"] = round((end - datetime.fromisoformat(s["start"])).total_seconds() / 60)
        return d

    def sessions(self):
        return self._read("sessions.csv")[::-1]


class LogWatcher(threading.Thread):
    """持續讀取機台 Log 新增內容,用正規表示式比對成事件。

    machines.json 的機台可加:
      "live_log": {"path": "\\\\AOI-PC\\Logs\\event.log", "encoding": "utf-8",
                   "patterns": [{"regex": "Registration failed", "event": "registration_fail"}]}
    """

    def __init__(self, live, machines, interval=5):
        super().__init__(daemon=True)
        self.live, self.interval = live, interval
        self.targets = []
        for m in machines:
            cfg = m.get("live_log")
            if cfg and cfg.get("path"):
                pats = [(re.compile(p["regex"], re.I), p["event"]) for p in cfg.get("patterns", [])]
                self.targets.append({"mid": m["id"], "path": Path(cfg["path"]), "enc": cfg.get("encoding", "utf-8"),
                                     "pats": pats, "pos": None})

    def poll_once(self):
        for t in self.targets:
            try:
                size = os.path.getsize(t["path"])
            except OSError:
                continue
            if t["pos"] is None or size < t["pos"]:      # 第一次從檔尾開始;檔案輪替則從頭
                t["pos"] = size if t["pos"] is None else 0
                if t["pos"] == size:
                    continue
            with open(t["path"], "rb") as f:
                f.seek(t["pos"])
                chunk = f.read()
            t["pos"] += len(chunk)
            for line in chunk.decode(t["enc"], errors="replace").splitlines():
                for rx, ev in t["pats"]:
                    if rx.search(line):
                        self.live.log_event(t["mid"], ev, line.strip())
                        break

    def run(self):
        while True:
            self.poll_once()
            time.sleep(self.interval)
