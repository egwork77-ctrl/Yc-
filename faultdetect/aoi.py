"""AOI 檢測結果分析:誤判率、不良率、缺陷類型、重複位置。

結果 CSV 欄位(每筆缺陷一列,PASS 板一列且 defect_type 留空):
  timestamp, machine_id, board_id, result(PASS/NG), defect_type, component(或 location 座標), verdict(real/false)
verdict:人員複判結果,real=真不良,false=誤判;空白視為未複判。
"""
from collections import Counter, defaultdict

from .detector import Finding

RESULT_COLUMNS = {"board_id", "result"}


def is_results(rows):
    return bool(rows) and RESULT_COLUMNS <= set(rows[0].keys())


def _loc(r):
    return r.get("component") or r.get("location") or "?"


def _level(rate, rule):
    if rate > rule["alarm"]:
        return "alarm"
    if rate > rule["warn"]:
        return "warn"
    return None


def analyze_machine(mid, rows, cfg):
    rc, names = cfg["results"], cfg.get("defect_names", {})
    findings = []
    boards = {r["board_id"] for r in rows}
    n_boards = len(boards) or 1
    calls = [r for r in rows if (r.get("result") or "").upper() == "NG" and r.get("defect_type")]
    false_calls = [r for r in calls if (r.get("verdict") or "").lower() == "false"]
    real = [r for r in calls if (r.get("verdict") or "").lower() != "false"]

    # 誤判:裸板 AOI 誤判本來就多,可改用「每片誤判數」(false_call_per_board)
    if "false_call_per_board" in rc:
        rate = len(false_calls) / n_boards
        lv = _level(rate, rc["false_call_per_board"])
        if lv:
            findings.append(Finding(mid, "result", "false_call_high", lv,
                                    f"每片誤判 {rate:.2f} 點 ({len(false_calls)}/{n_boards})", rate))
    elif len(calls) >= rc["min_calls"]:
        rate = len(false_calls) / len(calls)
        lv = _level(rate, rc["false_call_rate"])
        if lv:
            findings.append(Finding(mid, "result", "false_call_high", lv,
                                    f"誤判率 {rate:.0%} ({len(false_calls)}/{len(calls)})", rate))

    # 誤判集中在少數元件
    if len(false_calls) >= rc["repeat_min_count"]:
        comp, cnt = Counter(_loc(r) for r in false_calls).most_common(1)[0]
        share = cnt / len(false_calls)
        if cnt >= rc["repeat_min_count"] and share >= rc["concentrated_share"]:
            findings.append(Finding(mid, "result", "false_call_concentrated", "warn",
                                    f"誤判集中在 {comp} ({cnt} 筆, {share:.0%})", share))

    # 真不良板比例
    ng_boards = {r["board_id"] for r in real}
    rate = len(ng_boards) / n_boards
    lv = _level(rate, rc["ng_board_rate"])
    if lv:
        findings.append(Finding(mid, "result", "ng_rate_high", lv,
                                f"不良板比例 {rate:.1%} ({len(ng_boards)}/{n_boards})", rate))

    # 各缺陷類型(定位類缺陷屬機台問題,所有判定都算)
    md = rc.get("machine_defect", "fiducial")
    by_type = Counter(r["defect_type"] for r in real if r["defect_type"] != md)
    by_type[md] = sum(1 for r in calls if r["defect_type"] == md)
    for dtype, cnt in by_type.items():
        if not cnt:
            continue
        rate = cnt / n_boards
        if dtype == md:
            lv = _level(rate, rc.get("machine_defect_rate") or rc["fiducial_rate"])
            symptom = f"{md}_fail_high"
        else:
            lv, symptom = _level(rate, rc["defect_rate"]), f"defect_{dtype}_high"
        if lv:
            findings.append(Finding(mid, "result", symptom, lv,
                                    f"{names.get(dtype, dtype)} 每板 {rate:.1%} ({cnt} 筆)", rate))

    # 同元件同缺陷重複發生
    repeats = Counter((_loc(r), r["defect_type"]) for r in real)
    for (comp, dtype), cnt in repeats.most_common(3):
        if cnt >= rc["repeat_min_count"]:
            findings.append(Finding(mid, "result", "repeat_location", "warn",
                                    f"{comp} 重複 {names.get(dtype, dtype)} {cnt} 次", cnt))
    return findings


def analyze_results(rows, cfg):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r.get("machine_id") or "M?").strip()].append(r)
    return {mid: analyze_machine(mid, rs, cfg) for mid, rs in grouped.items()}
