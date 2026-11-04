"""統一入口:自動判斷 CSV 類型(感測資料 / AOI 檢測結果)並產生報告。"""
from . import aoi, detector, diagnosis


def run(source, profile="generic", config_path=None):
    rows = detector.read_rows(source)
    if not rows:
        raise ValueError("沒有資料")
    if aoi.is_results(rows):
        profile = "aoi"
        cfg = detector.load_config(config_path, profile)
        findings = aoi.analyze_results(rows, cfg)
    else:
        cfg = detector.load_config(config_path, profile)
        findings = detector.analyze(detector.group_rows(rows), cfg)
    return diagnosis.build_report(findings, diagnosis.load_kb(profile=profile))
