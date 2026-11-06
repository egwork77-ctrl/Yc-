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

from . import detector, diagnosis, engine, et_points, predict, vibration
from .live import Live, LogWatcher

STATIC_DIR = Path(__file__).with_name("static")
STATIC_TYPES = {".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary"}
MODEL3D = {"discovery8": "discovery", "fusion22": "fusion22", "vrs": "vrs", "et_precise": "mania"}

REPAIR_FIELDS = ["time", "machine_id", "fault_id", "fault_name", "result", "solved_step",
                 "steps_done", "technician", "note"]
_lock = threading.Lock()


def append_csv(path, row):
    """附加一列;檔案沒有的欄位會自動加到表頭(重寫檔案)。"""
    path = Path(path)
    with _lock:
        header = []
        if path.exists():
            with open(path, encoding="utf-8-sig", newline="") as f:
                header = next(csv.reader(f), [])
        missing = [k for k in row if k not in header]
        if header and not missing:
            with open(path, "a", encoding="utf-8", newline="") as f:
                csv.DictWriter(f, fieldnames=header, extrasaction="ignore").writerow(row)
            return
        rows = detector.read_rows(path) if path.exists() else []
        header += missing
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows + [row])


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

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
.card.alarm,.card.overdue,.card.down{border-left-color:var(--red)}.card.warn{border-left-color:var(--amber)}.card.info{border-left-color:var(--blue)}
.tap{cursor:pointer}.muted{color:var(--muted);font-size:14px}h2{margin:4px 0 8px;font-size:20px}h3{margin:14px 0 6px}
.bar{height:10px;border-radius:5px;background:var(--line);overflow:hidden}.bar i{display:block;height:100%}
button,.btn{font-size:18px;padding:14px 18px;border-radius:12px;border:0;background:var(--blue);color:#fff;min-height:52px;cursor:pointer}
button.ok{background:var(--green)}button.no{background:var(--amber)}button.ghost{background:var(--line);color:var(--fg)}button.danger{background:var(--red)}
.num{display:flex;align-items:center;gap:8px;margin:8px 0}.num label{flex:2}.num input{flex:1;max-width:160px;font-size:20px}
.stepper{display:flex;align-items:center;gap:8px}.stepper button{min-width:52px;padding:10px}.stepper b{min-width:36px;text-align:center;font-size:20px}
.evgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.evgrid button{background:var(--card);color:var(--fg);border:2px solid var(--line);font-size:17px;min-height:68px}
.evgrid button:active{background:var(--blue);color:#fff}.evgrid button b{display:block;font-size:22px;color:var(--blue)}
.toast{position:fixed;left:50%;bottom:90px;transform:translateX(-50%);background:#111827;color:#fff;padding:10px 18px;border-radius:999px;z-index:9}
@media print{nav,.noprint{display:none}main{padding:0}.card{box-shadow:none;border:1px solid #ccc;break-inside:avoid}}
.fxmap{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;max-width:420px;aspect-ratio:5/4}
.fxmap button{min-height:0;padding:0;border-radius:6px;background:var(--line);color:var(--fg);font-size:13px}
.fxmap button.sel{background:var(--blue);color:#fff}.seg button{flex:1}.seg button.ghost{opacity:.8}
#m3d.fs{position:fixed!important;inset:0;height:100vh!important;z-index:50;border-radius:0!important}
.row{display:flex;gap:10px;flex-wrap:wrap}.row>button{flex:1;min-width:150px}
.step{font-size:24px;line-height:1.5;padding:24px 4px}
textarea,input,select{width:100%;font-size:17px;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
textarea{min-height:90px}nav{position:fixed;bottom:0;left:0;right:0;display:flex;background:var(--card);border-top:1px solid var(--line);padding-bottom:env(safe-area-inset-bottom)}
nav{overflow-x:auto}nav a{flex:1 0 76px;text-align:center;padding:12px 0;color:var(--muted);text-decoration:none;font-size:15px}nav a.on{color:var(--blue);font-weight:700}
.tag{display:inline-block;font-size:13px;padding:2px 8px;border-radius:999px;background:var(--line);margin-right:6px}
ul{padding-left:20px}li{margin:4px 0}table{border-collapse:collapse;width:100%}td,th{padding:6px;border-bottom:1px solid var(--line);text-align:left;font-size:15px}
</style></head><body>
<header id="title">AOI 現場排除</header><main id="view"></main>
<nav><a href="#" data-v="overview">📊 總覽</a><a href="#" data-v="live">▶️ 監看</a><a href="#" data-v="inspect">📋 點檢</a><a href="#" data-v="pins">📍 假點</a><a href="#" data-v="parts">📦 備料</a><a href="#" data-v="pick">🔧 排除故障</a><a href="#" data-v="records">📝 紀錄</a><a href="#" data-v="upload">📤 上傳分析</a></nav>
<script>
const $=s=>document.querySelector(s), V=$('#view');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LV={down:'🛑 停機待修',overdue:'⛔ 逾期',alarm:'🔴 緊急',warn:'🟡 近期',info:'🔵 規劃',ok:'🟢 正常'};
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
let m3d=null;
const loadJS=src=>new Promise((ok,no)=>{if(document.querySelector(`script[src="${src}"]`))return ok();const s=document.createElement('script');s.src=src;s.onload=ok;s.onerror=no;document.head.appendChild(s);});
async function show3d(m){const el=$('#m3d');if(!el)return;
 try{await loadJS('/static/three.min.js');await loadJS('/static/OrbitControls.js');await loadJS('/static/model3d.js');}
 catch(e){el.innerHTML='<p class="muted">3D 載入失敗</p>';return;}
 const info=$('#pinfo');
 const urgent=m.tasks.filter(t=>['overdue','alarm'].includes(t.level)).length;
 m3d=AOI3D.mount(el,{model:m.model3d,parts:m.parts,mode:'holo',
  panel:{title:m.name+' · '+(m.model||''),health:m.health,rows:[['狀態',(LV[m.level]||'').replace(/^\S+\s/,'')],['緊急待辦',urgent+' 項'],
   ['機齡',m.info&&m.info.age_years?m.info.age_years+' 年':'—'],['資料時間',(m.as_of||'—').replace('T',' ')]]},
  gauges:m.predictions.slice().sort((a,b)=>a.health-b.health).map(p=>({name:p.name,value:+(+p.current).toPrecision(4),pct:p.health})),onPick:id=>{const p=m.parts.find(x=>x.part_id===id);
  info.innerHTML=p?`<b>${esc(p.name)}</b> · 健康 ${p.health} · 預計更換 ${dd(p.due_days)} · 庫存 ${p.stock} · ${PS[p.status]}<div class="muted">${esc(p.reasons.join(';')||'目前無異常趨勢')}</div>`
  :`<b>${esc(id)}</b><div class="muted">尚無此零件資料</div>`;}});}
let liveTimer=null;
function toast(t){const d=document.createElement('div');d.className='toast';d.textContent=t;document.body.appendChild(d);setTimeout(()=>d.remove(),1500);}
const getSid=()=>{try{return localStorage.getItem('sid')}catch(e){return null}},setSid=v=>{try{v?localStorage.setItem('sid',v):localStorage.removeItem('sid')}catch(e){}};
const sugg=(list,title)=>list.length?`<h3>${title}</h3>`+list.map(d=>`<div class="card warn"><span class="tag">${esc(d.category)}</span><b>${esc(d.name)}</b>
 <span class="muted">${d.support?'相關事件 '+d.support+' 次 · ':''}信心 ${Math.round(d.confidence*100)}%</span><div class="muted" style="margin-top:6px">現場排除</div><ol>${d.steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ol>
 ${d.improve&&d.improve.length?`<div class="muted">根本改善</div><ul>${d.improve.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}</div>`).join(''):'';
async function live(){const ov=S.ov||await load();let sid=getSid(),d=null;
 if(sid){try{d=await api('/api/live?session_id='+sid);if(d.session.end){setSid(null);d=null;}}catch(e){setSid(null);d=null;}}
 if(!d){V.innerHTML=`<div class="card"><h2>▶️ 作業監看</h2><p class="muted">機台作業時開著:有狀況就按一下記錄,短時間重複發生會立即警示並提出改善方法。</p>
  ${msel(ov)}<br><br><input id="lop" placeholder="作業 / 監看人員"><br><br><button style="width:100%" onclick="startLive()">▶️ 開始監看</button></div>`;
  if(lastM)$('#msel').value=lastM;try{$('#lop').value=localStorage.getItem('tech')||'';}catch(e){}return;}
 const evs=await api('/api/live/events?machine_id='+encodeURIComponent(d.session.machine_id));
 const m=ov.machines.find(x=>x.machine_id===d.session.machine_id)||{name:d.session.machine_id};
 V.innerHTML=`<div class="card info"><h2>▶️ 監看中:${esc(m.name)}</h2><div class="muted">${esc(d.session.operator)} · 開始 ${esc(d.session.start.slice(11,16))} · 已進行 <span id="elapsed"></span></div></div>
 <div class="card"><h3>有狀況就按(可連續按)</h3><div class="evgrid">${evs.map(e=>`<button onclick="logEv('${esc(e.id)}','${esc(e.name)}')">${esc(e.name)}<b id="c_${esc(e.id)}">0</b></button>`).join('')}</div>
 <div class="row" style="margin-top:12px"><input id="lnote" placeholder="文字備註(現象、處理方式、想法…)" style="flex:3"><button style="flex:1" onclick="logNote()">📝 記錄</button></div></div>
 <div id="lalerts"></div><div id="ltl"></div>
 <div class="card noprint"><textarea id="lend" placeholder="結束前的總結(可空白)"></textarea><br><br><button class="danger" style="width:100%" onclick="endLive()">⏹ 結束並產生改善報告</button></div>`;
 renderLive(d);clearInterval(liveTimer);liveTimer=setInterval(async()=>{if(cur!=='live')return clearInterval(liveTimer);
  try{renderLive(await api('/api/live?session_id='+getSid()));}catch(e){}},5000);}
function renderLive(d){const st=new Date(d.session.start);const min=Math.round((Date.now()-st)/60000);
 if($('#elapsed'))$('#elapsed').textContent=min>=60?Math.floor(min/60)+' 小時 '+min%60+' 分':min+' 分';
 document.querySelectorAll('[id^=c_]').forEach(b=>b.textContent=0);d.counts.forEach(c=>{const b=$('#c_'+c.event);if(b)b.textContent=c.count;});
 $('#lalerts').innerHTML=(d.alerts.length?d.alerts.map(a=>`<div class="card alarm"><h2>⚠️ ${esc(a.name)}:${a.minutes} 分鐘內 ${a.count} 次</h2>${sugg(a.suggestions,'可能原因與對策')}</div>`).join(''):'')+
  (d.overall.length?`<div class="card">${sugg(d.overall,'💡 依本場次記錄的綜合判斷')}</div>`:'');
 $('#ltl').innerHTML=`<div class="card"><h3>記錄(最新在上)</h3><ul>${d.events.map(e=>`<li><span class="muted">${esc(e.time.slice(11,16))}</span> ${e.source==='log'?'🤖':'👆'}
  ${esc(e.event==='note'?'📝':(d.counts.find(c=>c.event===e.event)||{name:e.event}).name)} ${esc(e.note)}</li>`).join('')||'<li class="muted">尚無記錄</li>'}</ul></div>`;}
async function startLive(){const mid=$('#msel').value,op=$('#lop').value;lastM=mid;try{localStorage.setItem('tech',op);}catch(e){}
 const s=await api('/api/live/start',{method:'POST',body:JSON.stringify({machine_id:mid,operator:op})});setSid(s.session_id);go('live');}
async function logEv(id,name){await api('/api/live/event',{method:'POST',body:JSON.stringify({session_id:getSid(),event:id})});toast('已記錄:'+name);
 renderLive(await api('/api/live?session_id='+getSid()));}
async function logNote(){const n=$('#lnote').value.trim();if(!n)return;await api('/api/live/event',{method:'POST',body:JSON.stringify({session_id:getSid(),event:'note',note:n})});
 $('#lnote').value='';toast('已記錄備註');renderLive(await api('/api/live?session_id='+getSid()));}
async function endLive(){const sid=getSid();await api('/api/live/end',{method:'POST',body:JSON.stringify({session_id:sid,note:$('#lend').value})});setSid(null);S.ov=null;go('report',sid);}
async function report(sid){const d=await api('/api/live/report?session_id='+sid);const ov=S.ov||await load();
 const m=ov.machines.find(x=>x.machine_id===d.session.machine_id)||{name:d.session.machine_id};
 V.innerHTML=`<div class="card"><h2>📄 改善報告:${esc(m.name)}</h2><table>
 <tr><td>機台</td><td>${esc(m.name)}(${esc(d.session.machine_id)})</td></tr><tr><td>人員</td><td>${esc(d.session.operator)}</td></tr>
 <tr><td>時間</td><td>${esc(d.session.start.replace('T',' '))} ~ ${esc((d.session.end||'進行中').replace('T',' '))}(${d.duration_min} 分鐘)</td></tr>
 <tr><td>總結</td><td>${esc(d.session.note)||'—'}</td></tr></table>
 <h3>事件統計</h3><table>${d.counts.map(c=>`<tr><td>${esc(c.event==='note'?'文字備註':c.name)}</td><td>${c.count} 次</td></tr>`).join('')||'<tr><td>無</td></tr>'}</table></div>
 ${d.alerts.length?`<div class="card alarm"><h3>結束時仍在警示的問題</h3><ul>${d.alerts.map(a=>`<li>${esc(a.name)}:${a.minutes} 分鐘內 ${a.count} 次</li>`).join('')}</ul></div>`:''}
 <div class="card">${sugg(d.overall,'💡 原因判斷與改善建議')||'<p class="muted">本場次沒有足夠事件做判斷</p>'}</div>
 <div class="card"><h3>完整記錄</h3><ul>${d.events.slice().reverse().map(e=>`<li>${esc(e.time.slice(11,16))} ${e.source==='log'?'🤖':'👆'} ${esc(e.event==='note'?'📝':(d.counts.find(c=>c.event===e.event)||{name:e.event}).name)} ${esc(e.note)}</li>`).join('')}</ul></div>
 <div class="row noprint"><button onclick="print()">🖨 列印 / 存 PDF</button><button class="ghost" onclick="go('records')">看所有紀錄</button></div>`;}
function fs3d(){const el=$('#m3d');const on=!el.classList.contains('fs');el.classList.toggle('fs',on);
 let x=$('#fsx');if(on&&!x){x=document.createElement('button');x.id='fsx';x.textContent='✕ 離開全螢幕';x.onclick=fs3d;
  x.style.cssText='position:fixed;top:12px;right:12px;z-index:60;background:rgba(15,23,42,.8)';document.body.appendChild(x);}else if(!on&&x)x.remove();}
function go(v,...a){cur=v;const fx=$('#fsx');if(fx)fx.remove();if(m3d){m3d.dispose();m3d=null;}nav(v==='machine'?'overview':v==='report'?'records':['faults','step','end'].includes(v)?'pick':v);window.scrollTo(0,0);
 ({overview,machine,live,report,inspect,pins,parts,pick,faults,step,end,records,upload})[v](...a).catch?.(e=>V.innerHTML=`<div class="card alarm">${esc(e.message)}</div>`);}
async function load(){S.ov=await api('/api/overview');autoRefresh(S.ov.refresh||60);return S.ov;}

async function overview(){V.innerHTML='<p class="muted">載入中…</p>';const ov=await load();
 if(ov.errors.length)V.innerHTML=ov.errors.map(e=>`<div class="card warn">${esc(e)}</div>`).join('');else V.innerHTML='';
 V.innerHTML+=`<p class="muted">🟢 監測中 · 每 ${ov.refresh} 秒自動更新 · 最後更新 ${esc(ov.updated.slice(11))}</p><div class="grid">`+ov.machines.map(m=>`
 <div class="card tap ${m.level}" onclick="go('machine','${esc(m.machine_id)}')">
 <h2>${esc(m.name)}</h2><div class="muted">${esc(m.model)}${m.info&&m.info.age_years?' · 機齡 '+m.info.age_years+' 年':''} · ${LV[m.level]}</div>
 <p>健康度 <b>${m.health}</b></p><div class="bar"><i style="width:${m.health}%;background:${hcol(m.health)}"></i></div>
 ${m.parts.filter(p=>p.status!=='ok').map(p=>`<div style="margin-top:6px">${PS[p.status]} ${esc(p.name)}(${dd(p.due_days)})</div>`).join('')}
 <ul>${m.tasks.slice(0,3).map(t=>`<li>${LV[t.level]} ${esc(t.item)}(${dd(t.due_days)})</li>`).join('')||'<li>無待辦</li>'}</ul></div>`).join('')+'</div>';}

const INFO=[['status_note','⚠️ 目前狀態'],['down_since','停機日期'],['model','型號'],['serial','序號'],['asset_no','設備 No.'],['card','卡號'],['installed','進廠日期'],['age_years','機齡(年)'],['dept','保管單位'],['note','備註']];
function infoTable(i){const rows=INFO.filter(([k])=>i[k]!=null).map(([k,t])=>`<tr><td class="muted">${t}</td><td>${esc(i[k])}</td></tr>`);
 if(i.calibration)rows.push(`<tr><td class="muted">外部校正</td><td>${esc(i.calibration.by||'')} 上次 ${esc(i.calibration.last||'—')} · 下次 ${esc(i.calibration.next||'—')}</td></tr>`);
 return rows.length?`<h3>銘牌資料</h3><table>${rows.join('')}</table>`:'';}
async function machine(id){const ov=S.ov||await load();const m=ov.machines.find(x=>x.machine_id===id);S.m=m;
 V.innerHTML=`<div class="card ${m.level}"><h2>${esc(m.name)}</h2><div class="muted">${esc(m.machine_id)} · ${esc(m.model)} · 資料至 ${esc(m.as_of||'—')}</div>
 <p>健康度 <b>${m.health}</b></p><div class="bar"><i style="width:${m.health}%;background:${hcol(m.health)}"></i></div>
 ${infoTable(m.info||{})}
 <div class="row" style="margin-top:14px"><button onclick="go('faults','${esc(id)}')">🔧 開始排除故障</button></div></div>
 ${m.model3d?`<div class="card"><h3>🧊 3D 機台</h3><p class="muted">拖曳旋轉、雙指縮放,點選零件查看資料(外型依現場照片估計,內部機構為示意)</p>
 <div id="m3d" style="height:min(62vh,520px);border-radius:12px;overflow:hidden;touch-action:none"></div>
 <div class="row" style="margin-top:10px" id="m3dmode">${[['holo','✨ 數位孿生'],['xray','👁 透視'],['solid','外觀'],['mech','⚙️ 機構'],['mesh','▦ 網格']].map(([k,t])=>
 `<button class="${k==='holo'?'':'ghost'}" data-m="${k}" onclick="m3d.setMode('${k}');document.querySelectorAll('#m3dmode button[data-m]').forEach(b=>b.className=b.dataset.m==='${k}'?'':'ghost')">${t}</button>`).join('')}</div>
 <div class="row" style="margin-top:10px"><button class="ghost" onclick="this.textContent=m3d.toggleAnim()?'⏸ 暫停動作':'▶ 掃描動作'">⏸ 暫停動作</button>
 <button class="ghost" onclick="m3d.reset()">↺ 重設視角</button><button class="ghost" onclick="fs3d()">⛶ 全螢幕</button></div><div id="pinfo" style="margin-top:10px" class="muted">點選零件查看資料</div></div>`:''}
 <div id="vib"></div>
 <div class="card"><h3>零件健康度</h3><div style="overflow-x:auto"><table><tr>${PH}</tr>${m.parts.map(p=>partRow(p)).join('')}</table></div></div>
 <div class="card"><h3>保養待辦</h3><ul>${m.tasks.map(t=>`<li>${LV[t.level]} [${esc(t.type)}] ${esc(t.item)} → ${esc(t.action)}(${dd(t.due_days)})</li>`).join('')||'<li>無</li>'}</ul>
 <h3>感測趨勢</h3><table><tr><th>項目</th><th>現值</th><th>趨勢</th><th>健康</th><th>預計超標</th></tr>${m.predictions.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.current}</td>
 <td>${p.r2>=0.5?(p.slope_per_day>0?'+':'')+p.slope_per_day+'/天':'穩定'}</td><td>${p.health}</td><td>${dd(p.due_days)}</td></tr>`).join('')}</table></div>`;
 show3d(m);showVib(m);}
function vibChart(v){const W=640,H=260,L=56,R=12,Tp=14,B=40,fx=W-L-R,fy=H-Tp-B;
 const ymax=Math.max(...v.latest_curve.map(p=>p[1]),...v.base_curve.map(p=>p[1]))*1.1||1;
 const X=f=>L+f/v.fmax*fx,Y=a=>Tp+fy-a/ymax*fy,path=c=>c.map((p,i)=>(i?'L':'M')+X(p[0]).toFixed(1)+','+Y(p[1]).toFixed(1)).join('');
 const nice=x=>{const e=10**Math.floor(Math.log10(x)),m=x/e;return (m<=1?1:m<=2?2:m<=5?5:10)*e;},fs=nice(v.fmax/5);
 let g='';for(let f=0;f<=v.fmax+1e-9;f+=fs)g+=`<line x1="${X(f)}" y1="${Tp}" x2="${X(f)}" y2="${Tp+fy}" stroke="var(--line)"/><text x="${X(f)}" y="${H-22}" font-size="11" text-anchor="middle" fill="var(--muted)">${f}</text>`;
 for(let i=0;i<=5;i++){const a=ymax*i/5;
  g+=`<line x1="${L}" y1="${Y(a)}" x2="${L+fx}" y2="${Y(a)}" stroke="var(--line)"/><text x="${L-6}" y="${Y(a)+4}" font-size="11" text-anchor="end" fill="var(--muted)">${a.toFixed(2)}</text>`;}
 const pk=v.peaks.filter(p=>p.vs_base>=3).map(p=>`<circle cx="${X(p.freq)}" cy="${Y(p.amp)}" r="5" fill="none" stroke="var(--red)" stroke-width="2"/>
  <text x="${X(p.freq)+8}" y="${Y(p.amp)-6}" font-size="12" fill="var(--red)">${p.freq} Hz ×${p.vs_base}</text>`).join('');
 return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">${g}
 <path d="${path(v.base_curve)}" fill="none" stroke="#9ca3af" stroke-width="1.5"/><path d="${path(v.latest_curve)}" fill="none" stroke="#dc2626" stroke-width="2"/>${pk}
 <text x="${L+fx/2}" y="${H-4}" font-size="12" text-anchor="middle" fill="var(--muted)">頻率 (Hz)</text>
 <text x="14" y="${Tp+fy/2}" font-size="12" text-anchor="middle" fill="var(--muted)" transform="rotate(-90 14 ${Tp+fy/2})">振幅</text></svg>`;}
async function showVib(m){const el=$('#vib');if(!el)return;const v=await api('/api/vibration?machine_id='+encodeURIComponent(m.machine_id));
 if(!v.captures){el.innerHTML=`<div class="card"><h3>📈 振動頻譜</h3><p class="muted">尚無振動資料。在 XY 平台馬達裝振動感測器,把量測檔放到 vibration/${esc(m.machine_id)}/ 即可分析。</p></div>`;return;}
 el.innerHTML=`<div class="card ${v.level}"><h3>📈 振動頻譜(${esc(v.latest)})</h3>
 <div class="muted">紅線:最新量測 · 灰線:基準(${esc(v.baseline)}) · 整體 RMS ${v.rms_latest}(基準的 ${v.rms_ratio} 倍)</div>${vibChart(v)}
 ${v.findings.length?`<ul>${v.findings.map(f=>`<li>${LV[v.level]} ${esc(f)}</li>`).join('')}</ul><button onclick="go('faults','${esc(m.machine_id)}')">🔧 排除 XY 平台問題</button>`:'<p>🟢 頻譜與基準相比無明顯變化</p>'}</div>`;}

const msel=(ov,id)=>`<select id="msel">${ov.machines.map(m=>`<option value="${esc(m.machine_id)}">${esc(m.name)}(${esc(m.machine_id)})</option>`).join('')}</select>`;
let lastM=null;
async function inspect(){const ov=S.ov||await load();
 V.innerHTML=`<div class="card"><h2>每日點檢</h2><p class="muted">把機台畫面 / 儀表上看到的數值填進來,留空的項目不記錄。數據累積後就能預測。</p>
 ${msel(ov)}<div id="form"></div></div><div id="res"></div>`;
 const sel=$('#msel');if(lastM)sel.value=lastM;sel.onchange=()=>{lastM=sel.value;loadForm();};loadForm();}
async function loadForm(){const f=await api('/api/form?machine_id='+encodeURIComponent($('#msel').value));
 const hint=x=>x.counter?'累計':[x.min!=null?'≥ '+x.min:'',x.max!=null?'≤ '+x.max:''].filter(Boolean).join(' ');
 $('#form').innerHTML=`<p class="muted">上次點檢:${esc(f.last_time||'無')}</p>`+f.fields.map(x=>`<div class="num"><label>${esc(x.name)}
 <div class="muted">${esc(hint(x))}${x.last!==''?' · 上次 '+esc(x.last):''}</div></label>
 <input type="number" step="any" inputmode="decimal" data-k="${esc(x.key)}"></div>`).join('')+
 `<input id="itech" placeholder="點檢人員" style="margin:8px 0"><button onclick="sendInspect()" style="width:100%">💾 儲存點檢</button>`;
 try{$('#itech').value=localStorage.getItem('tech')||'';}catch(e){}}
async function sendInspect(){const values={};document.querySelectorAll('#form input[data-k]').forEach(i=>{if(i.value!=='')values[i.dataset.k]=i.value;});
 try{const r=await api('/api/inspection',{method:'POST',body:JSON.stringify({machine_id:$('#msel').value,values})});S.ov=null;
 $('#res').innerHTML=`<div class="card ${r.warnings.length?'alarm':''}"><h2>${r.warnings.length?'⚠️ 已儲存,但有異常':'✅ 已儲存,數值正常'}</h2>
 <ul>${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>${r.warnings.length?`<button onclick="go('faults','${esc($('#msel').value)}')">🔧 開始排除故障</button>`:''}</div>`;
 document.querySelectorAll('#form input[data-k]').forEach(i=>i.value='');window.scrollTo(0,document.body.scrollHeight);}
 catch(e){$('#res').innerHTML=`<div class="card alarm">${esc(e.message)}</div>`;}}

let pinCell=null,pinSide='下治具',pinType='open';
async function pins(){const ov=S.ov||await load();const et=ov.machines.filter(m=>m.profile==='et_precise');const rep=await api('/api/et');
 const segBtns=(arr,cur,fn)=>arr.map(([v,t])=>`<button class="${v===cur?'':'ghost'}" onclick="${fn}('${v}')">${t}</button>`).join('');
 V.innerHTML=`<div class="card"><h2>📍 電測假點登錄</h2><p class="muted">重測會過的點(假點)每次發生就登錄。累積後系統會告訴你是哪支針、哪副治具、還是哪台機台的問題。</p>
 <select id="pm">${et.map(m=>`<option value="${esc(m.machine_id)}">${esc(m.name)}(${esc(m.model)})${m.level==='down'?' 🛑停機':''}</option>`).join('')}</select><br><br>
 <input id="pfx" list="pfxl" placeholder="治具編號(例:料號或治具標籤)"><datalist id="pfxl">${rep.fixtures.map(f=>`<option value="${esc(f)}">`).join('')}</datalist><br><br>
 <div class="row seg" id="pside">${segBtns([['上治具','上治具'],['下治具','下治具']],pinSide,'setSide')}</div>
 <p class="muted">點選假點在治具上的位置(可略過) <button class="ghost" style="min-height:0;padding:4px 10px;font-size:14px" onclick="setCell(null)">不指定位置</button></p><div class="fxmap" id="pmap">${Array.from({length:20},(_,k)=>{const i=k%5,j=3-Math.floor(k/5);
  return `<button data-c="${i},${j}" class="${pinCell==i+','+j?'sel':''}" onclick="setCell('${i},${j}')">${['左','','中','','右'][i]}${['下','','','上'][j]}</button>`}).join('')}</div><br>
 <input id="ppins" inputmode="numeric" placeholder="針號(多支用逗號分開,例:456, 1203)"><br><br>
 <div class="row seg" id="ptype">${segBtns([['open','Open 斷路'],['short','Short 短路']],pinType,'setType')}</div><br>
 <div class="row"><button class="ok" onclick="sendPins('pass')">登錄假點(重測通過)</button><button class="no" onclick="sendPins('fail')">登錄真不良</button></div>
 <h3>測試片數</h3><p class="muted">每批或每班結束時登錄這副治具測了幾片,才能算假點率。</p>
 <div class="row"><input id="pcnt" type="number" inputmode="numeric" placeholder="片數" style="flex:2"><button style="flex:1" onclick="sendBoards()">登錄片數</button></div></div>
 <div id="pres"></div>`;
 try{const l=JSON.parse(localStorage.getItem('pinlast')||'{}');if(l.m)$('#pm').value=l.m;if(l.f)$('#pfx').value=l.f;}catch(e){}
 renderPins(rep);}
function setSide(v){pinSide=v;document.querySelectorAll('#pside button').forEach(b=>b.className=b.textContent===v?'':'ghost');}
function setType(v){pinType=v;document.querySelectorAll('#ptype button').forEach((b,i)=>b.className=(i===0)===(v==='open')?'':'ghost');}
function setCell(c){pinCell=c;document.querySelectorAll('#pmap button').forEach(b=>b.className=b.dataset.c===pinCell?'sel':'');}
function pinBody(){const m=$('#pm').value,f=$('#pfx').value.trim();try{localStorage.setItem('pinlast',JSON.stringify({m,f}));}catch(e){}return {machine_id:m,fixture_id:f};}
async function sendPins(rt){const b=pinBody();let x='',y='';if(pinCell){const [i,j]=pinCell.split(',').map(Number);x=i*100+50;y=j*80+40;}
 try{const r=await api('/api/et/points',{method:'POST',body:JSON.stringify({...b,pins:$('#ppins').value,retest:rt,fail_type:pinType,side:pinSide,x,y})});
  toast(`已登錄 ${r.saved} 點`);$('#ppins').value='';renderPins(await api('/api/et'));}catch(e){toast(e.message);}}
async function sendBoards(){try{const r=await api('/api/et/boards',{method:'POST',body:JSON.stringify({...pinBody(),count:$('#pcnt').value})});
 toast(`已登錄 ${r.saved} 片`);$('#pcnt').value='';renderPins(await api('/api/et'));}catch(e){toast(e.message);}}
function heat(cells){const mx=Math.max(1,...Object.values(cells));let h='<div class="fxmap" style="max-width:260px">';
 for(let j=3;j>=0;j--)for(let i=0;i<5;i++){const n=cells[i+','+j]||0;h+=`<button style="background:rgba(220,38,38,${n/mx*0.85+0.05});color:${n/mx>0.5?'#fff':'var(--fg)'}">${n||''}</button>`;}
 return h+'</div>';}
function renderPins(rep){const el=$('#pres');if(!el)return;
 if(!rep.machines.length){el.innerHTML='<div class="card"><p class="muted">尚無登錄資料</p></div>';return;}
 el.innerHTML=rep.machines.filter(m=>m.findings.length).map(m=>`<div class="card ${m.status}"><h2>${esc(m.machine_id)} 分析結果</h2>
 <ul>${m.findings.map(f=>`<li>${LV[f.level]||''} ${esc(f.message)}</li>`).join('')}</ul>
 ${m.diagnosis.length?`<p>💡 最可能:<b>${esc(m.diagnosis[0].name)}</b></p><details><summary>看排除步驟與改善建議</summary>${sugg(m.diagnosis.slice(0,1),'')}</details>`:''}</div>`).join('')+
 `<div class="card"><h3>各治具假點排行(前 6)</h3>${rep.pins.slice(0,6).map(e=>`<div style="margin:10px 0"><b>${esc(e.machine_id)} · 治具 ${esc(e.fixture_id)}</b> — 假點 ${e.count} 點
 <div class="row" style="align-items:flex-start;margin-top:6px"><table style="flex:1">${e.top.slice(0,5).map(([p,n])=>`<tr><td>${esc(p)}</td><td>${n} 次</td></tr>`).join('')}</table>
 ${Object.keys(e.cells).length?`<div style="flex:1">${heat(e.cells)}<div class="muted">治具位置分布</div></div>`:''}</div></div>`).join('')||'<p class="muted">尚無假點</p>'}</div>`;}

async function parts(){const ov=S.ov||await load();
 const all=ov.machines.flatMap(m=>m.parts.map(p=>({...p,mname:m.name}))).filter(p=>p.due_days!=null)
  .sort((a,b)=>({order_now:0,order_soon:1,stocked:2,ok:3}[a.status]-{order_now:0,order_soon:1,stocked:2,ok:3}[b.status])||a.due_days-b.due_days);
 const n=k=>all.filter(p=>p.status===k).length;
 V.innerHTML=`<h2>備料清單</h2><p class="muted">依預測更換日 − 交期 − 安全天數 計算最晚下單日 · 最後更新 ${esc(ov.updated.slice(11))}</p>
 <div class="grid"><div class="card alarm"><h2>${n('order_now')}</h2>🛒 立即備料</div><div class="card warn"><h2>${n('order_soon')}</h2>📋 14 天內需下單</div>
 <div class="card info"><h2>${n('stocked')}</h2>📦 已有庫存</div></div>
 <div class="card" style="overflow-x:auto"><table><tr><th>狀態</th><th>機台</th>${PH.slice(PH.indexOf('<th>零件'))}</tr>${all.map(p=>partRow(p,p.mname)).join('')}</table></div>
 <div class="card"><h2>備品庫存</h2><p class="muted">取代人工記錄:入庫按 +,領用按 −。料號、交期可直接修改。</p><div id="stock"></div></div>`;stock();}
async function stock(){const sp=await api('/api/spares');
 $('#stock').innerHTML='<div style="overflow-x:auto"><table><tr><th>零件</th><th>庫存</th><th>交期(天)</th><th>料號</th></tr>'+sp.map(p=>`<tr><td><b>${esc(p.name)}</b></td>
 <td><div class="stepper"><button class="ghost" onclick="spare('${p.part_id}',{delta:-1})">−</button><b>${p.stock}</b><button class="ghost" onclick="spare('${p.part_id}',{delta:1})">+</button></div></td>
 <td><input type="number" inputmode="numeric" value="${p.lead_days}" style="max-width:90px" onchange="spare('${p.part_id}',{lead_days:this.value})"></td>
 <td><input value="${esc(p.part_no)}" onchange="spare('${p.part_id}',{part_no:this.value})"></td></tr>`).join('')+'</table></div>';}
async function spare(id,body){await api('/api/spares',{method:'POST',body:JSON.stringify({part_id:id,...body})});S.ov=null;
 if('delta' in body||'lead_days' in body){await parts();}}

async function pick(){const ov=S.ov||await load();
 V.innerHTML='<h2>選擇機台</h2><div class="grid">'+ov.machines.map(m=>`<div class="card tap ${m.level}" onclick="go('faults','${esc(m.machine_id)}')">
 <h2>${esc(m.name)}</h2><div class="muted">${esc(m.machine_id)} · ${LV[m.level]} · 健康度 ${m.health}</div></div>`).join('')+'</div>';}

async function faults(id){const ov=S.ov||await load();const m=ov.machines.find(x=>x.machine_id===id);S.m=m;
 S.faults=await api('/api/faults?profile='+encodeURIComponent(m.profile));
 const rec=new Set(m.predictions.filter(p=>p.level!=='ok').flatMap(p=>p.faults.map(f=>f.name)));
 if(m.level==='down')S.faults.filter(f=>/停機/.test(f.category)).forEach(f=>rec.add(f.name));
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

async function records(){const rs=await api('/api/repairs');const ov=S.ov||await load();
 const ss=await api('/api/live/sessions');
 V.innerHTML=(ss.length?`<div class="card"><h2>監看改善報告</h2><ul>${ss.slice(0,20).map(x=>`<li class="tap" onclick="go('report','${esc(x.session_id)}')">📄 ${esc(x.start.replace('T',' ').slice(0,16))} · ${esc(x.machine_id)} · ${esc(x.operator)} ${x.end?'':'(進行中)'}</li>`).join('')}</ul></div>`:'')+`<div class="card"><h2>登錄保養 / 更換零件</h2><p class="muted">做完保養請登錄,系統才會從今天重新計算壽命與下次到期。</p>
 ${msel(ov)}<br><br><select id="mitem"></select><br><br><select id="mpart"></select><br><br>
 <input id="mtech" placeholder="處理人員"><br><br><textarea id="mnote" placeholder="備註"></textarea><br><br>
 <button onclick="sendMaint()" style="width:100%">💾 登錄保養</button><div id="mres"></div></div>`+'<h2>維修紀錄</h2>'+(rs.length?'<div class="card"><table><tr><th>時間</th><th>機台</th><th>問題</th><th>結果</th><th>人員</th><th>備註</th></tr>'+
 rs.map(r=>`<tr><td>${esc(r.time)}</td><td>${esc(r.machine_id)}</td><td>${esc(r.fault_name)}</td><td>${r.result==='已解決'?'✅':'❌'} ${esc(r.result)}${r.solved_step?'(步驟 '+esc(r.solved_step)+')':''}</td>
 <td>${esc(r.technician)}</td><td>${esc(r.note)}</td></tr>`).join('')+'</table></div>':'<p class="muted">尚無紀錄</p>');
 const sel=$('#msel');if(lastM)sel.value=lastM;sel.onchange=()=>{lastM=sel.value;maintForm();};maintForm();
 try{$('#mtech').value=localStorage.getItem('tech')||'';}catch(e){}}
async function maintForm(){const f=await api('/api/form?machine_id='+encodeURIComponent($('#msel').value));
 $('#mitem').innerHTML=f.maintenance.map(x=>`<option>${esc(x)}</option>`).join('');
 $('#mpart').innerHTML='<option value="">不使用庫存零件</option>'+f.parts.map(p=>`<option value="${esc(p.id)}">領用:${esc(p.name)}</option>`).join('');}
async function sendMaint(){try{const r=await api('/api/maintenance',{method:'POST',body:JSON.stringify({machine_id:$('#msel').value,
 item:$('#mitem').value,part_id:$('#mpart').value,technician:$('#mtech').value,note:$('#mnote').value})});S.ov=null;
 await records();$('#mres').innerHTML=`<p>✅ 已登錄 ${esc(r.saved.item)}${r.spare?`,${esc(r.spare.name)} 庫存剩 ${r.spare.stock}`:''}</p>`;}
 catch(e){$('#mres').innerHTML=`<p style="color:var(--red)">${esc(e.message)}</p>`;}}

async function upload(){V.innerHTML=`<div class="card"><h2>上傳資料分析</h2><p class="muted">從機台匯出的 CSV(歷史感測資料 → 預知保養;檢測結果 → 故障診斷)</p>
 <select id="prof"><option value="discovery8">Orbotech Discovery 8</option><option value="fusion22">KLA Fusion 22</option><option value="vrs">Orbotech VRS</option><option value="et_precise">電測 Mania PRECISE</option><option value="aoi">SMT AOI</option><option value="generic">一般機台</option></select><br><br>
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
        self.live = Live(self.dir, self.meta, self.profile_of)

    def profile_of(self, mid):
        m = next((x for x in self.meta.get("machines", []) if x["id"] == mid), None)
        if not m:
            raise ValueError(f"未登錄的機台 {mid}")
        return m["profile"]

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
                                "model": info.get("model", src["profile"]),
                                "model3d": info.get("model3d") or MODEL3D.get(src["profile"])})
            except Exception as e:  # noqa: BLE001
                errors.append(f"{hist.name} 分析失敗:{e}")
        seen = {m["machine_id"] for m in out}
        for mid, info in machines.items():  # 有登錄但沒資料的機台也要能排除故障
            if mid not in seen:
                out.append({"machine_id": mid, "name": info.get("name", mid), "model": info.get("model", ""),
                             "model3d": info.get("model3d") or MODEL3D.get(info.get("profile")),
                             "profile": info.get("profile", "generic"), "health": 100, "level": "ok",
                             "as_of": None, "parts": [], "predictions": [], "schedule": [], "tasks": []})
        for m in out:
            meta = machines.get(m["machine_id"], {})
            m["info"] = self._info(meta)
            if meta.get("status") == "down":            # 故障停機中:最優先顯示
                m["level"] = "down"
                m["tasks"].insert(0, {"type": "停機", "item": f"停機待修(自 {meta.get('down_since', '—')})",
                                      "level": "overdue", "due_days": 0,
                                      "action": meta.get("status_note") or "請進入排除故障"})
            cal = (machines.get(m["machine_id"], {}).get("calibration") or {})
            if cal.get("next"):
                days = (datetime.fromisoformat(cal["next"]) - datetime.now()).days
                lv = "overdue" if days < 0 else "alarm" if days <= 7 else "warn" if days <= 30 else None
                if lv:
                    m["tasks"].insert(0, {"type": "校正", "item": f"外部校正({cal.get('by', '')})到期 {cal['next']}",
                                          "level": lv, "due_days": days,
                                          "action": f"已逾期 {-days} 天,請安排校正" if days < 0 else "請安排校正"})
                    if predict.LEVEL_ORDER[lv] < predict.LEVEL_ORDER[m["level"]]:
                        m["level"] = lv
        order = list(machines)
        out.sort(key=lambda m: order.index(m["machine_id"]) if m["machine_id"] in order else len(order))
        return {"data_dir": str(self.dir), "machines": out, "errors": errors,
                "updated": datetime.now().isoformat(timespec="seconds"),
                "refresh": self.meta.get("refresh_seconds", 60),
                "contacts": self.meta.get("contacts", [])}

    # ---- 機台 / 資料來源 ----
    def machine(self, mid):
        m = next((x for x in self.meta.get("machines", []) if x["id"] == mid), None)
        if not m:
            raise ValueError(f"未登錄的機台 {mid}")
        src = next((x for x in self.meta.get("sources", []) if x["profile"] == m["profile"]), None)
        if not src:
            raise ValueError(f"機型 {m['profile']} 沒有設定資料來源")
        return m, self.dir / src["history"], self.dir / src["log"]

    def _latest(self, hist, mid):
        rows = [r for r in detector.read_rows(hist) if r.get("machine_id") == mid] if hist.exists() else []
        return rows[-1] if rows else {}

    @staticmethod
    def _counters(cfg):
        return sorted({m["counter"] for m in cfg.get("maintenance", []) if "counter" in m})

    def form(self, mid):
        """點檢 / 保養表單需要的欄位、門檻與上次數值。"""
        m, hist, _ = self.machine(mid)
        cfg = detector.load_config(profile=m["profile"])
        last = self._latest(hist, mid)
        fields = [{"key": k, "name": r.get("name", k), "last": last.get(k, ""),
                   "min": r.get("min_warn"), "max": r.get("max_warn")} for k, r in cfg["sensors"].items()]
        fields += [{"key": c, "name": {"run_hours": "運轉時數(累計)", "lamp_hours": "燈管時數(累計)",
                                       "light_hours": "光源時數(累計)"}.get(c, c), "last": last.get(c, ""),
                    "min": None, "max": None, "counter": True} for c in self._counters(cfg)]
        return {"machine": m, "fields": fields, "last_time": last.get("timestamp"),
                "maintenance": [x["item"] for x in cfg.get("maintenance", [])],
                "parts": [{"id": p["id"], "name": p["name"]} for p in cfg.get("parts", [])]}

    def add_inspection(self, body):
        mid = body.get("machine_id", "")
        m, hist, _ = self.machine(mid)
        cfg = detector.load_config(profile=m["profile"])
        allowed = set(cfg["sensors"]) | set(self._counters(cfg))
        vals = {k: _float(v) for k, v in (body.get("values") or {}).items() if k in allowed}
        vals = {k: v for k, v in vals.items() if v is not None}
        if not vals:
            raise ValueError("沒有輸入任何數值")
        row = {"timestamp": datetime.now().isoformat(timespec="minutes"), "machine_id": mid, **vals}
        append_csv(hist, row)
        warnings = []
        for k, v in vals.items():
            r = cfg["sensors"].get(k)
            if not r:
                continue
            for key, op, word in (("max_alarm", v.__gt__, "🔴 超過警報值"), ("max_warn", v.__gt__, "🟡 超過警告值"),
                                  ("min_alarm", v.__lt__, "🔴 低於警報值"), ("min_warn", v.__lt__, "🟡 低於警告值")):
                if r.get(key) is not None and op(r[key]):
                    warnings.append(f"{r.get('name', k)} = {v:g} {word} {r[key]:g}")
                    break
        return {"saved": row, "warnings": warnings}

    # ---- 備品庫存 ----
    @property
    def spares_file(self):
        return self.dir / self.meta.get("spares", "spares.csv")

    def spares(self):
        rows = {(r.get("machine_id") or "*", r.get("part_id")): r
                for r in (detector.read_rows(self.spares_file) if self.spares_file.exists() else [])}
        parts = {}
        for src in self.meta.get("sources", []):
            for p in detector.load_config(profile=src["profile"]).get("parts", []):
                e = parts.setdefault(p["id"], {"part_id": p["id"], "name": p["name"], "models": [],
                                               "lead_days": p.get("lead_days", 14)})
                e["models"].append(src["profile"])
        out = []
        for pid, e in parts.items():
            r = rows.get(("*", pid), {})
            out.append({**e, "part_no": r.get("part_no", ""), "stock": int(_float(r.get("stock")) or 0),
                        "lead_days": int(_float(r.get("lead_days")) or e["lead_days"])})
        return out

    def update_spare(self, body):
        pid = body.get("part_id")
        cur = {x["part_id"]: x for x in self.spares()}
        if pid not in cur:
            raise ValueError(f"未知零件 {pid}")
        e = cur[pid]
        if "delta" in body:
            e["stock"] = max(0, e["stock"] + int(body["delta"]))
        for k in ("stock", "lead_days"):
            if k in body and k != "delta" and _float(body[k]) is not None:
                e[k] = max(0, int(_float(body[k])))
        if "part_no" in body:
            e["part_no"] = str(body["part_no"])[:100]
        with _lock:
            rows = detector.read_rows(self.spares_file) if self.spares_file.exists() else []
            rows = [r for r in rows if not ((r.get("machine_id") or "*") == "*" and r.get("part_id") == pid)]
            rows.append({"machine_id": "*", "part_id": pid, "part_no": e["part_no"],
                         "stock": e["stock"], "lead_days": e["lead_days"]})
            with open(self.spares_file, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["machine_id", "part_id", "part_no", "stock", "lead_days"],
                                   extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
        return e

    # ---- 保養登錄 ----
    # ---- 電測假點登錄 ----
    ET_FIELDS = ["timestamp", "machine_id", "fixture_id", "board_id", "point", "x", "y", "side", "fail_type",
                 "retest", "note"]

    @property
    def et_file(self):
        return self.dir / "et_points.csv"

    def _et_check(self, body):
        mid, fx = (body.get("machine_id") or "").strip(), (body.get("fixture_id") or "").strip()[:40]
        if self.profile_of(mid) != "et_precise":
            raise ValueError(f"{mid} 不是電測機台")
        if not fx:
            raise ValueError("請輸入治具編號")
        return mid, fx

    def add_et_points(self, body):
        mid, fx = self._et_check(body)
        pins = [p for p in str(body.get("pins", "")).replace(",", " ").replace("、", " ").split() if p][:50]
        if not pins:
            raise ValueError("請輸入針號")
        now = datetime.now().isoformat(timespec="minutes")
        rows = [{"timestamp": now, "machine_id": mid, "fixture_id": fx, "board_id": "",
                 "point": p if p.upper().startswith("P-") else f"P-{p}", "x": body.get("x", ""), "y": body.get("y", ""),
                 "side": body.get("side", ""), "fail_type": body.get("fail_type", "open"),
                 "retest": "pass" if body.get("retest", "pass") == "pass" else "fail", "note": str(body.get("note", ""))[:200]}
                for p in pins]
        for r in rows:
            append_csv(self.et_file, r)
        return {"saved": len(rows)}

    def add_et_boards(self, body):
        mid, fx = self._et_check(body)
        n = int(_float(body.get("count")) or 0)
        if not 1 <= n <= 5000:
            raise ValueError("片數需在 1–5000")
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        for i in range(n):
            append_csv(self.et_file, {"timestamp": datetime.now().isoformat(timespec="minutes"), "machine_id": mid,
                                      "fixture_id": fx, "board_id": f"{fx}-{stamp}-{i:04d}", "point": ""})
        return {"saved": n}

    def et_report(self):
        if not self.et_file.exists():
            return {"machines": [], "fixtures": [], "pins": []}
        rows = detector.read_rows(self.et_file)
        report = engine.run(self.et_file) if rows else []
        false = [r for r in rows if r.get("point") and r.get("retest") == "pass"]
        pins = {}
        for r in false:
            k = (r["machine_id"], r["fixture_id"])
            e = pins.setdefault(k, {"machine_id": k[0], "fixture_id": k[1], "count": 0, "top": {}, "cells": {}})
            e["count"] += 1
            e["top"][r["point"]] = e["top"].get(r["point"], 0) + 1
            if r.get("x") and r.get("y"):
                c = f"{int(float(r['x']) // 100)},{int(float(r['y']) // 80)}"
                e["cells"][c] = e["cells"].get(c, 0) + 1
        for e in pins.values():
            e["top"] = sorted(e["top"].items(), key=lambda kv: -kv[1])[:10]
        return {"machines": report, "fixtures": sorted({r["fixture_id"] for r in rows if r.get("fixture_id")}),
                "pins": sorted(pins.values(), key=lambda e: -e["count"])}

    def add_maintenance(self, body):
        mid, item = body.get("machine_id", ""), body.get("item", "")
        m, hist, log = self.machine(mid)
        cfg = detector.load_config(profile=m["profile"])
        if item not in [x["item"] for x in cfg.get("maintenance", [])]:
            raise ValueError(f"未知保養項目 {item}")
        last = self._latest(hist, mid)
        row = {"date": datetime.now().date().isoformat(), "machine_id": mid, "item": item,
               **{c: last[c] for c in self._counters(cfg) if last.get(c)}}
        append_csv(log, row)
        used = None
        if body.get("part_id"):
            used = self.update_spare({"part_id": body["part_id"], "delta": -1})
        self.add_repair({"machine_id": mid, "fault_id": "maintenance", "fault_name": f"保養:{item}",
                         "result": "保養完成", "technician": body.get("technician", ""),
                         "note": (body.get("note", "") + (f"(領用 {used['name']},剩 {used['stock']})" if used else ""))})
        return {"saved": row, "spare": used}

    @staticmethod
    def _info(meta):
        keys = ("model", "serial", "asset_no", "card", "installed", "dept", "note", "calibration",
                "status_note", "down_since")
        info = {k: meta[k] for k in keys if meta.get(k)}
        if meta.get("installed"):
            y, mth = (int(x) for x in meta["installed"][:7].split("-"))
            now = datetime.now()
            info["age_years"] = round(now.year - y + (now.month - mth) / 12, 1)
        return info

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

        def _static(self, name):
            f = (STATIC_DIR / name).resolve()
            if STATIC_DIR.resolve() not in f.parents or not f.is_file() or f.suffix not in STATIC_TYPES:
                return self._send(404, {"error": "not found"})
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", STATIC_TYPES[f.suffix])
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=86400")
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
                if url.path.startswith("/static/"):
                    return self._static(url.path[len("/static/"):])
                if url.path == "/api/overview":
                    return self._send(200, app.overview())
                if url.path == "/api/faults":
                    prof = q.get("profile", ["generic"])[0]
                    if prof not in detector.PROFILES:
                        raise ValueError(f"未知機型 {prof}")
                    return self._send(200, diagnosis.load_kb(profile=prof))
                if url.path == "/api/repairs":
                    return self._send(200, app.repairs())
                if url.path == "/api/form":
                    return self._send(200, app.form(q.get("machine_id", [""])[0]))
                if url.path == "/api/spares":
                    return self._send(200, app.spares())
                if url.path == "/api/et":
                    return self._send(200, app.et_report())
                if url.path == "/api/vibration":
                    mid = q.get("machine_id", [""])[0]
                    app.profile_of(mid)
                    return self._send(200, vibration.analyze(app.dir / "vibration" / mid) or {})
                if url.path == "/api/live/events":
                    return self._send(200, app.live.events_config(q.get("machine_id", [""])[0]))
                if url.path == "/api/live/active":
                    return self._send(200, app.live.active(q.get("machine_id", [""])[0]) or {})
                if url.path == "/api/live":
                    return self._send(200, app.live.live(q.get("session_id", [""])[0]))
                if url.path == "/api/live/report":
                    return self._send(200, app.live.report(q.get("session_id", [""])[0]))
                if url.path == "/api/live/sessions":
                    return self._send(200, app.live.sessions())
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
                if url.path.startswith("/api/live/"):
                    b = json.loads(text)
                    act = url.path.rsplit("/", 1)[1]
                    if act == "start":
                        return self._send(200, app.live.start(b.get("machine_id", ""), b.get("operator", "")))
                    if act == "event":
                        return self._send(200, app.live.add_event(b.get("session_id", ""), b.get("event", ""),
                                                                  b.get("note", "")))
                    if act == "end":
                        return self._send(200, app.live.end(b.get("session_id", ""), b.get("note", "")))
                if url.path == "/api/et/points":
                    return self._send(200, app.add_et_points(json.loads(text)))
                if url.path == "/api/et/boards":
                    return self._send(200, app.add_et_boards(json.loads(text)))
                if url.path == "/api/inspection":
                    return self._send(200, app.add_inspection(json.loads(text)))
                if url.path == "/api/spares":
                    return self._send(200, app.update_spare(json.loads(text)))
                if url.path == "/api/maintenance":
                    return self._send(200, app.add_maintenance(json.loads(text)))
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
    watcher = LogWatcher(app.live, app.meta.get("machines", []))
    if watcher.targets:
        watcher.start()
        print(f"自動讀取機台 Log:{len(watcher.targets)} 台")
    print(f"本機開啟:http://127.0.0.1:{port}")
    if host == "0.0.0.0" and (ip := _lan_ip()):
        print(f"iPad / 手機(同一網路)開啟:http://{ip}:{port}")
    print(f"資料目錄:{Path(data_dir).resolve()}")
    ThreadingHTTPServer((host, port), make_handler(app)).serve_forever()
