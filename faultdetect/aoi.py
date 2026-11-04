"""AOI 檢測結果分析:誤判率、不良率、缺陷類型、重複位置。

結果 CSV 欄位(每筆缺陷一列,PASS 板一列且 defect_type 留空):
  timestamp, machine_id, board_id, result(PASS/NG), defect_type, component, verdict(real/false)
verdict:人員複判結果,real=真不良,false=誤判;空白視為未複判。
"""
from collections import Counter, defaultdict

from .detector import Finding

RESULT_COLUMNS = {"board_id", "result"}


def is_results(rows):
    return bool(rows) and RESULT_COLUMNS <= set(rows[0].keys())


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

    # 誤判率
    if len(calls) >= rc["min_calls"]:
        rate = len(false_calls) / len(calls)
        lv = _level(rate, rc["false_call_rate"])
        if lv:
            findings.append(Finding(mid, "result", "false_call_high", lv,
                                    f"誤判率 {rate:.0%} ({len(false_calls)}/{len(calls)})", rate))

    # 誤判集中在少數元件
    if len(false_calls) >= rc["repeat_min_count"]:
        comp, cnt = Counter(r.get("component") or "?" for r in false_calls).most_common(1)[0]
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

    # 各缺陷類型(fiducial 屬機台定位問題,所有判定都算)
    by_type = Counter(r["defect_type"] for r in real if r["defect_type"] != "fiducial")
    by_type["fiducial"] = sum(1 for r in calls if r["defect_type"] == "fiducial")
    for dtype, cnt in by_type.items():
        if not cnt:
            continue
        rate = cnt / n_boards
        if dtype == "fiducial":
            lv, symptom = _level(rate, rc["fiducial_rate"]), "fiducial_fail_high"
        else:
            lv, symptom = _level(rate, rc["defect_rate"]), f"defect_{dtype}_high"
        if lv:
            findings.append(Finding(mid, "result", symptom, lv,
                                    f"{names.get(dtype, dtype)} 每板 {rate:.1%} ({cnt} 筆)", rate))

    # 同元件同缺陷重複發生
    repeats = Counter((r.get("component") or "?", r["defect_type"]) for r in real)
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
