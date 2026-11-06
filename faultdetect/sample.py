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


D8 = ("D83", "D85", "D88")
D8_FIELDS = ["timestamp", "machine_id", "lamp_intensity", "focus_score", "vacuum_kpa", "air_pressure",
             "registration_score", "stage_error_um", "temperature", "scan_time",
             "run_hours", "lamp_hours", "panel_count"]


def write_d8_history(path, days=30, seed=8):
    """3 台 Discovery 8:D83 真空緩降、D85 燈管衰減、D88 健康。"""
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 0, 0)
    init = {"D83": (31000, 900), "D85": (42000, 1380), "D88": (27000, 300)}
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=D8_FIELDS)
        w.writeheader()
        for mid in D8:
            for i in range(days * 4):
                d = i / 4
                v = dict(lamp_intensity=97 + rnd.gauss(0, 0.4), focus_score=91 + rnd.gauss(0, 0.5),
                         vacuum_kpa=78 + rnd.gauss(0, 0.6), air_pressure=6.2 + rnd.gauss(0, 0.05),
                         registration_score=0.95 + rnd.gauss(0, 0.004), stage_error_um=2 + rnd.gauss(0, 0.2),
                         temperature=22 + rnd.gauss(0, 0.2), scan_time=42 + rnd.gauss(0, 0.8))
                if mid == "D83":
                    v["vacuum_kpa"] -= d * 0.55
                elif mid == "D85":
                    v["lamp_intensity"] -= d * 0.3
                v["run_hours"] = init[mid][0] + d * 20
                v["lamp_hours"] = init[mid][1] + d * 20
                v["panel_count"] = int(d * 1500)
                w.writerow({"timestamp": (start + timedelta(hours=6 * i)).isoformat(timespec="minutes"),
                            "machine_id": mid, **{k: round(x, 3) for k, x in v.items()}})


def write_d8_log(path):
    rows = []
    for mid in D8:
        rows += [(mid, "掃描鏡頭 / 保護玻璃清潔", "2026-01-28", ""), (mid, "真空吸附平台清潔", "2026-01-27", ""),
                 (mid, "照明與影像校正(校正片)", "2026-01-20", ""), (mid, "空壓過濾器排水 / 濾芯檢查", "2026-01-15", ""),
                 (mid, "散熱風扇濾網清潔", "2025-12-15", ""), (mid, "XY 平台導軌潤滑", "2025-12-20", ""),
                 (mid, "真空幫浦保養", "2025-11-01", "")]
    rows += [("D83", "照明燈管更換", "2025-11-01", "400"), ("D85", "照明燈管更換", "2025-09-01", "600"),
             ("D88", "照明燈管更換", "2026-01-15", "0")]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "machine_id", "item", "lamp_hours"])
        w.writerows([(d, m, it, lh) for m, it, d, lh in rows])


def write_d8_results(path, panels=200, seed=9):
    """D83 正常、D85 同座標重複斷路(底片缺陷)、D88 短路偏多(蝕刻不足)。"""
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 8, 0)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "machine_id", "board_id", "result",
                                          "defect_type", "location", "verdict"])
        w.writeheader()
        for mid in D8:
            for b in range(panels):
                ts = (start + timedelta(seconds=90 * b)).isoformat(timespec="seconds")
                calls = []
                if rnd.random() < 0.05:
                    calls.append((rnd.choice(["nick", "protrusion", "pinhole"]),
                                  f"X{rnd.randint(1, 500)}Y{rnd.randint(1, 600)}", "false"))
                if rnd.random() < 0.01:
                    calls.append((rnd.choice(["open", "short"]), f"X{rnd.randint(1, 500)}Y{rnd.randint(1, 600)}", "real"))
                if mid == "D85" and rnd.random() < 0.06:
                    calls.append(("open", "X212Y348", "real"))
                if mid == "D88" and rnd.random() < 0.08:
                    calls.append(("short", f"X{rnd.randint(1, 500)}Y{rnd.randint(1, 600)}", "real"))
                base = {"timestamp": ts, "machine_id": mid, "board_id": f"{mid}-{b:04d}"}
                if not calls:
                    w.writerow({**base, "result": "PASS", "defect_type": "", "location": "", "verdict": ""})
                for dtype, loc, verdict in calls:
                    w.writerow({**base, "result": "NG", "defect_type": dtype, "location": loc, "verdict": verdict})


