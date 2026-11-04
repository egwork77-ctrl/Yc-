"""命令列介面。

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

    d = sub.add_parser("diagnose", help="直接輸入症狀診斷")
    d.add_argument("symptoms", nargs="+")
    d.add_argument("--profile", choices=detector.PROFILES, default="generic")

    y = sub.add_parser("symptoms", help="列出可用症狀代碼")
    y.add_argument("--profile", choices=detector.PROFILES, default="generic")

    s = sub.add_parser("serve", help="啟動網頁介面")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    g = sub.add_parser("sample", help="產生範例資料")
    g.add_argument("out")
    g.add_argument("--type", choices=["generic", "aoi", "aoi-results"], default="generic")

    args = p.parse_args(argv)

    if args.cmd == "analyze":
        report = engine.run(args.csv, args.profile, args.config)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_report(report)
        return 2 if any(m["status"] == "alarm" for m in report) else 0

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
        serve(args.host, args.port)
        return 0

    if args.cmd == "sample":
        from .sample import SAMPLES
        SAMPLES[args.type](args.out)
        print(f"已產生 {args.out}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
