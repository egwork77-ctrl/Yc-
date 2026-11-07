# AOI 機台預知保養與故障排除系統

目前機台（共 17 台，銘牌資料在 `samples/machines.json`）：
- AOI：D83、D85（Orbotech Discovery 8800）、D88（Discovery 9000 L）→ `discovery8`
- AOI：F1、F2（Orbotech Fusion 22）→ `fusion22`
- VRS 缺陷複判站 ×6（Orbotech VeriSmart）→ `vrs`
- 電測 ET1–ET6（Mania / Gardien PRECISE 治具式：200、400、M8 AUTO）→ `et_precise`

機台頁會顯示銘牌資料（型號、序號、設備 No.、卡號、進廠日期、機齡）；
`calibration.next` 到期或逾期時，會自動列入待辦。

**在故障發生前就預警。** 從機台感測資料的長期趨勢，預測幾天後會超標，
再搭配定期保養週期（天數、運轉時數、過板數），列出保養待辦和處理步驟。

## 展示版（不需要筆電）

`python tools/build_demo.py samples demo.html` 會產生單一 HTML 檔，內含目前資料的快照，發布成網頁後可直接在 iPad 瀏覽所有畫面和 3D。
展示版只能看；登錄、存檔需要執行完整版。

## 現場使用：筆電 + iPad

**最簡單的方式**：在筆電上雙擊 `start_windows.bat`（Mac 用 `start_mac.command`），畫面會顯示 iPad 要輸入的網址。
需要 Python 3.10 以上（python.org 下載，Windows 安裝時要勾選「Add python.exe to PATH」）。


```bash
python -m faultdetect serve --host 0.0.0.0 --data samples
```
筆電執行後會顯示網址，iPad／手機連同一個 Wi-Fi，用 Safari 開啟（可「加入主畫面」當 App 使用）。

| 頁面 | 功能 |
|---|---|
| 📊 總覽 | 5 台機台健康度，每 60 秒自動重新讀取資料 |
| 📦 備料 | 各零件健康度、預計更換日、交期、庫存、**最晚下單日**；庫存 +/− 管理 |
| 🔧 排除故障 | 選機台 → 選問題（⭐ 為系統推薦）→ 一步一步排除 → 解決或升級處理並記錄 |
| 📝 紀錄 | 登錄保養／更換（重新計算壽命、自動扣庫存）＋維修紀錄 |
| 📤 上傳分析 | 臨時上傳 CSV 分析 |
| ⚙️ 設定 | 直接在 iPad 修改機台資料（型號、序號、進廠日期）、停機狀態、外部校正日期、聯絡窗口（會寫回 `machines.json`） |

資料目錄設定在 `machines.json`：資料來源、機台清單、聯絡窗口、備品檔 `spares.csv`
（machine_id(`*`=全部), part_id, part_no, stock, lead_days）。
要做到「隨時監測」，就讓機台資料定期匯出（或由程式寫入）到這個目錄，網頁會自動更新。

**備料邏輯**：零件健康度 = min(相關感測健康度, 壽命剩餘%)；
最晚下單日 = 預計更換日 − 交期 − 安全天數（預設 3 天）。零件定義在 profile 的 `parts`。

## 電測假點分析

上傳不良點紀錄（「上傳分析 → 即時故障診斷」或 `python -m faultdetect analyze samples/et_points_sample.csv`），會自動判斷問題出在哪裡：

| 判斷結果 | 代表的問題 |
|---|---|
| 同一副治具、固定針位重複假點 | 這幾支針髒污／磨耗／卡針，會列出針號 |
| 同一副治具在多台機台都假點高 | **針床治具本身**（層板孔磨耗、針長不一） |
| 同一台機台換治具還是假點高 | **機台**（格點彈簧針、開關卡、壓合） |
| 假點集中在某一側 | 對位偏移，或壓合不平行 |
| 分散在很多針、沒有固定位置 | 針頭普遍髒污，或板面污染 |

CSV 欄位：`timestamp, machine_id, fixture_id, board_id, point, x, y, fail_type, retest`（retest=pass 代表假點）

