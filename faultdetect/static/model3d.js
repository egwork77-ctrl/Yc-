/* AOI 機台 3D 機構模型(外型依現場照片估計,內部機構為示意,尺寸單位:公尺,非原廠圖面)。
 *
 * AOI3D.mount(容器, {model:'fusion22'|'discovery'|'vrs'|'mania', parts:[...], onPick:fn})
 *   回傳 {setMode('xray'|'solid'|'mech'|'mesh'), toggleAnim(), reset(), select(id), dispose()}
 *
 * 機構以工程分析配色:床台藍、立柱橘、橫樑紫、工作台黃、線軌紅、滾珠螺桿黃、伺服馬達黑。
 * 「網格」模式以細分網格顯示,類似有限元素模型的外觀(僅為視覺,非 FEA 計算)。
 */
(function () {
  const T = THREE;
  const C = { base: 0x2f4fd6, column: 0xe0662e, beam: 0x7b5cd6, table: 0xd9b52a, rail: 0xd62828,
              screw: 0xe8d44d, motor: 0x1c1c1c, slider: 0x9aa4b2, head: 0x64748b, light: 0xf8fafc };
  const MESH_STEP = 0.07;

  function mat(color, o = {}) {
    return new T.MeshStandardMaterial({ color, roughness: o.rough ?? 0.55, metalness: o.metal ?? 0.15,
      transparent: !!o.shell, opacity: 1, emissive: o.emissive ?? 0x000000 });
  }
  const seg = v => Math.max(1, Math.min(18, Math.round(v / MESH_STEP)));
  function box(w, h, d, m) { return new T.Mesh(new T.BoxGeometry(w, h, d, seg(w), seg(h), seg(d)), m); }
  function cyl(r, h, m, n = 24) { return new T.Mesh(new T.CylinderGeometry(r, r, h, n, seg(h)), m); }
  function at(o, x, y, z) { o.position.set(x, y, z); return o; }

  // 滾珠螺桿:軸心 + 螺旋牙
  class Helix extends T.Curve {
    constructor(len, r, pitch) { super(); this.len = len; this.r = r; this.turns = len / pitch; }
    getPoint(t, out = new T.Vector3()) {
      const a = t * this.turns * Math.PI * 2;
      return out.set(this.r * Math.cos(a), t * this.len - this.len / 2, this.r * Math.sin(a));
    }
  }
  function screw(len, m) {
    const g = new T.Group();
    g.add(cyl(0.012, len, m, 12));
    g.add(new T.Mesh(new T.TubeGeometry(new Helix(len, 0.016, 0.025), Math.round(len / 0.025) * 8, 0.004, 5), m));
    return g;
  }
  function servo(m) {
    const g = new T.Group();
    g.add(box(0.11, 0.11, 0.17, m));
    const flange = at(cyl(0.035, 0.03, mat(0x52525b, { metal: 0.6 })), 0, 0, 0.1);
    flange.rotation.x = Math.PI / 2;
    g.add(flange);
    return g;
  }

  function extrudeProfile(points, w, m) {
    const s = new T.Shape();
    points(s);
    const g = new T.ExtrudeGeometry(s, { depth: w, bevelEnabled: false, curveSegments: 24 });
    g.rotateY(Math.PI / 2);
    g.translate(-w / 2, 0, 0);
    return new T.Mesh(g, m);
  }

  class Builder {
    constructor() {
      this.group = new T.Group();
      this.shells = [];
      this.mech = [];
      this.pickables = [];
    }
    add(o, x = 0, y = 0, z = 0, parent = this.group) { at(o, x, y, z); parent.add(o); return o; }
    shell(o, x, y, z) { this.add(o, x, y, z); this.shells.push(o); return o; }
    /** 機構零件:可點選、參與網格模式 */
    m(part, o, x, y, z, parent) {
      o.traverse(n => { if (n.isMesh) { n.userData.part = part; this.pickables.push(n); this.mech.push(n); } });
      return this.add(o, x, y, z, parent);
    }
    signalTower(x, y, z) {
      this.add(cyl(0.015, 0.25, mat(0x9ca3af)), x, y + 0.125, z);
      [[0xdc2626, 0.30], [0xf59e0b, 0.36], [0x16a34a, 0.42]].forEach(([c, h]) =>
        this.add(cyl(0.035, 0.06, mat(c)), x, y + h, z));
    }
    monitor(x, y, z) {
      this.add(cyl(0.02, 0.45, mat(0x374151)), x, y - 0.2, z);
      this.add(box(0.55, 0.36, 0.04, mat(0x111827, { rough: 0.2 })), x, y + 0.15, z).rotation.y = 0.35;
    }
  }

  /** 龍門式 XY 掃描機構(兩機型共用,參數不同) */
  function mechanism(b, p) {
    const { cz, bedY, beamY, hx, depth, light } = p;
    // 床台
    b.m('xy_stage', box(2 * hx + 0.1, 0.1, depth + 0.12, mat(C.base)), 0, bedY - 0.05, cz);
    for (const x of [-hx + 0.15, 0, hx - 0.15])
      b.m('xy_stage', box(0.05, 0.18, depth, mat(C.base)), x, bedY - 0.19, cz);            // 床台補強肋
    // Y 軸:線軌、螺桿、馬達
    for (const x of [-0.42, 0.42]) b.m('xy_stage', box(0.035, 0.03, depth, mat(C.rail)), x, bedY + 0.015, cz);
    const ys = b.m('xy_stage', screw(depth - 0.12, mat(C.screw, { metal: 0.5 })), 0, bedY + 0.04, cz);
    ys.rotation.x = Math.PI / 2;
    b.m('xy_stage', servo(mat(C.motor)), 0, bedY + 0.04, cz - depth / 2 - 0.1).rotation.y = Math.PI;
    // Y 移動台(真空吸附平台)
    const yg = b.add(new T.Group(), 0, 0, cz);
    for (const x of [-0.42, 0.42]) for (const z of [-0.22, 0.22])
      b.m('xy_stage', box(0.07, 0.04, 0.1, mat(C.slider, { metal: 0.5 })), x, bedY + 0.045, z, yg);
    b.m('xy_stage', box(0.08, 0.05, 0.08, mat(C.slider, { metal: 0.5 })), 0, bedY + 0.045, 0, yg);    // 螺帽座
    b.m('vacuum_pump', box(1.15, 0.035, 0.8, mat(C.table)), 0, bedY + 0.085, 0, yg);                  // 真空平台
    // 龍門:立柱 + 橫樑
    const bz = cz - 0.12;
    for (const s of [-1, 1]) b.m('xy_stage', box(0.12, beamY - bedY, 0.26, mat(C.column)), s * hx, (beamY + bedY) / 2, bz);
    b.m('xy_stage', box(2 * hx + 0.12, 0.16, 0.17, mat(C.beam)), 0, beamY, bz);
    // X 軸:線軌、螺桿、馬達
    for (const dy of [-0.055, 0.055]) b.m('xy_stage', box(2 * hx - 0.14, 0.025, 0.03, mat(C.rail)), 0, beamY + dy, bz + 0.1);
    const xs = b.m('xy_stage', screw(2 * hx - 0.2, mat(C.screw, { metal: 0.5 })), 0, beamY, bz + 0.105);
    xs.rotation.z = Math.PI / 2;
    b.m('xy_stage', servo(mat(C.motor)), hx + 0.15, beamY, bz + 0.1).rotation.y = Math.PI / 2;
    // X 移動座 + 掃描頭 + 照明
    const xg = b.add(new T.Group(), 0, 0, 0);
    b.m('xy_stage', box(0.2, 0.17, 0.035, mat(C.slider, { metal: 0.5 })), 0, beamY, bz + 0.135, xg);
    const head = new T.Group();
    head.add(box(0.17, 0.2, 0.17, mat(C.head, { metal: 0.4 })));
    head.add(at(cyl(0.05, 0.12, mat(0x0f172a, { rough: 0.2 })), 0, -0.16, 0));
    b.m('optics', head, 0, beamY - 0.16, bz + 0.24, xg);
    const lights = new T.Group();
    if (light === 'light_module') {
      [-1, 0, 1].forEach(i => lights.add(at(box(0.07, 0.03, 0.07, mat(C.light, { emissive: 0x334155 })), i * 0.09, 0, i ? 0 : 0.09)));
    } else {
      const ring = new T.Mesh(new T.TorusGeometry(0.08, 0.015, 8, 32), mat(C.light, { emissive: 0x334155 }));
      ring.rotation.x = Math.PI / 2;
      lights.add(ring);
    }
    b.m(light, lights, 0, beamY - 0.3, bz + 0.24, xg);
    // 底座內:真空幫浦、空壓濾芯
    b.m('vacuum_pump', box(0.38, 0.3, 0.3, mat(0x475569)), hx - 0.35, 0.22, cz - 0.3);
    b.m('air_filter', cyl(0.055, 0.26, mat(0x94a3b8, { metal: 0.4 })), -hx + 0.2, 0.42, cz - depth / 2 - 0.02);
    const y0 = yg.position.z;
    return { animate: t => {                                   // X 軸來回掃描,Y 平台逐步前後移動
      xg.position.x = (hx - 0.25) * Math.sin(t * 1.8);
      yg.position.z = y0 + (depth / 2 - 0.45) * Math.sin(t * 0.35);
    } };
  }

  // ---------- KLA (Orbotech) Fusion 22 ----------
  function fusion22(b) {
    const W = 1.9, D = 1.4, zc = -0.05;
    b.shell(box(W, 0.85, D, mat(0x2b2f36, { shell: true })), 0, 0.425, zc);
    const y0 = 0.95, y1 = 1.8, r = 0.28;
    b.shell(extrudeProfile(s => {
      s.moveTo(D / 2, y0); s.lineTo(-D / 2, y0); s.lineTo(-D / 2, y1 - r);
      s.quadraticCurveTo(-D / 2, y1, -D / 2 + r, y1); s.lineTo(D / 2, y1); s.closePath();
    }, W, mat(0xf2f2ee, { shell: true })), 0, 0, zc);
    b.shell(box(1.55, 0.36, 0.03, mat(0x0b0d10, { shell: true, rough: 0.15 })), 0.05, 1.12, zc + D / 2 + 0.005);
    b.shell(box(W - 0.1, 0.07, 0.02, mat(0xc7c9cc, { shell: true })), 0, 1.36, zc + D / 2 + 0.01);
    const fan = cyl(0.11, 0.04, mat(0x475569)); fan.rotation.z = Math.PI / 2;
    b.m('cooling_fan', fan, -W / 2 + 0.05, 1.5, zc - 0.25);
    b.add(box(0.5, 0.25, 0.4, mat(0x2b2f36)), -1.12, 0.78, 0.45);
    b.monitor(-1.12, 1.25, 0.45);
    b.signalTower(-0.7, y1, zc - 0.45);
    const k = mechanism(b, { cz: zc, bedY: 0.86, beamY: 1.5, hx: 0.78, depth: 1.25, light: 'light_module' });
    return { ...k, target: [0, 1.0, 0.1], cam: [2.5, 2.0, 2.9] };
  }

  // ---------- Orbotech Discovery ----------
  function discovery(b) {
    const W = 1.75, D = 1.35;
    b.shell(box(W, 0.72, D, mat(0xe8e2d0, { shell: true })), 0, 0.36, 0);
    b.shell(box(W + 0.05, 0.06, D + 0.1, mat(0x26324a, { shell: true })), 0, 0.75, 0.03);
    const y0 = 0.78, y1 = 1.5, HD = 1.15, zt = -0.15;
    const hood = e => s => {
      s.moveTo(HD / 2, y0); s.lineTo(HD / 2, y1); s.lineTo(-zt, y1);
      s.quadraticCurveTo(-HD / 2 - e, y1, -HD / 2 - e, y0); s.closePath();
    };
    b.shell(extrudeProfile(hood(0), 1.6, mat(0xefe9da, { shell: true })), 0, 0, -0.1);
    b.shell(extrudeProfile(hood(0.012), 0.85, mat(0x1f2937, { shell: true, rough: 0.2 })), -0.12, 0, -0.1);
    for (const [x, z] of [[-0.75, 0.55], [0.75, 0.55], [-0.75, -0.55], [0.75, -0.55]]) b.add(cyl(0.04, 0.06, mat(0x374151)), x, 0.03, z);
    const fan = cyl(0.1, 0.04, mat(0x475569)); fan.rotation.z = Math.PI / 2;
    b.m('cooling_fan', fan, W / 2 + 0.005, 0.45, -0.2);
    b.monitor(-1.0, 1.15, 0.55);
    b.signalTower(-0.62, y1, -0.5);
    const k = mechanism(b, { cz: 0, bedY: 0.85, beamY: 1.3, hx: 0.7, depth: 1.15, light: 'lamp' });
    return { ...k, target: [0, 0.95, 0.1], cam: [2.4, 1.9, 2.8] };
  }

  // ---------- Orbotech VRS 缺陷複判站:藍色機身 + 傾斜工作台 + 拱型橋架相機 ----------
  // 真空吸附台圓形吸盤紋路
  function circleTexture() {
    const c = document.createElement('canvas'); c.width = c.height = 512;
    const g = c.getContext('2d');
    g.fillStyle = '#111827'; g.fillRect(0, 0, 512, 512);
    g.strokeStyle = '#4b5563'; g.lineWidth = 3;
    for (let y = 0; y < 14; y++) for (let x = 0; x < 14; x++) {
      g.beginPath(); g.arc(18 + x * 36.5 + (y % 2) * 18, 18 + y * 36.5, 15, 0, Math.PI * 2); g.stroke();
    }
    const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping; return t;
  }

  // ---------- Orbotech VeriSmart(VRS):灰藍機身 + 傾斜吸盤台 + 後方拱型上蓋 + 左側弧形扶手鍵盤 ----------
  function vrs(b) {
    const blue = 0x5d7089, W = 1.4;
    b.shell(box(W, 0.45, 0.55, mat(blue, { shell: true })), 0, 0.62, 0.15);                 // 台面下機箱
    for (const [x, z] of [[-0.62, -0.45], [0.62, -0.45], [-0.62, 0.35], [0.62, 0.35]])
      b.add(box(0.05, 0.42, 0.05, mat(0x374151)), x, 0.21, z);                               // 支腳
    // 前方弧形扶手台(向左延伸成鍵盤台)
    b.shell(extrudeProfile(s => { s.moveTo(0.18, 0); s.lineTo(-0.18, 0); s.quadraticCurveTo(-0.2, 0.06, -0.12, 0.07); s.lineTo(0.18, 0.07); s.closePath(); },
      W + 0.1, mat(blue, { shell: true })), 0, 0.8, 0.52);
    const wing = new T.Shape();
    wing.moveTo(0, 0); wing.quadraticCurveTo(-0.35, 0.05, -0.62, 0.35); wing.quadraticCurveTo(-0.5, 0.48, -0.25, 0.36); wing.lineTo(0, 0.3); wing.closePath();
    const wg = new T.ExtrudeGeometry(wing, { depth: 0.06, bevelEnabled: false }); wg.rotateX(Math.PI / 2);
    b.shell(new T.Mesh(wg, mat(blue, { shell: true })), -0.55, 0.87, 0.42);
    b.add(box(0.24, 0.03, 0.17, mat(0xe7e5df)), -0.85, 0.88, 0.62).rotation.y = 0.35;      // 專用鍵盤(左側)
    for (let i = 0; i < 16; i++) {
      const k = b.add(box(0.035, 0.012, 0.03, mat([0x94a3b8, 0x16a34a, 0xdc2626, 0xeab308][i % 7 === 0 ? 1 + (i % 3) : 0])),
        -0.93 + (i % 4) * 0.05, 0.9, 0.57 + Math.floor(i / 4) * 0.035);
      k.rotation.y = 0.35;
    }
    b.add(cyl(0.025, 0.02, mat(0xdc2626)), 0.62, 0.89, 0.55);                                // 緊急停止
    b.monitor(-1.05, 1.25, 0.15);
    b.signalTower(-0.65, 1.55, -0.55);
    // 傾斜工作台(靠操作員端較低)
    const tilt = 0.44, tg = b.add(new T.Group(), 0, 1.02, -0.02);
    tg.rotation.x = tilt;
    const frame = box(W, 0.06, 1.05, mat(blue, { shell: true })); tg.add(at(frame, 0, -0.06, 0)); b.shells.push(frame);
    const plate = box(1.25, 0.03, 0.9, new T.MeshStandardMaterial({ map: circleTexture(), roughness: 0.4 }));
    b.m('vacuum_pump', plate, 0, -0.015, 0, tg);                                                      // 黑色圓形吸盤真空台
    b.add(box(0.9, 0.006, 0.62, mat(0xd9b48a)), 0, 0.003, 0.02, tg);                                // 待複判的板子
    for (const x of [-0.69, 0.69]) b.m('vrs_gantry', box(0.035, 0.03, 1.0, mat(C.rail)), x, 0.0, 0, tg);
    b.m('vrs_gantry', servo(mat(C.motor)), 0.69, 0.02, -0.58, tg).rotation.y = Math.PI;
    // 拱型橋架(沿台面上下移動)+ 相機座(沿橋架左右移動)
    const bg = b.add(new T.Group(), 0, 0, 0, tg);
    for (const x of [-0.69, 0.69]) b.m('vrs_gantry', box(0.08, 0.2, 0.12, mat(0x5b84c4)), x, 0.11, 0, bg);
    b.m('vrs_gantry', box(1.46, 0.08, 0.14, mat(0x5b84c4)), 0, 0.24, 0, bg);
    b.m('vrs_gantry', box(1.3, 0.02, 0.025, mat(C.rail)), 0, 0.24, 0.08, bg);
    const cg = b.add(new T.Group(), 0, 0, 0, bg);
    b.m('vrs_gantry', box(0.16, 0.12, 0.03, mat(C.slider, { metal: 0.5 })), 0, 0.24, 0.1, cg);
    const head = new T.Group();
    head.add(box(0.12, 0.16, 0.12, mat(C.head, { metal: 0.4 })));
    head.add(at(cyl(0.035, 0.08, mat(0x0f172a, { rough: 0.2 })), 0, -0.12, 0));
    b.m('optics', head, 0, 0.2, 0.18, cg);
    const ring = new T.Mesh(new T.TorusGeometry(0.055, 0.012, 8, 32), mat(C.light, { emissive: 0x334155 }));
    ring.rotation.x = Math.PI / 2;
    b.m('vrs_light', ring, 0, 0.04, 0.18, cg);
    // 後方上蓋
    b.shell(extrudeProfile(s => { s.moveTo(0.22, 0); s.lineTo(-0.22, 0); s.quadraticCurveTo(-0.24, 0.26, 0.05, 0.28); s.lineTo(0.22, 0.28); s.closePath(); },
      W + 0.05, mat(0x8592a3, { shell: true })), 0, 1.2, -0.6);                                    // 後方拱型上蓋(VeriSmart 標誌處)
    b.m('vacuum_pump', box(0.35, 0.28, 0.28, mat(0x475569)), 0.4, 0.2, -0.25);
    // 動作:相機在缺陷點之間移動(複判)
    let from = [0, 0], to = [0, 0], t0 = 0;
    return { target: [0, 0.95, 0.05], cam: [2.0, 1.9, 2.5], animate: t => {
      const k = Math.min(1, (t - t0) / 0.7), e = k * k * (3 - 2 * k);
      cg.position.x = from[0] + (to[0] - from[0]) * e;
      bg.position.z = from[1] + (to[1] - from[1]) * e;
      if (t - t0 > 1.4) { from = to; to = [(Math.random() - 0.5) * 0.8, (Math.random() - 0.5) * 0.6]; t0 = t; }
    } };
  }

  // ---------- Mania / Gardien PRECISE 治具(針床)電測機:上壓頭 + 上下治具疊板 + 導柱伸縮護套 + 藍色前台 ----------
  function mania(b) {
    const grey = 0xb9bec5, W = 1.45;
    b.shell(box(1.25, 0.72, 0.85, mat(0x9aa0a8, { shell: true })), 0, 0.36, -0.05);          // 下機箱
    // 藍色弧形前台 + 兩個半圓開口(啟動按鈕)
    const desk = new T.Shape();
    desk.moveTo(-W / 2 + 0.12, -0.22); desk.lineTo(W / 2 - 0.12, -0.22); desk.quadraticCurveTo(W / 2, -0.22, W / 2, -0.1);
    desk.lineTo(W / 2, 0.22); desk.lineTo(-W / 2, 0.22); desk.lineTo(-W / 2, -0.1); desk.quadraticCurveTo(-W / 2, -0.22, -W / 2 + 0.12, -0.22);
    const dg = new T.ExtrudeGeometry(desk, { depth: 0.2, bevelEnabled: false }); dg.rotateX(Math.PI / 2); dg.translate(0, 0.2, 0);
    b.shell(new T.Mesh(dg, mat(0x2b5aa0, { shell: true })), 0, 0.72, 0.38);
    for (const x of [-0.42, 0.42]) {
      const hole = cyl(0.11, 0.02, mat(0x111827), 24); hole.rotation.x = Math.PI / 2; b.add(hole, x, 0.8, 0.611);
      b.add(box(0.1, 0.05, 0.06, mat(0xeab308)), x, 0.77, 0.58);                              // 雙手啟動按鈕
    }
    b.add(cyl(0.03, 0.03, mat(0xdc2626)), 0.6, 0.93, 0.5);                                   // 緊急停止
    // 下壓板 + 下治具疊板(黃色多層板 + 藍色支撐柱)
    b.m('et_guide', box(1.2, 0.04, 0.8, mat(0xcbd5e1, { metal: 0.4 })), 0, 0.94, 0);
    const stack = (y0, dir) => {
      const g = new T.Group();
      for (let i = 0; i < 6; i++) g.add(at(box(0.72, 0.012, 0.56, mat(0xe9c46a)), 0, dir * i * 0.028, 0));
      for (const x of [-0.3, -0.1, 0.1, 0.3]) for (const z of [-0.24, 0.24])
        g.add(at(box(0.015, 0.15, 0.015, mat(0x2563eb)), x, dir * 0.07, z));
      return g;
    };
    b.m('et_pins', stack(0, 1), 0, 0.97, 0);
    // 四支導柱 + 前兩支伸縮護套
    for (const x of [-0.52, 0.52]) for (const z of [-0.3, 0.3]) {
      b.m('et_guide', cyl(0.03, 0.75, mat(0xd1d5db, { metal: 0.7, rough: 0.25 })), x, 1.33, z);
      if (z > 0) for (let i = 0; i < 14; i++)
        b.m('et_guide', new T.Mesh(new T.TorusGeometry(0.05, 0.012, 6, 18), mat(0x8b6b3d, { metal: 0.3 })), x, 1.0 + i * 0.022, z).rotation.x = Math.PI / 2;
    }
    // 上壓頭(會上下壓合):上壓板 + 上治具疊板 + 開關卡
    const head = b.add(new T.Group(), 0, 0, 0);
    b.m('et_guide', box(1.2, 0.05, 0.8, mat(0xcbd5e1, { metal: 0.4 })), 0, 1.5, 0, head);
    b.m('et_pins', stack(0, -1), 0, 1.46, 0, head);
    for (const x of [-0.18, 0.18]) b.m('et_grid', box(0.3, 0.02, 0.22, mat(0x15803d)), x, 1.55, -0.1, head);   // 開關卡 / 格點電路板
    b.m('et_press', cyl(0.07, 0.25, mat(0x94a3b8, { metal: 0.6 })), 0, 1.68, 0);                               // 壓合氣缸
    // 上機箱(標示 PRECISE / 機台編號處)
    b.shell(box(W, 0.4, 0.9, mat(grey, { shell: true })), 0, 1.95, -0.02);
    b.shell(box(W - 0.1, 0.12, 0.85, mat(grey, { shell: true })), 0, 1.7, -0.02);
    b.add(box(0.35, 0.2, 0.01, mat(0xffffff)), 0.45, 1.97, 0.435);                                             // 機台編號牌
    b.add(cyl(0.05, 0.08, mat(0xdc2626, { emissive: 0x440000 })), 0.55, 2.19, -0.3);                           // 警示燈
    b.m('et_press', box(0.18, 0.12, 0.1, mat(0x64748b)), -0.6, 0.55, -0.48);                                   // 空壓調壓 / 過濾組
    b.monitor(1.0, 1.3, 0.3);
    return { target: [0, 1.15, 0.1], cam: [2.2, 1.9, 2.9], animate: t => {                                      // 壓合循環
      const p = (t % 3) / 3, d = p < 0.2 ? p / 0.2 : p < 0.55 ? 1 : p < 0.75 ? 1 - (p - 0.55) / 0.2 : 0;
      head.position.y = -0.14 * d * d * (3 - 2 * d);
    } };
  }

  const MODELS = { fusion22, discovery, vrs, mania };

  // 數位孿生(全息)風格用的 HTML 疊層樣式
  const HOLO_CSS = `
  .aoi-ov{position:absolute;inset:0;pointer-events:none;font-family:system-ui,-apple-system,"PingFang TC",sans-serif;overflow:hidden}
  .aoi-ov svg{position:absolute;inset:0;width:100%;height:100%}
  .aoi-lb{position:absolute;transform:translate(-50%,-50%);background:rgba(8,47,73,.72);border:1px solid #22d3ee;color:#e0f2fe;
    padding:4px 8px;border-radius:6px;font-size:12px;line-height:1.35;white-space:nowrap;box-shadow:0 0 12px rgba(34,211,238,.35);backdrop-filter:blur(2px)}
  .aoi-lb b{color:#fff}.aoi-lb .v{font-size:15px;font-weight:700}
  .aoi-panel{position:absolute;left:10px;top:10px;width:min(210px,38%);background:rgba(8,47,73,.6);border:1px solid #22d3ee;border-radius:8px;
    color:#e0f2fe;padding:8px 10px;font-size:12px;box-shadow:0 0 16px rgba(34,211,238,.3)}
  .aoi-panel h4{margin:0 0 6px;font-size:14px;color:#fff}.aoi-panel .r{display:flex;justify-content:space-between;gap:8px;margin:2px 0}
  .aoi-hbar{height:6px;background:rgba(148,163,184,.3);border-radius:3px;margin:4px 0 6px}.aoi-hbar i{display:block;height:100%;border-radius:3px;background:#22d3ee}
  .aoi-gauges{position:absolute;right:10px;top:10px;bottom:10px;display:flex;flex-direction:column;justify-content:center;gap:8px;width:min(120px,24%)}
  .aoi-g{border-left:3px solid #22d3ee;padding:2px 0 2px 8px;color:#bae6fd;font-size:11px;background:linear-gradient(90deg,rgba(8,47,73,.6),transparent)}
  .aoi-g .v{font-size:20px;font-weight:700;color:#fff;line-height:1.1}.aoi-g .t{height:4px;background:rgba(148,163,184,.3);margin-top:3px}
  .aoi-g .t i{display:block;height:100%;background:#4ade80}`;
  function injectCss() {
    if (document.getElementById('aoi-holo-css')) return;
    const st = document.createElement('style'); st.id = 'aoi-holo-css'; st.textContent = HOLO_CSS; document.head.appendChild(st);
  }
  const hc = h => (h >= 80 ? '#4ade80' : h >= 60 ? '#fbbf24' : '#f87171');

  function mount(el, opt) {
    injectCss();
    const W = () => el.clientWidth, H = () => el.clientHeight;
    const scene = new T.Scene();
    const dark = matchMedia('(prefers-color-scheme: dark)').matches;
    const BG = new T.Color(dark ? 0x111827 : 0xf3f4f6), HOLO_BG = new T.Color(0x07111f);
    scene.background = BG;
    const camera = new T.PerspectiveCamera(40, W() / H(), 0.05, 50);
    const renderer = new T.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(W(), H());
    el.style.position = 'relative';
    el.appendChild(renderer.domElement);
    scene.add(new T.HemisphereLight(0xffffff, 0x666666, 0.9));
    const sun = new T.DirectionalLight(0xffffff, 0.8); sun.position.set(3, 5, 4); scene.add(sun);
    const floor = new T.Mesh(new T.CircleGeometry(3, 48), new T.MeshStandardMaterial({ color: dark ? 0x1f2937 : 0xd9dce1 }));
    floor.rotation.x = -Math.PI / 2; scene.add(floor);
    const grid = new T.GridHelper(8, 40, 0x22d3ee, 0x164e63);
    grid.material.transparent = true; grid.material.opacity = 0.45; grid.visible = false; scene.add(grid);

    const b = new Builder();
    const k = (MODELS[opt.model] || discovery)(b);
    scene.add(b.group);

    // 網格線(類 FEA 外觀)
    const wires = b.mech.map(n => {
      const l = new T.LineSegments(new T.WireframeGeometry(n.geometry),
        new T.LineBasicMaterial({ color: 0x0b1020, transparent: true, opacity: 0.35 }));
      l.visible = false; n.add(l); return l;
    });
    // 數位孿生:金色輪廓線 + 藍色半透明材質
    const holoMeshes = [];
    b.group.traverse(o => { if (o.isMesh && !o.userData.holoSkip) holoMeshes.push(o); });
    const edges = holoMeshes.map(n => {
      const l = new T.LineSegments(new T.EdgesGeometry(n.geometry, 28),
        new T.LineBasicMaterial({ color: 0xf5b942, transparent: true, opacity: 0.85 }));
      l.visible = false; l.userData.holoSkip = true; n.add(l); return l;
    });
    const isShell = new Set(); b.shells.forEach(s => s.traverse(o => { if (o.isMesh) isShell.add(o); }));
    holoMeshes.forEach(n => {
      n.userData.mat = n.material;
      n.userData.holo = new T.MeshBasicMaterial({ color: isShell.has(n) ? 0x60a5fa : 0x38bdf8, transparent: true,
        opacity: isShell.has(n) ? 0.06 : 0.3, depthWrite: false, blending: isShell.has(n) ? T.NormalBlending : T.AdditiveBlending });
    });

    // HTML 疊層:零件標示、左側資訊面板、右側儀表
    const ov = document.createElement('div'); ov.className = 'aoi-ov'; ov.style.display = 'none';
    ov.innerHTML = '<svg></svg>'; el.appendChild(ov);
    const svg = ov.querySelector('svg');
    const partsById = Object.fromEntries((opt.parts || []).map(p => [p.part_id, p]));
    const labels = [...new Set(b.pickables.map(o => o.userData.part))].filter(id => partsById[id]).map(id => {
      const p = partsById[id], d = document.createElement('div'); d.className = 'aoi-lb';
      d.innerHTML = `<b>${p.name}</b><br><span class="v" style="color:${hc(p.health)}">${p.health}%</span>`
        + (p.due_days != null ? ` · ${p.due_days <= 0 ? '需立即處理' : '約 ' + p.due_days + ' 天'}` : ' · 正常');
      ov.appendChild(d);
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      line.setAttribute('fill', 'none'); line.setAttribute('stroke', '#22d3ee'); line.setAttribute('stroke-width', '1.3');
      svg.appendChild(line);
      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('r', '3.5'); dot.setAttribute('fill', '#22d3ee'); svg.appendChild(dot);
      return { id, d, line, dot, meshes: b.pickables.filter(o => o.userData.part === id) };
    });
    if (opt.panel) {
      const pn = document.createElement('div'); pn.className = 'aoi-panel';
      pn.innerHTML = `<h4>${opt.panel.title}</h4><div class="r"><span>健康度</span><b style="color:${hc(opt.panel.health)}">${opt.panel.health}</b></div>
        <div class="aoi-hbar"><i style="width:${opt.panel.health}%;background:${hc(opt.panel.health)}"></i></div>`
        + (opt.panel.rows || []).map(([a, v]) => `<div class="r"><span>${a}</span><span>${v}</span></div>`).join('');
      ov.appendChild(pn);
    }
    if (opt.gauges && opt.gauges.length) {
      const g = document.createElement('div'); g.className = 'aoi-gauges';
      g.innerHTML = opt.gauges.slice(0, 5).map(x => `<div class="aoi-g">${x.name}<div class="v">${x.value}</div>
        <div class="t"><i style="width:${x.pct}%;background:${hc(x.pct)}"></i></div></div>`).join('');
      ov.appendChild(g);
    }
    const box = new T.Box3(), tmp = new T.Box3(), v3 = new T.Vector3();
    function placeLabels() {
      const w = W(), h = H(), used = [];
      labels.forEach(L => {
        box.makeEmpty(); L.meshes.forEach(m => box.union(tmp.setFromObject(m)));
        box.getCenter(v3).project(camera);
        const x = (v3.x + 1) / 2 * w, y = (1 - v3.y) / 2 * h;
        const side = x < w / 2 ? -1 : 1;
        let lx = Math.min(Math.max(x + side * Math.max(90, w * 0.14), 70), w - 70), ly = Math.min(Math.max(y - 30, 22), h - 22);
        while (used.some(u => Math.abs(u[0] - lx) < 120 && Math.abs(u[1] - ly) < 38)) ly += 40;   // 避免標示重疊
        used.push([lx, ly]);
        L.d.style.left = lx + 'px'; L.d.style.top = ly + 'px';
        const ex = lx - side * (L.d.offsetWidth / 2);
        L.line.setAttribute('points', `${x},${y} ${(x + ex) / 2},${ly} ${ex},${ly}`);
        L.dot.setAttribute('cx', x); L.dot.setAttribute('cy', y);
      });
    }

    const controls = new T.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.maxPolarAngle = Math.PI / 2 - 0.05;
    controls.minDistance = 0.8; controls.maxDistance = 8;
    function reset() { camera.position.set(...k.cam); controls.target.set(...k.target); controls.update(); }
    reset();

    let mode = 'xray', selected = null;
    function setMode(m) {
      mode = m;
      const holo = m === 'holo';
      holoMeshes.forEach(n => { n.material = holo ? n.userData.holo : n.userData.mat; });
      edges.forEach(e => { e.visible = holo; });
      b.shells.forEach(s => s.traverse(o => {
        if (!o.isMesh) return;
        o.visible = holo || m === 'xray' || m === 'solid';
        if (!holo) { o.material.opacity = m === 'xray' ? 0.25 : 1; o.material.depthWrite = m !== 'xray'; }
      }));
      wires.forEach(w => {
        w.visible = m === 'mesh' || holo;
        w.material.color.setHex(holo ? 0xf5b942 : 0x0b1020); w.material.opacity = holo ? 0.18 : 0.35;
      });
      b.mech.forEach(n => { if (n.material.isMeshStandardMaterial) { n.material.flatShading = m === 'mesh'; n.material.needsUpdate = true; } });
      scene.background = holo ? HOLO_BG : BG;
      floor.visible = !holo; grid.visible = holo;
      ov.style.display = holo ? '' : 'none';
      if (selected) select(selected, true);
    }
    setMode(opt.mode || 'xray');

    function select(id, quiet) {
      selected = id;
      b.pickables.forEach(o => {
        const on = o.userData.part === id;
        if (o.material.emissive) o.material.emissive.setHex(on ? 0x1d4ed8 : 0x000000);
        else o.material.color.setHex(on ? 0xfacc15 : 0x38bdf8);
      });
      labels.forEach(L => { L.d.style.borderColor = L.id === id ? '#facc15' : '#22d3ee'; });
      if (!quiet && opt.onPick) opt.onPick(id);
    }
    const ray = new T.Raycaster(), ptr = new T.Vector2();
    let down = null;
    renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
    renderer.domElement.addEventListener('pointerup', e => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6) return;
      const r = renderer.domElement.getBoundingClientRect();
      ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ptr, camera);
      const hit = ray.intersectObjects(b.pickables, false).find(h => h.object.visible);
      if (hit) select(hit.object.userData.part);
    });

    const ro = new ResizeObserver(() => { camera.aspect = W() / H(); camera.updateProjectionMatrix(); renderer.setSize(W(), H()); });
    ro.observe(el);

    // 動作模擬(各機型自訂)
    let anim = true, alive = true;
    const clock = new T.Clock();
    (function loop() {
      if (!alive) return;
      if (anim) k.animate(clock.getElapsedTime());
      controls.update();
      renderer.render(scene, camera);
      if (mode === 'holo') placeLabels();
      requestAnimationFrame(loop);
    })();

    return {
      select, reset, setMode,
      toggleAnim() { anim = !anim; if (anim) clock.start(); return anim; },
      dispose() { alive = false; ro.disconnect(); controls.dispose(); renderer.dispose(); el.innerHTML = ''; },
    };
  }

  window.AOI3D = { mount, MODELS: Object.keys(MODELS) };
})();
