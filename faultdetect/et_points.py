"""電測假點分析:從不良點紀錄找出問題在「哪支針 / 哪一區 / 哪副治具 / 哪台機台 / 板子本身」。

CSV 欄位(每個不良點一列;全部通過的板子留一列、point 空白,用來計算片數):
  timestamp, machine_id, fixture_id, board_id, point, x, y, fail_type(open/short), retest(pass/fail)
  retest=pass → 重測通過 = 假點;fail → 真不良。x, y 為針位座標(mm,可空白)。
"""
from collections import Counter, defaultdict

from .detector import Finding

COLUMNS = {"fixture_id", "retest"}
RULES = {
    "false_per_board": {"warn": 0.3, "alarm": 1.0},   # 每片平均假點數
    "repeat_min": 5, "repeat_share": 0.03,            # 同一支針假點 ≥5 次且 ≥3% 片數
    "edge_share": 0.6, "edge_min": 10,                # 假點 ≥60% 集中在某一側
    "spread_min_pins": 20,                            # 假點分散在很多支針
}


def is_et_points(rows):
    return bool(rows) and COLUMNS <= set(rows[0].keys())


def _level(v, r):
    return "alarm" if v > r["alarm"] else "warn" if v > r["warn"] else None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _edge(points):
    """回傳假點集中的那一側(左 / 右 / 上 / 下)與比例。"""
    xy = [(x, y) for x, y in points if x is not None and y is not None]
    if len(xy) < RULES["edge_min"]:
        return None
    xs, ys = [p[0] for p in xy], [p[1] for p in xy]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if x1 - x0 < 1e-9 or y1 - y0 < 1e-9:
        return None
    sides = {"左側": sum(x < x0 + (x1 - x0) / 3 for x in xs), "右側": sum(x > x1 - (x1 - x0) / 3 for x in xs),
             "下側": sum(y < y0 + (y1 - y0) / 3 for y in ys), "上側": sum(y > y1 - (y1 - y0) / 3 for y in ys)}
    side, n = max(sides.items(), key=lambda kv: kv[1])
    share = n / len(xy)
    return (side, share) if share >= RULES["edge_share"] else None


def analyze(rows):
    by_m = defaultdict(list)
    for r in rows:
        by_m[(r.get("machine_id") or "?").strip()].append(r)

    # 交叉比對用:每台 × 每副治具的假點率
    rate = {}
    for mid, rs in by_m.items():
        for fx in {r.get("fixture_id") for r in rs}:
            sub = [r for r in rs if r.get("fixture_id") == fx]
            boards = len({r["board_id"] for r in sub}) or 1
            rate[(mid, fx)] = (sum(1 for r in sub if (r.get("retest") or "").lower() == "pass" and r.get("point")) / boards, boards)
    high = {k for k, (v, n) in rate.items() if v > RULES["false_per_board"]["warn"] and n >= 10}

    out = {}
    for mid, rs in by_m.items():
        fs = []
        boards = len({r["board_id"] for r in rs}) or 1
        false = [r for r in rs if r.get("point") and (r.get("retest") or "").lower() == "pass"]
        real = [r for r in rs if r.get("point") and (r.get("retest") or "").lower() != "pass"]
        v = len(false) / boards
        if (lv := _level(v, RULES["false_per_board"])):
            fs.append(Finding(mid, "et_points", "false_fail_pct_high", lv,
                              f"每片平均假點 {v:.2f} 點({len(false)} 點 / {boards} 片,真不良 {len(real)} 點)", v))
        for fx in sorted({r.get("fixture_id") for r in false}):
            fx_false = [r for r in false if r.get("fixture_id") == fx]
            fx_boards = rate[(mid, fx)][1]
            pins = Counter(r["point"] for r in fx_false)
            reps = [(p, n) for p, n in pins.most_common(8)
                    if n >= max(RULES["repeat_min"], RULES["repeat_share"] * fx_boards)]
            if reps:
                fs.append(Finding(mid, "et_points", "repeat_pin", "warn",
                                  f"治具 {fx}:固定針位重複假點 → " + "、".join(f"{p}({n} 次)" for p, n in reps)
                                  + " → 優先清潔 / 更換這幾支針", len(reps)))
            edge = _edge([(_f(r.get("x")), _f(r.get("y"))) for r in fx_false])
            if edge:
                fs.append(Finding(mid, "et_points", "region_edge", "warn",
                                  f"治具 {fx}:假點 {edge[1]:.0%} 集中在{edge[0]} → 對位偏移或壓合不平行", edge[1]))
            if len(pins) >= RULES["spread_min_pins"] and not reps and not edge:
                fs.append(Finding(mid, "et_points", "spread_false", "warn",
                                  f"治具 {fx}:假點分散在 {len(pins)} 支針、無固定位置 → 針頭普遍髒污 / 磨耗或板面污染", len(pins)))
        # 交叉比對
        my_fx = [fx for (m, fx) in rate if m == mid]
        my_high = [fx for fx in my_fx if (mid, fx) in high]
        if len(my_fx) >= 2 and len(my_high) == len(my_fx):
            fs.append(Finding(mid, "et_points", "machine_wide", "alarm",
                              f"本機換了 {len(my_fx)} 副治具都假點偏高 → 問題在機台(格點彈簧針 / 開關卡 / 壓合)", len(my_fx)))
        for fx in my_high:
            others = [m for (m, f) in rate if f == fx and m != mid]
            if others and all((m, fx) in high for m in others):
                fs.append(Finding(mid, "et_points", "fixture_wide", "alarm",
                                  f"治具 {fx} 在 {len(others) + 1} 台機台都假點偏高 → 問題在治具本身(針床)", len(others) + 1))
            elif others and not any((m, fx) in high for m in others):
                fs.append(Finding(mid, "et_points", "machine_wide", "warn",
                                  f"治具 {fx} 在其他機台正常、只有本機假點高 → 問題偏向本機台", 1))
        out[mid] = fs
    return out
