/* AOI 機台 3D 機構模型(外型依現場照片估計,內部機構為示意,尺寸單位:公尺,非原廠圖面)。
 *
 * AOI3D.mount(容器, {model:'fusion22'|'discovery'|'vrs', parts:[...], onPick:fn})
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
  function vrs(b) {
    const blue = 0x2f6fb8, W = 1.5;
    b.shell(box(W, 0.72, 1.0, mat(blue, { shell: true })), 0, 0.36, -0.05);                 // 底座
    b.shell(box(W, 0.06, 0.3, mat(blue, { shell: true })), 0, 0.84, 0.55);                   // 前方扶手台
    b.add(box(0.26, 0.03, 0.17, mat(0xe5e7eb)), 0.45, 0.885, 0.55);                         // 專用鍵盤
    for (let i = 0; i < 12; i++) b.add(box(0.035, 0.012, 0.03, mat(0x94a3b8)), 0.365 + (i % 4) * 0.055, 0.905, 0.5 + Math.floor(i / 4) * 0.045);
    b.monitor(-0.95, 1.2, 0.3);
    b.signalTower(-0.65, 1.55, -0.55);
    // 傾斜工作台(靠操作員端較低)
    const tilt = 0.44, tg = b.add(new T.Group(), 0, 1.02, -0.02);
    tg.rotation.x = tilt;
    const frame = box(W, 0.06, 1.05, mat(blue, { shell: true })); tg.add(at(frame, 0, -0.06, 0)); b.shells.push(frame);
    b.m('vacuum_pump', box(1.25, 0.03, 0.9, mat(0x111827, { rough: 0.3 })), 0, -0.015, 0, tg);       // 黑色真空吸附台
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
    b.shell(extrudeProfile(s => { s.moveTo(0.2, 0); s.lineTo(-0.2, 0); s.quadraticCurveTo(-0.2, 0.22, 0.05, 0.25); s.lineTo(0.2, 0.25); s.closePath(); },
      W, mat(0x3b82c4, { shell: true })), 0, 1.22, -0.62);
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

  const MODELS = { fusion22, discovery, vrs };

  function mount(el, opt) {
    const W = () => el.clientWidth, H = () => el.clientHeight;
    const scene = new T.Scene();
    const dark = matchMedia('(prefers-color-scheme: dark)').matches;
    scene.background = new T.Color(dark ? 0x111827 : 0xf3f4f6);
    const camera = new T.PerspectiveCamera(40, W() / H(), 0.05, 50);
    const renderer = new T.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(W(), H());
    el.appendChild(renderer.domElement);
    scene.add(new T.HemisphereLight(0xffffff, 0x666666, 0.9));
    const sun = new T.DirectionalLight(0xffffff, 0.8); sun.position.set(3, 5, 4); scene.add(sun);
    const floor = new T.Mesh(new T.CircleGeometry(3, 48), new T.MeshStandardMaterial({ color: dark ? 0x1f2937 : 0xd9dce1 }));
    floor.rotation.x = -Math.PI / 2; scene.add(floor);

    const b = new Builder();
    const k = (MODELS[opt.model] || discovery)(b);
    scene.add(b.group);

    // 網格線(類 FEA 外觀),預設隱藏
    const wires = b.mech.map(n => {
      const l = new T.LineSegments(new T.WireframeGeometry(n.geometry),
        new T.LineBasicMaterial({ color: 0x0b1020, transparent: true, opacity: 0.35 }));
      l.visible = false; n.add(l); return l;
    });

    const controls = new T.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.maxPolarAngle = Math.PI / 2 - 0.05;
    controls.minDistance = 0.8; controls.maxDistance = 8;
    function reset() { camera.position.set(...k.cam); controls.target.set(...k.target); controls.update(); }
    reset();

    function setMode(mode) {
      b.shells.forEach(s => s.traverse(o => {
        if (!o.isMesh) return;
        o.visible = mode === 'xray' || mode === 'solid';
        o.material.opacity = mode === 'xray' ? 0.25 : 1;
        o.material.depthWrite = mode !== 'xray';
      }));
      wires.forEach(w => { w.visible = mode === 'mesh'; });
      b.mech.forEach(n => { n.material.flatShading = mode === 'mesh'; n.material.needsUpdate = true; });
    }
    setMode('xray');

    let selected = null;
    function select(id) {
      selected = id;
      b.pickables.forEach(o => o.material.emissive.setHex(o.userData.part === id ? 0x1d4ed8 : 0x000000));
      opt.onPick && opt.onPick(id);
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
      if (anim) {
        const t = clock.getElapsedTime();
        k.animate(t);
      }
      controls.update();
      renderer.render(scene, camera);
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
