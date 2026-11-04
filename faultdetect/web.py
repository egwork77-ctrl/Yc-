"""簡易網頁介面(僅用標準函式庫)。"""
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from urllib.parse import parse_qs, urlparse

from . import detector, engine

PAGE = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Discovery 8 預知保養</title><style>
body{font-family:system-ui,sans-serif;max-width:900px;margin:auto;padding:16px;background:#f6f7f9;color:#222}
textarea{width:100%;height:160px;font-family:monospace}
.card{background:#fff;border-radius:8px;padding:12px 16px;margin:12px 0;box-shadow:0 1px 3px #0002}
td{padding:2px 10px}.alarm{border-left:6px solid #d33}.warn{border-left:6px solid #e9a400}.ok{border-left:6px solid #2a2}
button{padding:8px 16px;font-size:15px}small{color:#666}
</style></head><body>
<h1>AOI 機台預知保養與故障排除</h1>
<div class="card"><p>機台類型:<select id="profile"><option value="discovery8">Orbotech Discovery 8(裸板 AOI)</option><option value="aoi">SMT AOI</option><option value="generic">一般機台</option></select>
<small>(AOI 檢測結果 CSV 會自動辨識)</small></p>
<p>上傳 CSV 或直接貼上內容:</p>
<input type="file" id="file" accept=".csv"><br><br>
<textarea id="csv" placeholder="timestamp,machine_id,temperature,..."></textarea><br>
<p>保養紀錄 CSV(預知保養用,可空白;欄位:date, machine_id, item):</p>
<textarea id="log" style="height:80px" placeholder="date,machine_id,item"></textarea><br>
<button onclick="predict()">🔧 預知保養</button> <button onclick="run()">即時故障診斷</button></div>
<div id="out"></div>
<script>
const L={alarm:'🔴 警報',warn:'🟡 警告',ok:'🟢 正常',info:'ℹ️ 資訊'};
document.getElementById('file').onchange=e=>{const r=new FileReader();
 r.onload=()=>document.getElementById('csv').value=r.result;r.readAsText(e.target.files[0]);};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const P={overdue:'⛔ 逾期',alarm:'🔴 緊急',warn:'🟡 近期',info:'🔵 規劃',ok:'🟢 正常'};
const dd=d=>d==null?'—':(d<=0?'現在':d+' 天');
async function predict(){
 const res=await fetch('/api/predict',{method:'POST',body:JSON.stringify({profile:document.getElementById('profile').value,
  csv:document.getElementById('csv').value,log:document.getElementById('log').value})});
 const data=await res.json(); const out=document.getElementById('out');
 if(data.error){out.innerHTML='<div class="card alarm">'+esc(data.error)+'</div>';return;}
 const cls=l=>({overdue:'alarm',alarm:'alarm',warn:'warn'}[l]||'ok');
 out.innerHTML=data.map(m=>`<div class="card ${cls(m.level)}"><h2>機台 ${esc(m.machine_id)} — 健康度 ${m.health}
 <meter min="0" max="100" low="60" high="80" optimum="100" value="${m.health}"></meter></h2><small>資料至 ${esc(m.as_of)}</small>
 <h3>保養待辦</h3><ul>${m.tasks.map(t=>`<li>${P[t.level]} [${esc(t.type)}] ${esc(t.item)} → ${esc(t.action)}(期限 ${dd(t.due_days)})</li>`).join('')||'<li>無</li>'}</ul>
 <h3>感測趨勢</h3><table>${m.predictions.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.current}</td>
 <td>${p.r2>=0.5?(p.slope_per_day>0?'+':'')+p.slope_per_day+'/天':'穩定'}</td><td>健康 ${p.health}</td></tr>`).join('')}</table>
 ${m.predictions.filter(p=>p.faults.length).map(p=>`<h3>▶ ${esc(p.name)}:${esc(p.faults[0].name)}</h3>
 <ol>${p.faults[0].steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol>`).join('')}</div>`).join('');
}
async function run(){
 const res=await fetch('/api/analyze?profile='+document.getElementById('profile').value,{method:'POST',body:document.getElementById('csv').value});
 const data=await res.json(); const out=document.getElementById('out');
 if(data.error){out.innerHTML='<div class="card alarm">'+esc(data.error)+'</div>';return;}
 out.innerHTML=data.map(m=>`<div class="card ${m.status}"><h2>機台 ${esc(m.machine_id)} — ${L[m.status]}</h2>
 <ul>${m.findings.map(f=>`<li>${L[f.level]} ${esc(f.message)}</li>`).join('')}</ul>
 ${m.diagnosis.slice(0,3).map(d=>`<h3>${d.category?'['+esc(d.category)+'] ':''}${esc(d.name)} <small>信心 ${Math.round(d.confidence*100)}%</small></h3>
 <ol>${d.steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol>`).join('')}</div>`).join('');
}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE, "text/html")
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path not in ("/api/analyze", "/api/predict"):
            return self._send(404, "not found", "text/plain")
        length = int(self.headers.get("Content-Length", 0))
        if length > 20_000_000:
            return self._send(413, json.dumps({"error": "檔案過大"}), "application/json")
        text = self.rfile.read(length).decode("utf-8-sig", errors="replace")
        if url.path == "/api/predict":
            return self._predict(text)
        try:
            profile = parse_qs(url.query).get("profile", ["generic"])[0]
            if profile not in detector.PROFILES:
                raise ValueError(f"未知機台類型 {profile}")
            report = engine.run(io.StringIO(text), profile)
            self._send(200, json.dumps(report, ensure_ascii=False), "application/json")
        except Exception as e:  # noqa: BLE001
            self._send(400, json.dumps({"error": f"解析失敗:{e}"}, ensure_ascii=False), "application/json")

    def _predict(self, text):
        from . import predict
        try:
            body = json.loads(text)
            profile = body.get("profile", "discovery8")
            if profile not in detector.PROFILES:
                raise ValueError(f"未知機台類型 {profile}")
            log = io.StringIO(body["log"]) if body.get("log", "").strip() else None
            report = predict.run(io.StringIO(body.get("csv", "")), profile, log)
            self._send(200, json.dumps(report, ensure_ascii=False), "application/json")
        except Exception as e:  # noqa: BLE001
            self._send(400, json.dumps({"error": f"分析失敗:{e}"}, ensure_ascii=False), "application/json")


def serve(host="127.0.0.1", port=8000):
    print(f"網頁介面:http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
