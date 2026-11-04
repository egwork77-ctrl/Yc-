"""現場排除介面:筆電執行,iPad / 手機用瀏覽器連線(僅用標準函式庫)。

  python -m faultdetect serve --host 0.0.0.0 --data samples
  iPad 開啟 http://<筆電 IP>:8000
"""
import csv
import io
import json
import socket
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import detector, diagnosis, engine, predict

REPAIR_FIELDS = ["time", "machine_id", "fault_id", "fault_name", "result", "solved_step",
                 "steps_done", "technician", "note"]
_lock = threading.Lock()

PAGE = r"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="AOI 排除">
<title>AOI 現場排除</title><style>
:root{--bg:#f3f4f6;--card:#fff;--fg:#1f2937;--muted:#6b7280;--red:#dc2626;--amber:#d97706;--green:#16a34a;--blue:#2563eb;--line:#e5e7eb}
@media (prefers-color-scheme:dark){:root{--bg:#111827;--card:#1f2937;--fg:#f3f4f6;--muted:#9ca3af;--line:#374151}}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"PingFang TC",sans-serif;background:var(--bg);color:var(--fg);font-size:17px}
header{padding:14px 16px;font-size:20px;font-weight:700}main{padding:0 16px 96px;max-width:1100px;margin:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{background:var(--card);border-radius:14px;padding:14px 16px;margin:10px 0;box-shadow:0 1px 3px #0002;border-left:6px solid var(--green)}
.card.alarm,.card.overdue{border-left-color:var(--red)}.card.warn{border-left-color:var(--amber)}.card.info{border-left-color:var(--blue)}
.tap{cursor:pointer}.muted{color:var(--muted);font-size:14px}h2{margin:4px 0 8px;font-size:20px}h3{margin:14px 0 6px}
.bar{height:10px;border-radius:5px;background:var(--line);overflow:hidden}.bar i{display:block;height:100%}
button,.btn{font-size:18px;padding:14px 18px;border-radius:12px;border:0;background:var(--blue);color:#fff;min-height:52px;cursor:pointer}
button.ok{background:var(--green)}button.no{background:var(--amber)}button.ghost{background:var(--line);color:var(--fg)}button.danger{background:var(--red)}
.row{display:flex;gap:10px;flex-wrap:wrap}.row>button{flex:1;min-width:150px}
.step{font-size:24px;line-height:1.5;padding:24px 4px}
textarea,input,select{width:100%;font-size:17px;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
textarea{min-height:90px}nav{position:fixed;bottom:0;left:0;right:0;display:flex;background:var(--card);border-top:1px solid var(--line);padding-bottom:env(safe-area-inset-bottom)}
nav a{flex:1;text-align:center;padding:12px 0;color:var(--muted);text-decoration:none;font-size:15px}nav a.on{color:var(--blue);font-weight:700}
.tag{display:inline-block;font-size:13px;padding:2px 8px;border-radius:999px;background:var(--line);margin-right:6px}
ul{padding-left:20px}li{margin:4px 0}table{border-collapse:collapse;width:100%}td,th{padding:6px;border-bottom:1px solid var(--line);text-align:left;font-size:15px}
</style></head><body>
<header id="title">AOI 現場排除</header><main id="view"></main>
<nav><a href="#" data-v="overview">📊 總覽</a><a href="#" data-v="parts">📦 備料</a><a href="#" data-v="pick">🔧 排除故障</a><a href="#" data-v="records">📝 紀錄</a><a href="#" data-v="upload">📤 上傳分析</a></nav>
<script>
const $=s=>document.querySelector(s), V=$('#view');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LV={overdue:'⛔ 逾期',alarm:'🔴 緊急',warn:'🟡 近期',info:'🔵 規劃',ok:'🟢 正常'};
const dd=d=>d==null?'—':(d<=0?'現在':d+' 天');
const hcol=h=>h<60?'var(--red)':h<80?'var(--amber)':'var(--green)';
const PS={order_now:'🛒 立即備料',order_soon:'📋 準備備料',stocked:'📦 有庫存',ok:'🟢 正常'};
const PC={order_now:'alarm',order_soon:'warn',stocked:'info',ok:''};
const ob=p=>p.status==='stocked'?'不需(有庫存)':p.order_by_days==null?'—':(p.order_by_days<=0?'已過,立即下單':p.order_by_days+' 天內');
const partRow=(p,m)=>`<tr><td>${PS[p.status]}</td>${m?`<td>${esc(m)}</td>`:''}<td><b>${esc(p.name)}</b><div class="muted">${esc(p.reasons.join(';'))}</div></td>
 <td><div class="bar" style="width:70px"><i style="width:${p.health}%;background:${hcol(p.health)}"></i></div>${p.health}</td>
 <td>${dd(p.due_days)}</td><td>${p.lead_days} 天</td><td>${p.stock}</td><td>${ob(p)}</td><td>${esc(p.part_no)}</td></tr>`;
const PH='<th>狀態</th><th>零件</th><th>健康</th><th>預計更換</th><th>交期</th><th>庫存</th><th>最晚下單</th><th>料號</th>';
let timer=null,cur='overview';
function autoRefresh(sec){clearInterval(timer);timer=setInterval(async()=>{if(['overview','parts'].includes(cur)){S.ov=null;go(cur);}},sec*1000);}
let S={ov:null,m:null,faults:[],f:null,i:0};
async function api(p,o){const r=await fetch(p,o);const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j;}
function nav(v){document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('on',a.dataset.v===v));}
document.querySelectorAll('nav a').forEach(a=>a.onclick=e=>{e.preventDefault();go(a.dataset.v);});
function go(v,...a){cur=v;nav(v==='machine'?'overview':['faults','step','end'].includes(v)?'pick':v);window.scrollTo(0,0);
 ({overview,machine,parts,pick,faults,step,end,records,upload})[v](...a).catch?.(e=>V.innerHTML=`<div class="card alarm">${esc(e.message)}</div>`);}
async function load(){S.ov=await api('/api/overview');autoRefresh(S.ov.refresh||60);return S.ov;}

async function overview(){V.innerHTML='<p class="muted">載入中…</p>';const ov=await load();
 if(ov.errors.length)V.innerHTML=ov.errors.map(e=>`<div class="card warn">${esc(e)}</div>`).join('');else V.innerHTML='';
 V.innerHTML+=`<p class="muted">🟢 監測中 · 每 ${ov.refresh} 秒自動更新 · 最後更新 ${esc(ov.updated.slice(11))}</p><div class="grid">`+ov.machines.map(m=>`
 <div class="card tap ${m.level}" onclick="go('machine','${esc(m.machine_id)}')">
 <h2>${esc(m.name)}</h2><div class="muted">${esc(m.machine_id)} · ${esc(m.model)} · ${LV[m.level]}</div>
 <p>健康度 <b>${m.health}</b></p><div class="bar"><i style="width:${m.health}%;background:${hcol(m.health)}"></i></div>
 ${m.parts.filter(p=>p.status!=='ok').map(p=>`<div style="margin-top:6px">${PS[p.status]} ${esc(p.name)}(${dd(p.due_days)})</div>`).join('')}
 <ul>${m.tasks.slice(0,3).map(t=>`<li>${LV[t.level]} ${esc(t.item)}(${dd(t.due_days)})</li>`).join('')||'<li>無待辦</li>'}</ul></div>`).join('')+'</div>';}

async function machine(id){const ov=S.ov||await load();const m=ov.machines.find(x=>x.machine_id===id);S.m=m;
 V.innerHTML=`<div class="card ${m.level}"><h2>${esc(m.name)}</h2><div class="muted">${esc(m.machine_id)} · ${esc(m.model)} · 資料至 ${esc(m.as_of||'—')}</div>
 <p>健康度 <b>${m.health}</b></p><div class="bar"><i style="width:${m.health}%;background:${hcol(m.health)}"></i></div>
 <div class="row" style="margin-top:14px"><button onclick="go('faults','${esc(id)}')">🔧 開始排除故障</button></div></div>
 <div class="card"><h3>零件健康度</h3><div style="overflow-x:auto"><table><tr>${PH}</tr>${m.parts.map(p=>partRow(p)).join('')}</table></div></div>
 <div class="card"><h3>保養待辦</h3><ul>${m.tasks.map(t=>`<li>${LV[t.level]} [${esc(t.type)}] ${esc(t.item)} → ${esc(t.action)}(${dd(t.due_days)})</li>`).join('')||'<li>無</li>'}</ul>
 <h3>感測趨勢</h3><table><tr><th>項目</th><th>現值</th><th>趨勢</th><th>健康</th><th>預計超標</th></tr>${m.predictions.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.current}</td>
 <td>${p.r2>=0.5?(p.slope_per_day>0?'+':'')+p.slope_per_day+'/天':'穩定'}</td><td>${p.health}</td><td>${dd(p.due_days)}</td></tr>`).join('')}</table></div>`;}

async function parts(){const ov=S.ov||await load();
 const all=ov.machines.flatMap(m=>m.parts.map(p=>({...p,mname:m.name}))).filter(p=>p.due_days!=null)
  .sort((a,b)=>({order_now:0,order_soon:1,stocked:2,ok:3}[a.status]-{order_now:0,order_soon:1,stocked:2,ok:3}[b.status])||a.due_days-b.due_days);
 const n=k=>all.filter(p=>p.status===k).length;
 V.innerHTML=`<h2>備料清單</h2><p class="muted">依預測更換日 − 交期 − 安全天數 計算最晚下單日 · 最後更新 ${esc(ov.updated.slice(11))}</p>
 <div class="grid"><div class="card alarm"><h2>${n('order_now')}</h2>🛒 立即備料</div><div class="card warn"><h2>${n('order_soon')}</h2>📋 14 天內需下單</div>
 <div class="card info"><h2>${n('stocked')}</h2>📦 已有庫存</div></div>
 <div class="card" style="overflow-x:auto"><table><tr><th>狀態</th><th>機台</th>${PH.slice(PH.indexOf('<th>零件'))}</tr>${all.map(p=>partRow(p,p.mname)).join('')}</table></div>`;}

async function pick(){const ov=S.ov||await load();
 V.innerHTML='<h2>選擇機台</h2><div class="grid">'+ov.machines.map(m=>`<div class="card tap ${m.level}" onclick="go('faults','${esc(m.machine_id)}')">
 <h2>${esc(m.name)}</h2><div class="muted">${esc(m.machine_id)} · ${LV[m.level]} · 健康度 ${m.health}</div></div>`).join('')+'</div>';}

async function faults(id){const ov=S.ov||await load();const m=ov.machines.find(x=>x.machine_id===id);S.m=m;
 S.faults=await api('/api/faults?profile='+encodeURIComponent(m.profile));
 const rec=new Set(m.predictions.filter(p=>p.level!=='ok').flatMap(p=>p.faults.map(f=>f.name)));
 const sorted=[...S.faults].sort((a,b)=>rec.has(b.name)-rec.has(a.name));
 V.innerHTML=`<h2>${esc(m.name)}:發生什麼問題?</h2><p class="muted">⭐ 為系統依數據推薦</p>`+sorted.map((f,i)=>`
 <div class="card tap ${rec.has(f.name)?'warn':''}" onclick="startFix('${esc(f.id)}')"><span class="tag">${esc(f.category)}</span>
 <b>${rec.has(f.name)?'⭐ ':''}${esc(f.name)}</b><div class="muted">${f.steps.length} 個步驟</div></div>`).join('');}
function startFix(fid){S.f=S.faults.find(f=>f.id===fid);S.i=0;go('step');}

async function step(){const f=S.f,n=f.steps.length;
 V.innerHTML=`<div class="card"><div class="muted">${esc(S.m.name)} · ${esc(f.name)}</div>
 <h2>步驟 ${S.i+1} / ${n}</h2><div class="bar"><i style="width:${(S.i+1)/n*100}%;background:var(--blue)"></i></div>
 <div class="step">${esc(f.steps[S.i])}</div>
 <div class="row"><button class="ok" onclick="go('end',true)">✅ 問題已解決</button>
 <button class="no" onclick="next()">${S.i+1<n?'➡️ 沒解決,下一步':'❌ 全部做完仍無法排除'}</button></div>
 <div class="row" style="margin-top:10px">${S.i>0?'<button class="ghost" onclick="S.i--;go(\'step\')">⬅️ 上一步</button>':''}
 <button class="ghost" onclick="go('faults',S.m.machine_id)">換一個問題</button></div></div>`;}
function next(){if(S.i+1<S.f.steps.length){S.i++;go('step');}else go('end',false);}

async function end(solved){const ov=S.ov||await load();
 V.innerHTML=`<div class="card ${solved?'':'alarm'}"><h2>${solved?'✅ 已解決':'❌ 無法排除,請升級處理'}</h2>
 <div class="muted">${esc(S.m.name)} · ${esc(S.f.name)} · 執行到步驟 ${S.i+1}/${S.f.steps.length}</div>
 ${solved?'':`<h3>聯絡窗口</h3><ul>${ov.contacts.map(c=>`<li><b>${esc(c.name)}</b>:${esc(c.phone)} ${esc(c.note||'')}</li>`).join('')}</ul>
 <p class="muted">建議:接上筆電匯出機台 Log、拍下錯誤畫面,一併提供給工程師。</p>`}
 <h3>維修紀錄</h3><input id="tech" placeholder="處理人員"><br><br>
 <textarea id="note" placeholder="現象、更換零件、量測數值、錯誤代碼…"></textarea><br><br>
 <button onclick="save(${solved})">💾 送出紀錄</button></div>`;
 try{$('#tech').value=localStorage.getItem('tech')||'';}catch(e){}}
async function save(solved){const tech=$('#tech').value;try{localStorage.setItem('tech',tech);}catch(e){}
 await api('/api/repairs',{method:'POST',body:JSON.stringify({machine_id:S.m.machine_id,fault_id:S.f.id,fault_name:S.f.name,
 result:solved?'已解決':'未解決',solved_step:solved?S.i+1:'',steps_done:S.i+1,technician:tech,note:$('#note').value})});
 V.innerHTML=`<div class="card"><h2>已儲存紀錄 👍</h2><div class="row"><button onclick="go('overview')">回總覽</button><button class="ghost" onclick="go('records')">看紀錄</button></div></div>`;}

async function records(){const rs=await api('/api/repairs');
 V.innerHTML='<h2>維修紀錄</h2>'+(rs.length?'<div class="card"><table><tr><th>時間</th><th>機台</th><th>問題</th><th>結果</th><th>人員</th><th>備註</th></tr>'+
 rs.map(r=>`<tr><td>${esc(r.time)}</td><td>${esc(r.machine_id)}</td><td>${esc(r.fault_name)}</td><td>${r.result==='已解決'?'✅':'❌'} ${esc(r.result)}${r.solved_step?'(步驟 '+esc(r.solved_step)+')':''}</td>
 <td>${esc(r.technician)}</td><td>${esc(r.note)}</td></tr>`).join('')+'</table></div>':'<p class="muted">尚無紀錄</p>');}

async function upload(){V.innerHTML=`<div class="card"><h2>上傳資料分析</h2><p class="muted">從機台匯出的 CSV(歷史感測資料 → 預知保養;檢測結果 → 故障診斷)</p>
 <select id="prof"><option value="discovery8">Orbotech Discovery 8</option><option value="fusion22">KLA Fusion 22</option><option value="aoi">SMT AOI</option><option value="generic">一般機台</option></select><br><br>
 <input type="file" id="file" accept=".csv"><br><br><textarea id="csv" placeholder="或貼上 CSV 內容"></textarea><br><br>
 <div class="row"><button onclick="up('predict')">🔧 預知保養</button><button class="ghost" onclick="up('analyze')">即時故障診斷</button></div></div><div id="out"></div>`;
 $('#file').onchange=e=>{const r=new FileReader();r.onload=()=>$('#csv').value=r.result;r.readAsText(e.target.files[0]);};}
async function up(kind){const prof=$('#prof').value,csv=$('#csv').value,out=$('#out');
 try{if(kind==='predict'){const d=await api('/api/predict',{method:'POST',body:JSON.stringify({profile:prof,csv})});
  out.innerHTML=d.map(m=>`<div class="card ${m.level}"><h2>${esc(m.machine_id)} — 健康度 ${m.health}</h2><ul>${m.tasks.map(t=>`<li>${LV[t.level]} ${esc(t.item)} → ${esc(t.action)}(${dd(t.due_days)})</li>`).join('')||'<li>無</li>'}</ul></div>`).join('');}
 else{const d=await api('/api/analyze?profile='+prof,{method:'POST',body:csv});
  out.innerHTML=d.map(m=>`<div class="card ${m.status}"><h2>${esc(m.machine_id)}</h2><ul>${m.findings.map(f=>`<li>${esc(f.message)}</li>`).join('')}</ul>
  ${m.diagnosis.slice(0,3).map(x=>`<h3>[${esc(x.category)}] ${esc(x.name)} <span class="muted">${Math.round(x.confidence*100)}%</span></h3><ol>${x.steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol>`).join('')}</div>`).join('');}}
 catch(e){out.innerHTML=`<div class="card alarm">${esc(e.message)}</div>`;}}
go('overview');
</script></body></html>"""


class App:
    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        f = self.dir / "machines.json"
        self.meta = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def overview(self):
        machines = {m["id"]: m for m in self.meta.get("machines", [])}
        out, errors = [], []
        for src in self.meta.get("sources", []):
            hist = self.dir / src["history"]
            log = self.dir / src["log"] if src.get("log") else None
            if not hist.exists():
                errors.append(f"找不到資料檔 {hist}")
                continue
            try:
                sp = self.dir / self.meta["spares"] if self.meta.get("spares") else None
                for r in predict.run(hist, src["profile"], log if log and log.exists() else None,
                                     spares_source=sp if sp and sp.exists() else None):
                    info = machines.get(r["machine_id"], {})
                    out.append({**r, "profile": src["profile"], "name": info.get("name", r["machine_id"]),
                                "model": info.get("model", src["profile"])})
            except Exception as e:  # noqa: BLE001
                errors.append(f"{hist.name} 分析失敗:{e}")
        seen = {m["machine_id"] for m in out}
        for mid, info in machines.items():  # 有登錄但沒資料的機台也要能排除故障
            if mid not in seen:
                out.append({"machine_id": mid, "name": info.get("name", mid), "model": info.get("model", ""),
                             "profile": info.get("profile", "generic"), "health": 100, "level": "ok",
                             "as_of": None, "parts": [], "predictions": [], "schedule": [], "tasks": []})
        order = list(machines)
        out.sort(key=lambda m: order.index(m["machine_id"]) if m["machine_id"] in order else len(order))
        return {"data_dir": str(self.dir), "machines": out, "errors": errors,
                "updated": datetime.now().isoformat(timespec="seconds"),
                "refresh": self.meta.get("refresh_seconds", 60),
                "contacts": self.meta.get("contacts", [])}

    @property
    def repair_file(self):
        return self.dir / "repair_log.csv"

    def add_repair(self, body):
        row = {k: str(body.get(k, ""))[:2000] for k in REPAIR_FIELDS}
        row["time"] = datetime.now().isoformat(timespec="minutes")
        with _lock:
            new = not self.repair_file.exists()
            with open(self.repair_file, "a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=REPAIR_FIELDS)
                if new:
                    w.writeheader()
                w.writerow(row)
        return row

    def repairs(self):
        if not self.repair_file.exists():
            return []
        return list(reversed(detector.read_rows(self.repair_file)))


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype="application/json"):
            if not isinstance(body, str):
                body = json.dumps(body, ensure_ascii=False)
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _err(self, e, code=400):
            self._send(code, {"error": str(e)})

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            try:
                if url.path == "/":
                    return self._send(200, PAGE, "text/html")
                if url.path == "/api/overview":
                    return self._send(200, app.overview())
                if url.path == "/api/faults":
                    prof = q.get("profile", ["generic"])[0]
                    if prof not in detector.PROFILES:
                        raise ValueError(f"未知機型 {prof}")
                    return self._send(200, diagnosis.load_kb(profile=prof))
                if url.path == "/api/repairs":
                    return self._send(200, app.repairs())
                self._send(404, {"error": "not found"})
            except Exception as e:  # noqa: BLE001
                self._err(e)

        def do_POST(self):
            url = urlparse(self.path)
            length = int(self.headers.get("Content-Length", 0))
            if length > 20_000_000:
                return self._err("檔案過大", 413)
            text = self.rfile.read(length).decode("utf-8-sig", errors="replace")
            try:
                if url.path == "/api/repairs":
                    return self._send(200, app.add_repair(json.loads(text)))
                if url.path == "/api/predict":
                    body = json.loads(text)
                    prof = body.get("profile", "discovery8")
                    if prof not in detector.PROFILES:
                        raise ValueError(f"未知機型 {prof}")
                    log = io.StringIO(body["log"]) if (body.get("log") or "").strip() else None
                    return self._send(200, predict.run(io.StringIO(body.get("csv", "")), prof, log))
                if url.path == "/api/analyze":
                    prof = parse_qs(url.query).get("profile", ["generic"])[0]
                    if prof not in detector.PROFILES:
                        raise ValueError(f"未知機型 {prof}")
                    return self._send(200, engine.run(io.StringIO(text), prof))
                self._send(404, {"error": "not found"})
            except Exception as e:  # noqa: BLE001
                self._err(f"處理失敗:{e}")

    return Handler


def _lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def serve(host="127.0.0.1", port=8000, data_dir="samples"):
    app = App(data_dir)
    print(f"本機開啟:http://127.0.0.1:{port}")
    if host == "0.0.0.0" and (ip := _lan_ip()):
        print(f"iPad / 手機(同一網路)開啟:http://{ip}:{port}")
    print(f"資料目錄:{Path(data_dir).resolve()}")
    ThreadingHTTPServer((host, port), make_handler(app)).serve_forever()
