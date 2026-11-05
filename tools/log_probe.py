"""AOI 機台 Log / 校正紀錄探勘工具(唯讀)。

在「筆電」上執行,掃描機台電腦的網路分享資料夾(或複製出來的資料夾),
找出可能有用的 Log、校正、警報、統計檔,產生報告給開發者判斷怎麼自動擷取。

  python tools/log_probe.py "\\\\AOI-PC\\D$" "\\\\AOI-PC\\Logs" --days 60 --out probe_DIS8-1

⚠️ 本工具只讀取檔案,不修改、不刪除、不在機台上安裝任何東西。
⚠️ 送出報告前請先看過內容,移除客戶料號等機密。
"""
import argparse
import csv
import os
import sys
import time
from collections import Counter
from pathlib import Path

TEXT_EXT = {".log", ".txt", ".csv", ".xml", ".ini", ".cfg", ".cal", ".dat", ".json", ".lst", ".rpt", ".his", ".evt"}
KEYWORDS = ("log", "cal", "lamp", "light", "illum", "vacuum", "vac", "pressure", "air", "alarm", "error", "err",
            "event", "hist", "stat", "maint", "diag", "focus", "stage", "motor", "temp", "health", "fiducial",
            "regist", "verify", "vrs", "report")
SKIP_DIRS = {"windows", "program files", "program files (x86)", "$recycle.bin", "system volume information",
             "programdata\\microsoft", "winnt", "temp", "tmp"}


def score(path, size, age_days):
    name = path.name.lower()
    s = 0
    if path.suffix.lower() in TEXT_EXT:
        s += 3
    s += sum(2 for k in KEYWORDS if k in name)
    s += sum(1 for k in KEYWORDS if k in str(path.parent).lower())
    if age_days <= 7:
        s += 3
    elif age_days <= 30:
        s += 1
    if size == 0 or size > 200_000_000:
        s -= 5
    return s


def head(path, n=25):
    try:
        with open(path, "rb") as f:
            raw = f.read(8192)
    except OSError as e:
        return f"(無法讀取:{e})"
    if b"\x00" in raw[:1024]:
        return "(二進位檔,略過內容)"
    for enc in ("utf-8", "big5", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return "\n".join(text.splitlines()[:n])


def walk(roots, days, max_files):
    now = time.time()
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: print(f"  略過:{e}", file=sys.stderr)):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                p = Path(dirpath) / fn
                try:
                    st = p.stat()
                except OSError:
                    continue
                age = (now - st.st_mtime) / 86400
                if age > days:
                    continue
                yield p, st.st_size, age
                max_files -= 1
                if max_files <= 0:
                    print("  已達檔案數上限,停止掃描", file=sys.stderr)
                    return


def main(argv=None):
    ap = argparse.ArgumentParser(description="AOI 機台 Log 探勘(唯讀)")
    ap.add_argument("roots", nargs="+", help="要掃描的資料夾(可為網路路徑)")
    ap.add_argument("--days", type=int, default=60, help="只看最近 N 天有更新的檔案")
    ap.add_argument("--out", default="probe_report", help="報告輸出資料夾(在筆電上)")
    ap.add_argument("--top", type=int, default=40, help="擷取內容的候選檔數量")
    ap.add_argument("--max-files", type=int, default=200_000)
    a = ap.parse_args(argv)

    out = Path(a.out)
    for r in a.roots:
        if Path(r).resolve() in out.resolve().parents or Path(r).resolve() == out.resolve():
            sys.exit("輸出資料夾不能放在被掃描的路徑裡")
    out.mkdir(parents=True, exist_ok=True)

    files = list(walk(a.roots, a.days, a.max_files))
    rows = sorted(({"score": score(p, sz, age), "path": str(p), "size": sz, "age_days": round(age, 1),
                    "ext": p.suffix.lower()} for p, sz, age in files), key=lambda r: -r["score"])
    with open(out / "file_list.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["score", "path", "size", "age_days", "ext"])
        w.writeheader()
        w.writerows(rows)

    with open(out / "summary.txt", "w", encoding="utf-8") as f:
        f.write(f"掃描路徑:{a.roots}\n最近 {a.days} 天更新的檔案:{len(rows)} 個\n\n副檔名統計:\n")
        for ext, n in Counter(r["ext"] for r in rows).most_common(20):
            f.write(f"  {ext or '(無)'}: {n}\n")
        dirs = Counter(str(Path(r["path"]).parent) for r in rows)
        f.write("\n最常更新的資料夾(可能是 Log 所在):\n")
        for d, n in dirs.most_common(20):
            f.write(f"  {n:6d}  {d}\n")

    with open(out / "samples.txt", "w", encoding="utf-8") as f:
        for r in rows[: a.top]:
            f.write(f"\n{'=' * 80}\n{r['path']}  ({r['size']:,} bytes, {r['age_days']} 天前, 分數 {r['score']})\n{'-' * 80}\n")
            f.write(head(r["path"]) + "\n")

    print(f"完成:{len(rows)} 個檔案。報告在 {out.resolve()}")
    print("  summary.txt   概要(副檔名、最常更新的資料夾)")
    print("  file_list.csv 全部檔案清單(依可能性排序)")
    print("  samples.txt   前幾名候選檔的開頭內容")
    print("請先檢查內容沒有機密,再把整個資料夾傳給我。")


if __name__ == "__main__":
    main()