**現場登錄（iPad「📍 假點」頁）**：選電測機台和治具，點選假點在治具上的位置（5×4 格），輸入針號後送出；每批結束再登錄測試片數。
資料存在 `<資料目錄>/et_points.csv`，頁面下方會即時顯示分析結果、各治具假點排行和位置分布圖。

## 3D 機構模型與振動頻譜

- **✨ 數位孿生（預設畫面）**：深色背景、金色線框加藍色半透明機台；零件拉出標示線，顯示健康度和預計更換天數；左上是機台資訊面板，右側是感測儀表；可以切換全螢幕。（螢幕版，不是 AR 擴增實境。）
- 機台頁的 3D 另有四種顯示：👁 透視／外觀／⚙️ 機構（床台、龍門、線軌、滾珠螺桿、伺服馬達、掃描頭）／▦ 網格（類有限元素外觀，**僅為視覺效果，不是 FEA 計算**），並可播放 XY 掃描動作。
- 📈 振動頻譜：在 XY 平台馬達或軸承座裝振動感測器，把量測檔放到 `<資料目錄>/vibration/<機台ID>/<日期時間>_<位置>.csv`（欄位 `t, accel`）。
  最早一筆當作基準，系統會比較最新一筆的整體 RMS，以及新出現的峰值（軸承／螺桿磨損、鬆動、共振）。

## 取得機台資料

1. **先手動點檢**：每天在 iPad 上「📋 點檢」輸入一次，約兩週後就能開始預測。
2. **找出可自動擷取的 Log**（唯讀，不修改機台）：
   - 機台有開網路分享時，在筆電執行：
     `python tools/log_probe.py "\\機台電腦\分享資料夾" --days 60 --out probe_D83`
   - 舊版 Windows、沒有網路分享時：把 `tools/list_files.bat` 放進 USB，在機台電腦上點兩下執行
   - 執行前請先確認公司 IT／設備課的規定，以及原廠保固條款
3. 找到 Log 後，在 `machines.json` 的機台加入 `live_log`（路徑＋正規表示式對應事件），監看時就會自動記錄（🤖 標示）：
   ```json
   "live_log": {"path": "\\\\AOI-PC\\Logs\\event.log",
                "patterns": [{"regex": "Registration failed", "event": "registration_fail"}]}
   ```
4. 把報告傳給開發者，就能寫出自動擷取程式，做到真正的即時監測。

## 預知保養（主要功能）

```bash
python -m faultdetect predict samples/d8_history.csv --log samples/d8_maintenance_log.csv
python -m faultdetect analyze samples/d8_results.csv --profile discovery8   # 檢測結果 / VRS 複判分析
```

Discovery 8 監測項目：照明亮度、影像清晰度、平台真空、氣源壓力、對位分數、XY 定位誤差、
光學室溫度、掃描時間，以及累計計數 `run_hours`、`lamp_hours`、`panel_count`。
裸板缺陷代碼：`short` `open` `nick` `protrusion` `pinhole` `island` `narrow` `wide` `spacing` `registration`

> ⚠️ `profiles/discovery8/config.json` 中的門檻與保養週期都是**暫定值**，
> 請依原廠手冊 / KLA 服務建議與機台實際基準值調整。

- **趨勢預測**：用最近 14 天的資料做線性回歸，算出距離警告／警報門檻還有幾天（R² 太低時判定為穩定，不做預測）
- **健康度 0–100**：從基準值到警報值，還剩多少空間
- **定期保養**：依天數、`run_hours`、`board_count` 計算下次到期日（耗用速度由歷史資料推算）
- **分級**：⛔ 逾期 / 🔴 緊急（≤3 天）/ 🟡 近期（≤14 天）/ 🔵 規劃
- 有警報或逾期時，回傳碼為 2，可以接排程每天自動執行

歷史資料 CSV：`timestamp, machine_id, light_intensity, focus_score, fiducial_score, temperature, conveyor_speed, cycle_time, run_hours, board_count`
保養紀錄 CSV：`date, machine_id, item[, run_hours, board_count]`（item 名稱需和 config 的 `maintenance` 項目一致）
保養週期在 `faultdetect/profiles/aoi/config.json` 的 `maintenance` 修改。

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
