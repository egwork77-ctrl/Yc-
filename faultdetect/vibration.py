"""振動頻譜分析:把振動感測器的時域資料轉成頻譜,與基準比較找出異常峰值。

資料放在 <資料目錄>/vibration/<machine_id>/<YYYYMMDD-HHMM>_<位置>.csv
CSV 欄位:t(秒), accel(g 或 mm/s²);取樣率由 t 推算。最早一筆視為基準(新機或保養後)。
"""
import cmath
import csv
import math
from pathlib import Path

WARN_RMS, ALARM_RMS = 1.5, 2.0          # 整體 RMS 相對基準倍數
PEAK_RATIO, MIN_PEAK_SHARE = 3.0, 0.1   # 新峰值:比基準同頻率高 3 倍,且佔最大峰 10% 以上


def fft(x):
    """遞迴 radix-2 FFT(長度需為 2 的次方)。"""
    n = len(x)
    if n == 1:
        return [complex(x[0])]
    even, odd = fft(x[0::2]), fft(x[1::2])
    out = [0j] * n
    for k in range(n // 2):
        t = cmath.exp(-2j * math.pi * k / n) * odd[k]
        out[k], out[k + n // 2] = even[k] + t, even[k] - t
    return out


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [(float(r["t"]), float(r["accel"])) for r in csv.DictReader(f) if r.get("t") and r.get("accel")]
    if len(rows) < 64:
        raise ValueError(f"{Path(path).name} 資料點太少")
    fs = (len(rows) - 1) / (rows[-1][0] - rows[0][0])
    return [v for _, v in rows], fs


def spectrum(values, fs):
    n = 1 << (len(values).bit_length() - 1)          # 取 2 的次方長度
    x = values[:n]
    mean = sum(x) / n
    win = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]   # Hann 窗
    X = fft([(v - mean) * w for v, w in zip(x, win)])
    amp = [2 * abs(c) / (n * 0.5) for c in X[: n // 2]]
    freqs = [i * fs / n for i in range(n // 2)]
    rms = math.sqrt(sum((v - mean) ** 2 for v in x) / n)
    return freqs, amp, rms


def peaks(freqs, amp, top=5):
    cand = [i for i in range(2, len(amp) - 1) if amp[i] >= amp[i - 1] and amp[i] >= amp[i + 1]]
    cand.sort(key=lambda i: -amp[i])
    out = []
    for i in cand:
        if all(abs(freqs[i] - p["freq"]) > 3 * freqs[1] for p in out):
            out.append({"freq": round(freqs[i], 1), "amp": round(amp[i], 4), "i": i})
        if len(out) >= top:
            break
    return out


def _downsample(freqs, amp, points=300):
    step = max(1, len(amp) // points)
    return [[round(freqs[i], 1), round(max(amp[i:i + step]), 5)] for i in range(0, len(amp), step)]


def analyze(machine_dir):
    files = sorted(Path(machine_dir).glob("*.csv")) if Path(machine_dir).is_dir() else []
    if not files:
        return None
    base_v, base_fs = load(files[0])
    last_v, last_fs = load(files[-1])
    bf, ba, brms = spectrum(base_v, base_fs)
    lf, la, lrms = spectrum(last_v, last_fs)
    lp = peaks(lf, la)
    ratio = lrms / brms if brms else 1.0
    findings, level = [], "ok"
    if ratio > ALARM_RMS:
        level = "alarm"
    elif ratio > WARN_RMS:
        level = "warn"
    if level != "ok":
        findings.append(f"整體振動 RMS 為基準的 {ratio:.1f} 倍")
    top = lp[0]["amp"] if lp else 0
    for p in lp:
        j = min(range(len(bf)), key=lambda i: abs(bf[i] - p["freq"]))
        b = max(ba[max(0, j - 2): j + 3])
        p["vs_base"] = round(p["amp"] / b, 1) if b else None
        if p["amp"] >= top * MIN_PEAK_SHARE and b and p["amp"] / b >= PEAK_RATIO:
            findings.append(f"{p['freq']:g} Hz 峰值為基準的 {p['amp'] / b:.1f} 倍(可能軸承 / 螺桿磨損、鬆動或共振)")
            level = "alarm" if level == "alarm" or p["amp"] == top else "warn"
        p.pop("i")
    return {"captures": [f.stem for f in files], "baseline": files[0].stem, "latest": files[-1].stem,
            "rms_base": round(brms, 4), "rms_latest": round(lrms, 4), "rms_ratio": round(ratio, 2),
            "level": level, "findings": findings, "peaks": lp,
            "base_curve": _downsample(bf, ba), "latest_curve": _downsample(lf, la),
            "fmax": round(lf[-1], 1)}


def write_sample(machine_dir, kind="worn", seed=5, fs=2000, n=2048):
    """產生模擬資料:基準 + 30 天後。kind='worn' 會出現 157 Hz 軸承峰值與整體上升。"""
    import random
    rnd = random.Random(seed)
    d = Path(machine_dir)
    d.mkdir(parents=True, exist_ok=True)
    for name, wear in (("20260101-0900_X軸馬達", 0.0), ("20260130-0900_X軸馬達", 1.0 if kind == "worn" else 0.0)):
        with open(d / f"{name}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t", "accel"])
            for i in range(n):
                t = i / fs
                v = (0.30 * math.sin(2 * math.pi * 30 * t) + 0.10 * math.sin(2 * math.pi * 60 * t)
                     + 0.06 * math.sin(2 * math.pi * 410 * t)                       # 結構共振
                     + wear * (0.35 * math.sin(2 * math.pi * 157 * t) + 0.12 * math.sin(2 * math.pi * 314 * t))
                     + rnd.gauss(0, 0.03 + 0.04 * wear))
                w.writerow([f"{t:.5f}", f"{v:.5f}"])
