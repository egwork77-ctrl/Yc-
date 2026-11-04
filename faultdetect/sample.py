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


AOI_SENSOR_FIELDS = ["timestamp", "machine_id", "light_intensity", "focus_score",
                     "fiducial_score", "temperature", "conveyor_speed", "cycle_time"]
AOI_RESULT_FIELDS = ["timestamp", "machine_id", "board_id", "result", "defect_type",
                     "component", "verdict"]
COMPONENTS = ["R12", "C33", "U5", "Q2", "D7", "L1", "J3", "C108"]


def write_aoi_sensors(path, n=20, seed=1):
    """AOI1 正常、AOI2 光源衰減、AOI3 鏡頭失焦。"""
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 8, 0)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=AOI_SENSOR_FIELDS)
        w.writeheader()
        for mid in ("AOI1", "AOI2", "AOI3"):
            for i in range(n):
                v = dict(light_intensity=98 + rnd.gauss(0, 0.5), focus_score=92 + rnd.gauss(0, 0.8),
                         fiducial_score=0.95 + rnd.gauss(0, 0.005), temperature=28 + rnd.gauss(0, 0.3),
                         conveyor_speed=200 + rnd.gauss(0, 2), cycle_time=18 + rnd.gauss(0, 0.5))
                if mid == "AOI2":
                    v["light_intensity"] -= i * 1.0
                elif mid == "AOI3":
                    v["focus_score"] -= i * 1.2
                w.writerow({"timestamp": (start + timedelta(minutes=i)).isoformat(timespec="seconds"),
                            "machine_id": mid, **{k: round(x, 3) for k, x in v.items()}})


def write_aoi_results(path, boards=200, seed=7):
    """AOI1 正常、AOI2 誤判多(集中在 C33)、AOI3 U5 重複少錫(鋼板堵孔)。"""
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 8, 0)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=AOI_RESULT_FIELDS)
        w.writeheader()
        for mid in ("AOI1", "AOI2", "AOI3"):
            for b in range(boards):
                ts = (start + timedelta(seconds=20 * b)).isoformat(timespec="seconds")
                bid = f"{mid}-{b:04d}"
                calls = []
                if rnd.random() < 0.03:
                    calls.append((rnd.choice(["bridge", "missing", "shift"]), rnd.choice(COMPONENTS), "false"))
                if rnd.random() < 0.01:
                    calls.append((rnd.choice(["bridge", "missing"]), rnd.choice(COMPONENTS), "real"))
                if mid == "AOI2" and rnd.random() < 0.25:
                    calls.append(("shift", "C33", "false"))
                if mid == "AOI3" and rnd.random() < 0.08:
                    calls.append(("insufficient", "U5", "real"))
                if not calls:
                    w.writerow({"timestamp": ts, "machine_id": mid, "board_id": bid, "result": "PASS",
                                "defect_type": "", "component": "", "verdict": ""})
                for dtype, comp, verdict in calls:
                    w.writerow({"timestamp": ts, "machine_id": mid, "board_id": bid, "result": "NG",
                                "defect_type": dtype, "component": comp, "verdict": verdict})


PM_FIELDS = AOI_SENSOR_FIELDS + ["run_hours", "board_count"]


def write_aoi_history(path, days=30, seed=3):
    """30 天、每 6 小時一筆。AOI1 穩定、AOI2 光源緩慢衰減、AOI3 對焦緩慢下降。"""
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 0, 0)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PM_FIELDS)
        w.writeheader()
        for mid, hours0, boards0 in (("AOI1", 5000, 900000), ("AOI2", 18500, 3200000), ("AOI3", 9000, 1500000)):
            for i in range(days * 4):
                d = i / 4
                v = dict(light_intensity=97 + rnd.gauss(0, 0.4), focus_score=92 + rnd.gauss(0, 0.5),
                         fiducial_score=0.95 + rnd.gauss(0, 0.004), temperature=28 + rnd.gauss(0, 0.3),
                         conveyor_speed=200 + rnd.gauss(0, 2), cycle_time=18 + rnd.gauss(0, 0.4))
                if mid == "AOI2":
                    v["light_intensity"] -= d * 0.35
                elif mid == "AOI3":
                    v["focus_score"] -= d * 0.25
                v["run_hours"] = hours0 + d * 20
                v["board_count"] = boards0 + int(d * 3000)
                w.writerow({"timestamp": (start + timedelta(hours=6 * i)).isoformat(timespec="minutes"),
                            "machine_id": mid, **{k: round(x, 3) for k, x in v.items()}})


def write_maintenance_log(path):
    rows = []
    for mid in ("AOI1", "AOI2", "AOI3"):
        rows += [("2026-01-28", mid, "鏡頭與保護玻璃清潔"), ("2026-01-20", mid, "光源 / 相機校正(標準板驗證)"),
                 ("2025-12-15", mid, "散熱風扇與濾網清潔"), ("2025-12-20", mid, "XY 軸線軌 / 導螺桿潤滑"),
                 ("2025-11-01", mid, "輸送皮帶檢查 / 更換")]
    rows.append(("2024-01-10", "AOI1", "光源模組更換"))
    rows.append(("2023-05-15", "AOI2", "光源模組更換"))
    rows.append(("2024-08-15", "AOI3", "光源模組更換"))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "machine_id", "item"])
        w.writerows(rows)


SAMPLES = {"aoi-history": write_aoi_history, "maintenance-log": write_maintenance_log, "generic": write_sample, "aoi": write_aoi_sensors, "aoi-results": write_aoi_results}
