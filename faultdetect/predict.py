"""預知保養:趨勢外推預測何時會超標、健康分數、定期保養到期提醒。

感測 CSV 需有 timestamp(ISO 格式),可選累計計數欄位 run_hours、board_count。
保養紀錄 CSV:date, machine_id, item[, run_hours, board_count]
"""
from collections import defaultdict
from datetime import datetime, timedelta

from . import detector

LEVEL_ORDER = {"overdue": 0, "alarm": 1, "warn": 2, "info": 3, "ok": 4}
LEVEL_TEXT = {"overdue": "已逾期/已超標", "alarm": "緊急", "warn": "近期", "info": "規劃", "ok": "正常"}


def _ts(s):
    try:
        return datetime.fromisoformat((s or "").strip())
    except ValueError:
        return None


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _fit(points):
    """最小平方法,回傳 (slope, intercept, r2)。"""
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    if sxx == 0:
        return 0.0, my, 0.0
    sxy = sum((x - mx) * (y - my) for x, y in points)
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((y - my) ** 2 for _, y in points)
    r2 = (sxy * sxy) / (sxx * syy) if syy else 0.0
    return slope, intercept, r2


def _limits(rule):
    """回傳 (方向, warn, alarm);方向 +1 代表往上超標,-1 代表往下。"""
    if "max_warn" in rule or "max_alarm" in rule:
        return 1, rule.get("max_warn"), rule.get("max_alarm")
    if "min_warn" in rule or "min_alarm" in rule:
        return -1, rule.get("min_warn"), rule.get("min_alarm")
    return 0, None, None


def _related_faults(sensor, direction, kb):
    keys = {f"{sensor}_high", f"{sensor}_rising"} if direction > 0 else {f"{sensor}_low", f"{sensor}_falling"}
    hits = [(sum(w for s, w in f["symptoms"].items() if s in keys), f) for f in kb]
    return [f for score, f in sorted(hits, key=lambda h: -h[0]) if score > 0][:2]


