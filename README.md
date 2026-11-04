# 機台故障偵測與排除系統

讀取機台感測資料 → 偵測異常 → 比對知識庫推論故障原因 → 提供排除步驟。
純 Python 標準函式庫(3.10+),免安裝套件。

支援機台類型(profile):`generic` 一般機台、`aoi` AOI 電路板自動光學檢測機。

## AOI 電路板檢測

兩種資料都可分析,`analyze` 會自動辨識:

1. **AOI 機台狀態**(`--profile aoi`)
   `timestamp, machine_id, light_intensity, focus_score, fiducial_score, temperature, conveyor_speed, cycle_time`
   → 光源老化、鏡頭失焦、Mark 點定位、輸送軌道、過熱
2. **AOI 檢測結果**(每筆缺陷一列,PASS 板一列)
   `timestamp, machine_id, board_id, result(PASS/NG), defect_type, component, verdict(real/false)`
   → 誤判率、不良率、缺陷類型、同位置重複不良,推論是 **AOI 本身問題**(程式過嚴、光源、鏡頭)
   還是 **上游製程問題**(印刷鋼板堵孔、印刷偏移、貼片吸嘴、回焊爐溫、上料錯誤)

缺陷代碼:`missing` 缺件、`shift` 偏移、`bridge` 橋接、`insufficient` 少錫、`excess` 多錫、
`tombstone` 立碑、`polarity` 極性反、`wrong` 錯件、`lifted` 翹腳、`fiducial` Mark 點失敗

```bash
python -m faultdetect sample samples/aoi_sensors.csv --type aoi
python -m faultdetect sample samples/aoi_results.csv --type aoi-results
python -m faultdetect analyze samples/aoi_sensors.csv --profile aoi
python -m faultdetect analyze samples/aoi_results.csv
```

## 快速開始(一般機台)

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

- `faultdetect/profiles/<類型>/config.json`:門檻值
- `faultdetect/profiles/<類型>/knowledge_base.json`:故障模式、症狀權重、排除步驟(可依自家機台新增)
- 新增機台類型:建立新資料夾並加入 `detector.PROFILES`

## 測試

```bash
python -m unittest discover tests
```
