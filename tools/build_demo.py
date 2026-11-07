"""產生「展示版」單一 HTML:內嵌目前資料的快照,不需要伺服器,可發布成網頁在 iPad 上瀏覽。

  python tools/build_demo.py samples demo.html

展示版可瀏覽所有畫面與 3D;登錄 / 存檔需要在筆電執行完整版。
"""
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from faultdetect import web  # noqa: E402
from faultdetect.live import Live  # noqa: E402

THREE = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
ORBIT = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"


def snapshot(data_dir):
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(data_dir, tmp, dirs_exist_ok=True)
    if (tmp / "et_points_sample.csv").exists() and not (tmp / "et_points.csv").exists():
        shutil.copy(tmp / "et_points_sample.csv", tmp / "et_points.csv")
    app = web.App(tmp)
    # 範例監看場次與維修紀錄,讓「紀錄」頁有內容可看
    if not app.live.sessions():
        t = datetime(2026, 1, 30, 9, 0)
        clock = lambda: t  # noqa: E731
        live = Live(tmp, app.meta, app.profile_of, clock)
        s = live.start("ET1", "範例")
        for ev in ("contact_fail", "contact_fail", "false_fail", "contact_fail"):
            live.add_event(s["session_id"], ev)
        live.add_event(s["session_id"], "note", "治具 FX-A 左下角 P-0456 反覆 Open")
        t = datetime(2026, 1, 30, 10, 30)
        live.end(s["session_id"], "清潔針床並更換 P-0456 後恢復(範例)")
    if not app.repairs():
        app.add_repair({"machine_id": "ET1", "fault_id": "et_bed_sop", "fault_name": "針床假點完整排除 SOP",
                        "result": "已解決", "solved_step": 11, "steps_done": 11, "technician": "範例",
                        "note": "更換 P-0456、P-1203(範例紀錄)"})
    d = {}
    ov = app.overview()
    d["/api/overview"] = ov
    for p in sorted({m["profile"] for m in ov["machines"]}):
        d[f"/api/faults?profile={p}"] = web.diagnosis.load_kb(profile=p)
    for m in ov["machines"]:
        mid = m["machine_id"]
        d[f"/api/vibration?machine_id={mid}"] = web.vibration.analyze(tmp / "vibration" / mid) or {}
        d[f"/api/form?machine_id={mid}"] = app.form(mid)
        d[f"/api/live/events?machine_id={mid}"] = app.live.events_config(mid)
        d[f"/api/live/active?machine_id={mid}"] = {}
    d["/api/repairs"] = app.repairs()
    d["/api/spares"] = app.spares()
    d["/api/et"] = app.et_report()
    d["/api/settings"] = app.settings()
    d["/api/live/sessions"] = app.live.sessions()
    for s in app.live.sessions():
        d[f"/api/live/report?session_id={s['session_id']}"] = app.live.report(s["session_id"])
    shutil.rmtree(tmp, ignore_errors=True)
    return d


SHIM = r"""<script>
/* 展示版:用內嵌的資料快照回應 API,寫入動作不會儲存 */
(function(){const DATA=__DATA__;const _f=window.fetch;
window.fetch=async(url,opt)=>{const u=new URL(url,location.href);
 if(!u.pathname.startsWith('/api/'))return _f(url,opt);
 const q=[...u.searchParams.entries()].map(([k,v])=>k+'='+v).join('&');const key=u.pathname+(q?'?'+q:'');
 const json=(o,s)=>new Response(JSON.stringify(o),{status:s||200,headers:{'Content-Type':'application/json'}});
 if((opt&&opt.method||'GET').toUpperCase()!=='GET')return json({error:'展示版不會儲存資料。要登錄、存檔,請在筆電執行完整版(雙擊 start_windows.bat)。'},400);
 if(key in DATA)return json(DATA[key]);if(u.pathname in DATA)return json(DATA[u.pathname]);
 return json({error:'展示版沒有這項資料'},404);};})();
</script>"""


def build(data_dir, out):
    page = web.PAGE
    data = json.dumps(snapshot(data_dir), ensure_ascii=False).replace("</", "<\\/")
    m3d = (ROOT / "faultdetect" / "static" / "model3d.js").read_text(encoding="utf-8")
    head, body = page.split("</head><body>", 1)
    style = re.search(r"<style>(.*)</style>", head, re.S).group(1)
    # 主題:依 artifact 規範加上 data-theme 切換與 color-scheme;邊距加上 safe-area
    dark = re.search(r"@media \(prefers-color-scheme:dark\)\{:root\{(.*?)\}\}", style).group(1)
    style = style.replace(f"@media (prefers-color-scheme:dark){{:root{{{dark}}}}}",
                          f"@media (prefers-color-scheme:dark){{:root:not([data-theme=\"light\"]){{{dark};color-scheme:dark}}}}"
                          f":root[data-theme=\"dark\"]{{{dark};color-scheme:dark}}")
    style = style.replace("header{padding:14px 16px;", "header{padding-block:14px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));")
    style = style.replace("main{padding:0 16px 96px;", "main{padding-block:0 96px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));")
    style += ".demo{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;background:var(--amber);color:#fff;margin-left:8px;vertical-align:middle}"
    body = body.replace('<header id="title">AOI 現場排除</header>',
                        '<header id="title">AOI 現場排除<span class="demo">展示版</span>'
                        '<div class="muted" style="font-size:13px;font-weight:400;margin-top:4px">範例資料,可瀏覽所有畫面;登錄、存檔請在筆電執行完整版</div></header>')
    body = body.replace("try{await loadJS('/static/three.min.js');await loadJS('/static/OrbitControls.js');await loadJS('/static/model3d.js');}",
                        "try{if(!window.AOI3D)throw Error('3D 未載入');}")
    body = body.replace("</body></html>", "")
    html = ("<title>AOI 現場監測</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n"
            f"<style>{style}</style>\n<script src=\"{THREE}\"></script>\n<script src=\"{ORBIT}\"></script>\n"
            f"<script>{m3d}</script>\n" + SHIM.replace("__DATA__", data) + "\n" + body)
    Path(out).write_text(html, encoding="utf-8")
    return len(html.encode("utf-8"))


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "samples")
    out = sys.argv[2] if len(sys.argv) > 2 else "demo.html"
    print(f"已產生 {out}({build(src, out) / 1e6:.1f} MB)")