F22 = ("F1", "F2")
F22_FIELDS = ["timestamp", "machine_id", "light_ch1", "light_ch2", "light_ch3", "focus_score", "vacuum_kpa",
              "air_pressure", "registration_score", "stage_error_um", "temperature", "sides_per_hour",
              "run_hours", "light_hours", "panel_count"]


def write_f22_history(path, days=30, seed=22):
    """2 台 Fusion 22:F1 照明通道 2 衰減、F2 XY 定位誤差上升 + 產能下滑。"""
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 0, 0)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=F22_FIELDS)
        w.writeheader()
        for n, mid in enumerate(F22):
            for i in range(days * 4):
                d = i / 4
                v = dict(light_ch1=97 + rnd.gauss(0, 0.4), light_ch2=97 + rnd.gauss(0, 0.4),
                         light_ch3=97 + rnd.gauss(0, 0.4), focus_score=92 + rnd.gauss(0, 0.5),
                         vacuum_kpa=80 + rnd.gauss(0, 0.6), air_pressure=6.2 + rnd.gauss(0, 0.05),
                         registration_score=0.96 + rnd.gauss(0, 0.004), stage_error_um=1.5 + rnd.gauss(0, 0.15),
                         temperature=22 + rnd.gauss(0, 0.2), sides_per_hour=240 + rnd.gauss(0, 3))
                if mid == "F1":
                    v["light_ch2"] -= d * 0.32
                else:
                    v["stage_error_um"] += d * 0.11
                    v["sides_per_hour"] -= d * 0.9
                v["run_hours"] = 8000 + n * 3000 + d * 20
                v["light_hours"] = 4000 + n * 2000 + d * 20
                v["panel_count"] = int(d * 2500)
                w.writerow({"timestamp": (start + timedelta(hours=6 * i)).isoformat(timespec="minutes"),
                            "machine_id": mid, **{k: round(x, 3) for k, x in v.items()}})


def write_f22_log(path):
    items = ["掃描鏡頭 / 保護玻璃清潔", "真空吸附平台清潔", "多光源照明與影像校正(校正片)",
             "空壓過濾器排水 / 濾芯檢查", "散熱風扇濾網清潔", "XY 平台導軌潤滑", "真空幫浦保養"]
    dates = ["2026-01-28", "2026-01-27", "2026-01-20", "2026-01-15", "2025-12-15", "2025-12-20", "2025-11-01"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "machine_id", "item", "light_hours"])
        for mid in F22:
            w.writerows([(d, mid, it, "") for it, d in zip(items, dates)])
            w.writerow(("2025-06-01", mid, "照明光源模組檢查 / 更換(依原廠壽命)", "0"))


VRS = tuple(f"VRS-{i}" for i in range(1, 7))
VRS_FIELDS = ["timestamp", "machine_id", "focus_score", "light_intensity", "vacuum_kpa", "gantry_error_um",
              "move_time_ms", "run_hours", "light_hours"]


def write_vrs_history(path, days=30, seed=66):
    """6 台 VRS:VRS-2 照明衰減、VRS-5 橋架定位誤差上升,其餘正常。"""
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 0, 0)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=VRS_FIELDS)
        w.writeheader()
        for n, mid in enumerate(VRS):
            for i in range(days * 4):
                d = i / 4
                v = dict(focus_score=90 + rnd.gauss(0, 0.6), light_intensity=97 + rnd.gauss(0, 0.4),
                         vacuum_kpa=70 + rnd.gauss(0, 0.6), gantry_error_um=8 + rnd.gauss(0, 0.6),
                         move_time_ms=380 + rnd.gauss(0, 12))
                if mid == "VRS-2":
                    v["light_intensity"] -= d * 0.33
                elif mid == "VRS-5":
                    v["gantry_error_um"] += d * 0.4
                    v["move_time_ms"] += d * 5
                v["run_hours"] = 6000 + n * 1500 + d * 18
                v["light_hours"] = 3000 + n * 1200 + d * 18
                w.writerow({"timestamp": (start + timedelta(hours=6 * i)).isoformat(timespec="minutes"),
                            "machine_id": mid, **{k: round(x, 3) for k, x in v.items()}})


