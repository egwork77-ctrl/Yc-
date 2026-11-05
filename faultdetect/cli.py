"""命令列介面。

  python -m faultdetect predict samples/d8_history.csv --log samples/d8_maintenance_log.csv
  python -m faultdetect analyze samples/sensors.csv [--profile aoi] [--json]
  python -m faultdetect diagnose temperature_high vibration_high [--profile aoi]
  python -m faultdetect symptoms [--profile aoi]
  python -m faultdetect serve [--port 8000]
  python -m faultdetect sample samples/aoi_results.csv --type aoi-results

analyze 會自動判斷 CSV 是感測資料或 AOI 檢測結果。
"""
import argparse
import json
import sys

from . import detector, diagnosis, engine

ICON = {"alarm": "🔴 警報", "warn": "🟡 警告", "ok": "🟢 正常", "info": "ℹ️ 資訊"}


def print_report(report):
    for m in report:
        print(f"\n=== 機台 {m['machine_id']}  {ICON[m['status']]} ===")
        for f in m["findings"]:
            print(f"  [{ICON[f['level']]}] {f['message']}")
        for i, d in enumerate(m["diagnosis"][:3], 1):
            cat = f"[{d['category']}] " if d.get("category") else ""
            print(f"\n  可能原因 {i}: {cat}{d['name']}  (信心 {d['confidence']:.0%})")
            for n, step in enumerate(d["steps"], 1):
                print(f"     {n}. {step}")


PM_ICON = {"overdue": "⛔ 逾期", "alarm": "🔴 緊急", "warn": "🟡 近期", "info": "🔵 規劃", "ok": "🟢 正常"}


PART_ICON = {"order_now": "🛒 立即備料", "order_soon": "📋 準備備料", "stocked": "📦 有庫存", "ok": "🟢 正常"}


def _order(d):
    return "—" if d is None else ("已過(立即下單)" if d <= 0 else f"{d:g} 天內")


def _days(d):
    return "—" if d is None else ("現在" if d <= 0 else f"{d:g} 天")


def print_predict(report):
    for m in report:
        bar = "█" * (m["health"] // 10) + "░" * (10 - m["health"] // 10)
        print(f"\n=== 機台 {m['machine_id']}  健康度 {bar} {m['health']}  {PM_ICON[m['level']]}"
              f"  (資料至 {m['as_of']}) ===")
        print("  感測趨勢:")
        for p in m["predictions"]:
            eta = p["eta"].get("warn", p["eta"].get("alarm"))
            trend = f"{p['slope_per_day']:+g}/天" if p["r2"] >= 0.5 else "穩定"
            print(f"    {p['name']:<14} 現值 {p['current']:<8.4g} 趨勢 {trend:<12} 健康 {p['health']:>3}"
                  f"  預計超標 {_days(eta)}")
        if m.get("parts"):
            print("  零件健康度:")
            for p in m["parts"]:
                if p["due_days"] is None:
                    continue
                print(f"    {PART_ICON[p['status']]} {p['name']:<16} 健康 {p['health']:>3}  預計 {_days(p['due_days'])} 需更換"
                      f"  交期 {p['lead_days']} 天  庫存 {p['stock']}  最晚下單 {'不需(有庫存)' if p['status'] == 'stocked' else _order(p['order_by_days'])}")
        if m["tasks"]:
            print("  保養待辦:")
            for t in m["tasks"]:
                print(f"    {PM_ICON[t['level']]} [{t['type']}] {t['item']}  →  {t['action']}"
                      f"  (期限 {_days(t['due_days'])})")
        for p in m["predictions"]:
            if p["faults"]:
                f = p["faults"][0]
                print(f"\n  ▶ {p['name']} 建議保養:{f['name']}")
                for n, step in enumerate(f["steps"], 1):
                    print(f"     {n}. {step}")


def all_symptoms(profile="generic"):
    return sorted({s for f in diagnosis.load_kb(profile=profile) for s in f["symptoms"]})


def main(argv=None):
    p = argparse.ArgumentParser(prog="faultdetect", description="機台故障偵測與排除")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="分析感測器 CSV")
    a.add_argument("csv")
    a.add_argument("--profile", choices=detector.PROFILES, default="generic", help="機台類型")
    a.add_argument("--config", help="自訂門檻設定檔")
    a.add_argument("--json", action="store_true", help="輸出 JSON")

    pr = sub.add_parser("predict", help="預知保養:預測何時超標 + 定期保養到期")
    pr.add_argument("csv", help="含 timestamp 的歷史感測資料")
    pr.add_argument("--log", help="保養紀錄 CSV (date, machine_id, item)")
    pr.add_argument("--profile", choices=detector.PROFILES, default="discovery8")
    pr.add_argument("--spares", help="備品庫存 CSV (machine_id, part_id, part_no, stock, lead_days)")
    pr.add_argument("--config")
    pr.add_argument("--json", action="store_true")

    d = sub.add_parser("diagnose", help="直接輸入症狀診斷")
    d.add_argument("symptoms", nargs="+")
    d.add_argument("--profile", choices=detector.PROFILES, default="generic")

    y = sub.add_parser("symptoms", help="列出可用症狀代碼")
    y.add_argument("--profile", choices=detector.PROFILES, default="generic")

    s = sub.add_parser("serve", help="啟動現場排除介面(--host 0.0.0.0 讓 iPad 連線)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--data", default="samples", help="資料目錄(含 machines.json)")

    g = sub.add_parser("sample", help="產生範例資料")
    g.add_argument("out")
    g.add_argument("--type", choices=["generic", "aoi", "aoi-results", "aoi-history", "maintenance-log",
                                       "d8-history", "d8-log", "d8-results", "f22-history", "f22-log", "vrs-history", "vrs-log"], default="generic")

    args = p.parse_args(argv)

    if args.cmd == "analyze":
        report = engine.run(args.csv, args.profile, args.config)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_report(report)
        return 2 if any(m["status"] == "alarm" for m in report) else 0

    if args.cmd == "predict":
        from . import predict
        report = predict.run(args.csv, args.profile, args.log, args.config, args.spares)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_predict(report)
        return 2 if any(m["level"] in ("overdue", "alarm") for m in report) else 0

    if args.cmd == "diagnose":
        unknown = set(args.symptoms) - set(all_symptoms(args.profile))
        if unknown:
            print(f"未知症狀: {', '.join(sorted(unknown))}(用 symptoms 指令查詢)", file=sys.stderr)
        results = diagnosis.diagnose(args.symptoms, diagnosis.load_kb(profile=args.profile))
        if not results:
            print("查無符合的故障模式")
        print_report([{"machine_id": "-", "status": "warn", "findings": [], "diagnosis": results}])
        return 0

    if args.cmd == "symptoms":
        print("\n".join(all_symptoms(args.profile)))
        return 0

    if args.cmd == "serve":
        from .web import serve
        serve(args.host, args.port, args.data)
        return 0

    if args.cmd == "sample":
        from .sample import SAMPLES
        SAMPLES[args.type](args.out)
        print(f"已產生 {args.out}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
