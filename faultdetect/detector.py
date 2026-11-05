"""感測資料異常偵測:門檻值、統計離群 (z-score)、趨勢、不穩定度。"""
import csv
import json
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path

PROFILES_DIR = Path(__file__).with_name("profiles")
PROFILES = ("discovery8", "fusion22", "vrs", "aoi", "generic")
LEVEL_RANK = {"info": 0, "warn": 1, "alarm": 2}


@dataclass
class Finding:
    machine_id: str
    sensor: str
    symptom: str      # 例如 temperature_high
    level: str        # info / warn / alarm
    message: str
    value: float | None = None

    def to_dict(self):
        return asdict(self)


def _merge(base, over):
    """字典深層合併;值為 null 代表刪除該鍵,清單整個取代。"""
    out = dict(base)
    for k, v in over.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path=None, profile="generic"):
    """讀取設定;支援 "extends": "<profile>" 繼承另一機型。"""
    with open(path or PROFILES_DIR / profile / "config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    parent = cfg.pop("extends", None)
    return _merge(load_config(profile=parent), cfg) if parent else cfg


def read_rows(path_or_file):
    if hasattr(path_or_file, "read"):
        return list(csv.DictReader(path_or_file))
    with open(path_or_file, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_csv(path_or_file):
    """讀取 CSV,依 machine_id 分組。回傳 {machine_id: {sensor: [值或 None]}}。"""
    return group_rows(read_rows(path_or_file))


def group_rows(rows):
    data = {}
    for row in rows:
        mid = (row.get("machine_id") or "M?").strip()
        bucket = data.setdefault(mid, {})
        for key, raw in row.items():
            if key in ("machine_id", "timestamp") or key is None:
                continue
            raw = (raw or "").strip()
            try:
                val = float(raw) if raw else None
            except ValueError:
                val = None
            bucket.setdefault(key, []).append(val)
    return data


def _slope(values):
    n = len(values)
    if n < 2:
        return 0.0
    xs = range(n)
    mx, my = (n - 1) / 2, sum(values) / n
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, values)) / den


def analyze_sensor(machine_id, sensor, series, cfg):
    findings = []
    rule = cfg["sensors"].get(sensor, {})
    name = rule.get("name", sensor)
    vals = [v for v in series if v is not None]

    missing = len(series) - len(vals)
    if series and missing / len(series) > 0.2:
        findings.append(Finding(machine_id, sensor, "sensor_missing", "warn",
                                f"{name} 缺值比例 {missing}/{len(series)}"))
    if not vals:
        return findings

    latest = vals[-1]
    # 1. 門檻值(以最新值判斷)
    for direction, op in (("max", lambda v, t: v > t), ("min", lambda v, t: v < t)):
        for level in ("alarm", "warn"):
            limit = rule.get(f"{direction}_{level}")
            if limit is not None and op(latest, limit):
                word = "high" if direction == "max" else "low"
                sign = ">" if direction == "max" else "<"
                findings.append(Finding(machine_id, sensor, f"{sensor}_{word}", level,
                                        f"{name} = {latest:g} {sign} {limit:g}", latest))
                break

    # 2. 統計離群 (z-score)
    if len(vals) >= 5:
        mean, sd = statistics.fmean(vals), statistics.pstdev(vals)
        if sd > 0:
            spikes = [v for v in vals if abs(v - mean) / sd > cfg.get("zscore_limit", 3)]
            if spikes:
                findings.append(Finding(machine_id, sensor, f"{sensor}_spike", "info",
                                        f"{name} 出現 {len(spikes)} 筆離群值", max(spikes, key=abs)))

    # 3. 趨勢(最後 N 筆的斜率)
    window = vals[-cfg.get("trend_window", 10):]
    slope_limit = cfg.get("trend_slope_warn", {}).get(sensor)
    if slope_limit is not None and len(window) >= 3:
        s = _slope(window)
        if s > slope_limit:
            findings.append(Finding(machine_id, sensor, f"{sensor}_rising", "warn",
                                    f"{name} 持續上升 (每筆 +{s:.2f})", s))

    fall_limit = cfg.get("trend_slope_fall_warn", {}).get(sensor)
    if fall_limit is not None and len(window) >= 3:
        s = _slope(window)
        if s < -fall_limit:
            findings.append(Finding(machine_id, sensor, f"{sensor}_falling", "warn",
                                    f"{name} 持續下降 (每筆 {s:.2f})", s))

    # 4. 不穩定度(變異係數)
    cv_limit = cfg.get("unstable_cv", {}).get(sensor)
    if cv_limit is not None and len(window) >= 3:
        mean = statistics.fmean(window)
        if mean:
            cv = statistics.pstdev(window) / abs(mean)
            if cv > cv_limit:
                findings.append(Finding(machine_id, sensor, f"{sensor}_unstable", "warn",
                                        f"{name} 波動過大 (CV={cv:.1%})", cv))
    return findings


def analyze(data, cfg=None):
    """data: {machine_id: {sensor: [values]}} → {machine_id: [Finding]}"""
    cfg = cfg or load_config()
    return {mid: [f for s, series in sensors.items()
                  for f in analyze_sensor(mid, s, series, cfg)]
            for mid, sensors in data.items()}
