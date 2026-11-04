"""產生模擬感測資料:M01 正常、M02 軸承磨損、M03 冷卻故障、M04 氣壓洩漏。"""
import csv
import random
from datetime import datetime, timedelta

FIELDS = ["timestamp", "machine_id", "temperature", "vibration", "current", "pressure", "rpm"]


def _row(t, mid, i, rnd):
    base = dict(temperature=55 + rnd.gauss(0, 1), vibration=2.0 + rnd.gauss(0, 0.2),
                current=12 + rnd.gauss(0, 0.3), pressure=6 + rnd.gauss(0, 0.1),
                rpm=1480 + rnd.gauss(0, 5))
    if mid == "M02":
        base["vibration"] += i * 0.3
        base["temperature"] += i * 0.8
    elif mid == "M03":
        base["temperature"] += i * 1.6
    elif mid == "M04":
        base["pressure"] -= i * 0.12
    return {"timestamp": t.isoformat(timespec="seconds"), "machine_id": mid,
            **{k: round(v, 2) for k, v in base.items()}}


def write_sample(path, n=20, seed=42):
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 8, 0)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for mid in ("M01", "M02", "M03", "M04"):
            for i in range(n):
                w.writerow(_row(start + timedelta(minutes=i), mid, i, rnd))
