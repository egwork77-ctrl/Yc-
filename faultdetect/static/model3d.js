/* AOI 機台 3D 示意模型(依現場照片估計外型,尺寸單位:公尺,非原廠圖面)。
 * 用法:AOI3D.mount(容器, {model:'fusion22'|'discovery', parts:[...], onPick:fn})
 * 內部零件以統一顏色顯示,點選後反白並回呼 onPick(part_id)。
 */
(function () {
  const T = THREE;
  const PART_COLOR = 0x94a3b8;

  function mat(color, o = {}) {
    return new T.MeshStandardMaterial({ color, roughness: o.rough ?? 0.6, metalness: o.metal ?? 0.1,
      transparent: !!o.shell, opacity: 1, emissive: o.emissive ?? 0x000000 });
  }

  function box(w, h, d, m) { return new T.Mesh(new T.BoxGeometry(w, h, d), m); }
  function cyl(r, h, m, seg = 24) { return new T.Mesh(new T.CylinderGeometry(r, r, h, seg), m); }
  function at(obj, x, y, z) { obj.position.set(x, y, z); return obj; }

  // 側面輪廓(z: 前為正, y: 上)沿 X 方向擠出成寬度 w 的外殼
  function extrudeProfile(points, w, m) {
    const s = new T.Shape();
    points(s);
    const g = new T.ExtrudeGeometry(s, { depth: w, bevelEnabled: false, curveSegments: 24 });
    g.rotateY(Math.PI / 2);
    g.translate(-w / 2, 0, 0);
    return new T.Mesh(g, m);
  }

  class Builder {
    constructor(parts) {
      this.group = new T.Group();
      this.shells = [];
      this.pickables = [];
      this.parts = Object.fromEntries((parts || []).map(p => [p.part_id, p]));
    }
    add(obj, x = 0, y = 0, z = 0) { at(obj, x, y, z); this.group.add(obj); return obj; }
    shell(obj, x, y, z) { this.add(obj, x, y, z); this.shells.push(obj); return obj; }
    part(id, obj, x, y, z) {
      obj.traverse(o => {
        if (o.isMesh) {
          o.material = mat(PART_COLOR, { rough: 0.35, metal: 0.4 });
          o.userData.part = id;
          this.pickables.push(o);
        }
      });
      obj.userData.part = id;
      return this.add(obj, x, y, z);
    }
    signalTower(x, y, z) {
      this.add(cyl(0.015, 0.25, mat(0x9ca3af)), x, y + 0.125, z);
      [[0xdc2626, 0.30], [0xf59e0b, 0.36], [0x16a34a, 0.42]].forEach(([c, h]) =>
        this.add(cyl(0.035, 0.06, mat(c, { emissive: c === 0xdc2626 ? 0x330000 : 0 })), x, y + h, z));
    }
    monitor(x, y, z) {
      this.add(cyl(0.02, 0.45, mat(0x374151)), x, y - 0.2, z);
      const scr = this.add(box(0.55, 0.36, 0.04, mat(0x111827, { rough: 0.2 })), x, y + 0.15, z);
      scr.rotation.y = 0.35;
    }
  }

  // ---------- KLA (Orbotech) Fusion 22:方型白色上蓋 + 深灰底座 + 前方抽屜式真空平台 ----------
  function fusion22(b) {
    const W = 1.9, D = 1.4, zc = -0.05;
    const dark = mat(0x2b2f36), white = mat(0xf2f2ee, { shell: true });
    b.shell(box(W, 0.85, D, mat(0x2b2f36, { shell: true })), 0, 0.425, zc);              // 底座
    b.add(box(1.5, 0.18, 0.04, mat(0x1f2329)), 0, 0.6, zc + D / 2 + 0.01);              // 前方抽屜面
    const y0 = 0.95, y1 = 1.8, r = 0.28;
    b.shell(extrudeProfile(s => {                                                       // 上蓋(前上圓角)
      s.moveTo(D / 2, y0); s.lineTo(-D / 2, y0); s.lineTo(-D / 2, y1 - r);
      s.quadraticCurveTo(-D / 2, y1, -D / 2 + r, y1); s.lineTo(D / 2, y1); s.closePath();
    }, W, white), 0, 0, zc);
    b.shell(box(W, 0.12, D, mat(0x2b2f36, { shell: true })), 0, 0.9, zc);                // 腰帶
    b.add(box(1.55, 0.36, 0.03, mat(0x0b0d10, { rough: 0.15 })), 0.05, 1.12, zc + D / 2 + 0.005); // 前方開口
    b.add(box(W - 0.1, 0.07, 0.02, mat(0xc7c9cc)), 0, 1.36, zc + D / 2 + 0.01);         // 灰色飾條
    for (let i = 0; i < 6; i++) b.add(box(0.01, 0.03, 0.18, mat(0x6b7280)), -W / 2 - 0.005, 1.55 - i * 0.05, zc - 0.25); // 側面散熱孔
    b.part('vacuum_pump', box(1.3, 0.05, 0.85, dark), 0.05, 0.98, zc + D / 2 + 0.3);    // 前方真空平台(抽屜)
    b.add(box(0.5, 0.25, 0.4, dark), -1.12, 0.78, 0.45);                                // 左前鍵盤台
    b.monitor(-1.12, 1.25, 0.45);
    b.signalTower(-0.7, y1, zc - 0.45);
    // 內部零件
    b.part('xy_stage', box(0.06, 0.05, 1.25, null), -0.55, 1.0, zc);
    b.part('xy_stage', box(0.06, 0.05, 1.25, null), 0.65, 1.0, zc);
    b.part('xy_stage', box(1.5, 0.08, 0.1, null), 0.05, 1.55, zc - 0.05);               // 掃描橫樑
    const head = new T.Group();
    head.add(box(0.32, 0.28, 0.26, null));
    head.add(at(cyl(0.06, 0.14, null), 0, -0.2, 0));
    b.part('optics', head, 0.05, 1.38, zc - 0.05);
    const lights = new T.Group();
    [-0.13, 0, 0.13].forEach((dx, i) => lights.add(at(box(0.09, 0.04, 0.2, null), dx, 0, i === 1 ? 0.12 : 0)));
    b.part('light_module', lights, 0.05, 1.12, zc - 0.05);
    const fan = cyl(0.11, 0.04, null); fan.rotation.z = Math.PI / 2;
    b.part('cooling_fan', fan, -W / 2 + 0.05, 1.5, zc - 0.25);
    b.part('air_filter', cyl(0.06, 0.28, null), 0.75, 0.45, zc - D / 2 - 0.08);
    b.part('vacuum_pump', box(0.4, 0.32, 0.32, null), 0.5, 0.25, zc - 0.35);
    return { target: [0, 0.9, 0.1], cam: [2.6, 2.0, 3.0] };
  }

  // ---------- Orbotech Discovery:米色底座 + 圓弧頂罩 + 深藍工作台 ----------
  function discovery(b) {
    const W = 1.75, D = 1.35, cream = mat(0xe8e2d0, { shell: true });
    b.shell(box(W, 0.72, D, cream), 0, 0.42, 0);                                          // 底座
    for (let i = 0; i < 5; i++) b.add(box(W - 0.3, 0.012, 0.01, mat(0xa8a196)), 0, 0.3 + i * 0.05, D / 2 + 0.005); // 前方格柵
    b.add(box(W + 0.05, 0.08, D + 0.1, mat(0x26324a)), 0, 0.82, 0.03);                     // 深藍工作台
    const y0 = 0.86, y1 = 1.5, HD = 1.15, zt = -0.15;
    const hood = profile => s => {
      s.moveTo(HD / 2, y0); s.lineTo(HD / 2, y1); s.lineTo(-zt, y1);
      s.quadraticCurveTo(-HD / 2 - profile, y1, -HD / 2 - profile, y0); s.closePath();
    };
    b.shell(extrudeProfile(hood(0), 1.5, mat(0xefe9da, { shell: true })), 0, 0, -0.1);    // 圓弧頂罩
    b.shell(extrudeProfile(hood(0.012), 0.85, mat(0x1f2937, { shell: true, rough: 0.2 })), -0.12, 0, -0.1); // 深色視窗
    for (const [x, z] of [[-0.75, 0.55], [0.75, 0.55], [-0.75, -0.55], [0.75, -0.55]]) b.add(cyl(0.04, 0.06, mat(0x374151)), x, 0.03, z);
    b.monitor(-1.0, 1.15, 0.55);
    b.signalTower(-0.62, y1, -0.5);
    // 內部零件
    b.part('xy_stage', box(0.06, 0.04, 1.1, null), -0.5, 0.88, 0);
    b.part('xy_stage', box(0.06, 0.04, 1.1, null), 0.5, 0.88, 0);
    b.part('xy_stage', box(1.2, 0.07, 0.09, null), 0, 1.33, -0.1);
    const head = new T.Group();
    head.add(box(0.3, 0.24, 0.24, null));
    head.add(at(cyl(0.055, 0.12, null), 0, -0.17, 0));
    b.part('optics', head, 0, 1.18, -0.1);
    const tube = cyl(0.03, 0.9, null); tube.rotation.z = Math.PI / 2;
    b.part('lamp', tube, 0, 1.0, 0.12);
    const fan = cyl(0.1, 0.04, null); fan.rotation.z = Math.PI / 2;
    b.part('cooling_fan', fan, W / 2 + 0.005, 0.45, -0.2);
    b.part('air_filter', cyl(0.06, 0.28, null), -0.6, 0.4, -D / 2 - 0.08);
    b.part('vacuum_pump', box(0.4, 0.3, 0.3, null), 0.45, 0.25, -0.3);
    return { target: [0, 0.85, 0.1], cam: [2.4, 1.9, 2.9] };
  }

  const MODELS = { fusion22, discovery };

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

    const b = new Builder(opt.parts);
    const view = (MODELS[opt.model] || discovery)(b);
    scene.add(b.group);

    const controls = new T.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.maxPolarAngle = Math.PI / 2 - 0.05;
    controls.minDistance = 1; controls.maxDistance = 8;
    function reset() { camera.position.set(...view.cam); controls.target.set(...view.target); controls.update(); }
    reset();

    let xray = true;
    function setXray(v) {
      xray = v;
      b.shells.forEach(s => s.traverse(o => { if (o.isMesh) { o.material.opacity = v ? 0.28 : 1; o.material.depthWrite = !v; } }));
    }
    setXray(true);

    let selected = null;
    function select(id) {
      selected = id;
      b.pickables.forEach(o => o.material.emissive.setHex(o.userData.part === id ? 0x3b82f6 : 0x000000));
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
      const hit = ray.intersectObjects(b.pickables, false)[0];
      if (hit) select(hit.object.userData.part);
    });

    const ro = new ResizeObserver(() => { camera.aspect = W() / H(); camera.updateProjectionMatrix(); renderer.setSize(W(), H()); });
    ro.observe(el);

    let alive = true;
    (function loop() {
      if (!alive) return;
      controls.update();
      renderer.render(scene, camera);
      requestAnimationFrame(loop);
    })();

    return {
      select, reset, toggleXray() { setXray(!xray); return xray; },
      dispose() { alive = false; ro.disconnect(); controls.dispose(); renderer.dispose(); el.innerHTML = ''; },
    };
  }

  window.AOI3D = { mount, MODELS: Object.keys(MODELS) };
})();