def write_vrs_log(path):
    items = [("鏡頭 / 保護玻璃清潔", "2026-01-28"), ("吸附平台清潔", "2026-01-27"),
             ("照明與相機校正(校正片)", "2026-01-20"), ("鍵盤 / 軌跡球清潔檢查", "2026-01-10"),
             ("橋架導軌清潔潤滑", "2025-12-20")]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "machine_id", "item", "light_hours"])
        for mid in VRS:
            w.writerows([(d, mid, it, "") for it, d in items])
            w.writerow(("2025-03-01", mid, "照明光源更換(依原廠壽命)", "0"))


ET = tuple(f"ET{i}" for i in range(1, 7))
ET_FIELDS = ["timestamp", "machine_id", "false_fail_pct", "contact_fail_pts", "air_pressure", "selftest_fail_pins",
             "cycle_time_s", "run_hours", "press_cycles"]


def write_et_history(path, days=30, seed=77):
    """6 台電測:ET1 測試針磨耗(接觸不良上升)、ET5 氣壓下降,其餘正常。"""
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, 0, 0)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ET_FIELDS)
        w.writeheader()
        for n, mid in enumerate(ET):
            for i in range(days * 4):
                d = i / 4
                v = dict(false_fail_pct=1.0 + abs(rnd.gauss(0, 0.2)), contact_fail_pts=1.5 + abs(rnd.gauss(0, 0.3)),
                         air_pressure=6.2 + rnd.gauss(0, 0.04), selftest_fail_pins=0, cycle_time_s=15 + rnd.gauss(0, 0.4))
                if mid == "ET1":
                    v["contact_fail_pts"] += d * 0.12
                    v["false_fail_pct"] += d * 0.06
                elif mid == "ET5":
                    v["air_pressure"] -= d * 0.025
                v["run_hours"] = 30000 + n * 2000 + d * 20
                v["press_cycles"] = 200000 + n * 50000 + int(d * 2400)
                w.writerow({"timestamp": (start + timedelta(hours=6 * i)).isoformat(timespec="minutes"),
                            "machine_id": mid, **{k: round(x, 3) for k, x in v.items()}})


def write_et_log(path):
    items = [("治具 / 針盤清潔", "2026-01-28"), ("系統自我測試(Self-Test)", "2026-01-27"),
             ("空壓過濾器排水 / 濾芯檢查", "2026-01-15"), ("伸縮護套 / 導柱外觀檢查", "2025-12-01"),
             ("外部校正(ATT)", "2024-03-09"), ("導柱 / 軸承潤滑", "2026-01-05")]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "machine_id", "item", "press_cycles"])
        for n, mid in enumerate(ET):
            w.writerows([(d, mid, it, "") for it, d in items])
            w.writerow(("2025-06-01", mid, "測試針 / 彈簧針更換", str(200000 + n * 50000 - 330000 + n * 20000)))


SAMPLES = {"et-history": write_et_history, "et-log": write_et_log, "vrs-history": write_vrs_history, "vrs-log": write_vrs_log, "f22-history": write_f22_history, "f22-log": write_f22_log,
           "d8-history": write_d8_history, "d8-log": write_d8_log, "d8-results": write_d8_results,
           "aoi-history": write_aoi_history, "maintenance-log": write_maintenance_log, "generic": write_sample, "aoi": write_aoi_sensors, "aoi-results": write_aoi_results}
