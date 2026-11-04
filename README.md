# 機台故障偵測與排除系統

讀取機台感測資料 → 偵測異常 → 比對知識庫推論故障原因 → 提供排除步驟。
純 Python 標準函式庫(3.10+),免安裝套件。

## 快速開始

```bash
python -m faultdetect sample samples/sensors.csv   # 產生範例資料
python -m faultdetect analyze samples/sensors.csv  # 分析(--json 輸出 JSON)
python -m faultdetect diagnose vibration_high temperature_high  # 直接用症狀診斷
python -m faultdetect symptoms                     # 列出症狀代碼
python -m faultdetect serve --port 8000            # 網頁介面 http://127.0.0.1:8000
```

`analyze` 有警報時回傳碼為 2,可接排程或監控腳本。

## 資料格式(CSV)

`timestamp, machine_id, temperature, vibration, current, pressure, rpm`

## 偵測方法

| 方法 | 說明 |
|---|---|
| 門檻值 | 最新值超過 warn / alarm 上下限 |
| 離群值 | z-score 超過 3 |
| 趨勢 | 最近 N 筆斜率過大(如溫度持續上升) |
| 不穩定 | 變異係數過大(如轉速、電流波動) |
| 缺值 | 缺值比例 > 20%,判斷感測器異常 |

## 客製化

- `faultdetect/config.json`:各感測器門檻值
- `faultdetect/knowledge_base.json`:故障模式、症狀權重、排除步驟(可依自家機台新增)

## 測試

```bash
python -m unittest discover tests
```