def predict_sensor(sensor, pts, now, cfg, kb):
    rule = cfg["sensors"][sensor]
    pc = cfg["predict"]
    direction, warn, alarm = _limits(rule)
    window = [(t, v) for t, v in pts if t >= now - timedelta(days=pc["window_days"])]
    if direction == 0 or len(window) < pc["min_points"]:
        return None
    t0 = window[0][0]
    xy = [((t - t0).total_seconds() / 86400, v) for t, v in window]
    slope, intercept, r2 = _fit(xy)
    x_now = (now - t0).total_seconds() / 86400
    current = slope * x_now + intercept

    # 健康分數:基準值(歷史前段中位數)到警報值的剩餘比例
    head = sorted(v for _, v in pts[: max(3, len(pts) // 5)])
    baseline = head[len(head) // 2]
    limit = alarm if alarm is not None else warn
    span = (limit - baseline) * direction
    health = 100.0 if span <= 0 else max(0.0, min(1.0, (limit - current) * direction / span)) * 100

    res = {"sensor": sensor, "name": rule.get("name", sensor), "current": round(current, 3),
           "slope_per_day": round(slope, 4), "r2": round(r2, 2), "health": round(health),
           "eta": {}, "level": "ok", "faults": []}

    heading = slope * direction > 0 and r2 >= pc["min_r2"]
    for key, thr in (("warn", warn), ("alarm", alarm)):
        if thr is None:
            continue
        if (current - thr) * direction >= 0:
            res["eta"][key] = 0.0
        elif heading:
            res["eta"][key] = round((thr - current) / slope, 1)

    days = min(res["eta"].values(), default=None)
    if days is not None:
        if days <= 0:
            res["level"] = "overdue"
        elif days <= pc["urgent_days"]:
            res["level"] = "alarm"
        elif days <= pc["soon_days"]:
            res["level"] = "warn"
        else:
            res["level"] = "info"
        res["due_days"] = days
        res["faults"] = [{"name": f["name"], "steps": f["steps"]}
                         for f in _related_faults(sensor, direction, kb)]
    return res


def _usage_rate(pts):
    if len(pts) < 2:
        return None
    t0 = pts[0][0]
    slope, _, _ = _fit([((t - t0).total_seconds() / 86400, v) for t, v in pts])
    return slope if slope > 0 else None


def schedule(mid, counters, now, cfg, log):
    """依保養週期計算下次到期。log: {(mid, item): (date, {counter: value})}"""
    pc = cfg["predict"]
    out = []
    for m in cfg.get("maintenance", []):
        item = m["item"]
        last = log.get((mid, item))
        entry = {"item": item, "last": last[0].date().isoformat() if last else None}
        if last is None:
            entry.update(level="warn", due_days=None, note="無保養紀錄,建議盡快執行並登錄")
            out.append(entry)
            continue
        if "every_days" in m:
            due = (last[0] + timedelta(days=m["every_days"]) - now).total_seconds() / 86400
            entry["note"] = f"每 {m['every_days']} 天"
        else:
            unit = "every_hours" if "every_hours" in m else "every_boards"
            col = m["counter"]
            pts = counters.get(col, [])
            rate = _usage_rate(pts)
            if not pts or rate is None:
                continue
            current = pts[-1][1]
            at_last = last[1].get(col)
            if at_last is None:
                at_last = current - rate * (now - last[0]).total_seconds() / 86400
            remaining = m[unit] - (current - at_last)
            due = remaining / rate
            label = "小時" if unit == "every_hours" else "片"
            entry["note"] = f"每 {m[unit]:,} {label},剩 {max(remaining, 0):,.0f} {label}"
        entry["due_days"] = round(due, 1)
        entry["level"] = ("overdue" if due <= 0 else "alarm" if due <= pc["urgent_days"]
                          else "warn" if due <= pc["soon_days"] else "ok")
        out.append(entry)
    return out


def load_log(source):
    log = {}
    if source is None:
        return log
    for r in detector.read_rows(source):
        t = _ts(r.get("date"))
        if not t:
            continue
        key = ((r.get("machine_id") or "").strip(), (r.get("item") or "").strip())
        vals = {k: _num(v) for k, v in r.items() if k not in ("date", "machine_id", "item") and _num(v) is not None}
        if key not in log or t > log[key][0]:
            log[key] = (t, vals)
    return log


def run(source, profile="aoi", log_source=None, config_path=None):
    cfg = detector.load_config(config_path, profile)
    from .diagnosis import load_kb
    kb = load_kb(profile=profile)
    log = load_log(log_source)

    by_machine = defaultdict(lambda: defaultdict(list))
    for r in detector.read_rows(source):
        t = _ts(r.get("timestamp"))
        if not t:
            continue
        mid = (r.get("machine_id") or "M?").strip()
        for k, v in r.items():
            val = _num(v)
            if val is not None and k not in ("timestamp", "machine_id"):
                by_machine[mid][k].append((t, val))
    if not by_machine:
        raise ValueError("沒有含 timestamp 的資料")

    report = []
    for mid, cols in by_machine.items():
        now = max(p[-1][0] for p in cols.values())
        preds = [p for s in cfg["sensors"] if s in cols
                 for p in [predict_sensor(s, sorted(cols[s]), now, cfg, kb)] if p]
        sched = schedule(mid, {k: sorted(v) for k, v in cols.items()}, now, cfg, log)
        tasks = [{"type": "預知", "item": f"{p['name']} 預計 {p['due_days']:g} 天後超標",
                  "level": p["level"], "due_days": p["due_days"],
                  "action": p["faults"][0]["name"] if p["faults"] else "檢查該項目"}
                 for p in preds if p["level"] != "ok"]
        tasks += [{"type": "定期", "item": s["item"], "level": s["level"], "due_days": s["due_days"],
                   "action": s["note"]} for s in sched if s["level"] != "ok"]
        tasks.sort(key=lambda x: (LEVEL_ORDER[x["level"]], x["due_days"] if x["due_days"] is not None else -1))
        health = min((p["health"] for p in preds), default=100)
        level = min((t["level"] for t in tasks), key=LEVEL_ORDER.get, default="ok")
        report.append({"machine_id": mid, "as_of": now.isoformat(timespec="minutes"),
                       "health": health, "level": level,
                       "predictions": preds, "schedule": sched, "tasks": tasks})
    return sorted(report, key=lambda m: (m["health"], m["machine_id"]))
