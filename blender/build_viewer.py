# -*- coding: utf-8 -*-
"""build_viewer.py —— 生成《AG-1 结构剖视》交互页（three.js，单文件、离线）
按钮：整体视图 / 半剖视图 / 原理流向 / 自动旋转 / 重置
"""
import os
ROOT = os.environ.get("AG1_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HERE = os.path.dirname(os.path.abspath(__file__))
THREE_JS = os.path.join(ROOT, "_cpptest", "three.min.js")
MODEL_JSON = os.path.join(HERE, "out", "ag1_model_full.json")
OUT = os.path.join(ROOT, "反重力的真实物理模型", "AG-1结构剖视.html")

THREE = open(THREE_JS, "r", encoding="utf-8").read().replace("</script", "<\\/script")
MODEL = open(MODEL_JSON, "r", encoding="utf-8").read().replace("</", "<\\/")

# ---- 百万零件族参数（只注入参数与共享低模几何，实例在浏览器里按算法生成）----
import json as _json
try:
    import massparts as _MP
    _fams, _geoms = _MP.build_families()
    MASS_INFO = _json.dumps({"geoms": _geoms, "families": _fams},
                            ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    _tot = sum(len(_MP.gen_instances(f)) for f in _fams)
except Exception as _e:
    print("MASS INFO FAIL", _e)
    MASS_INFO = '{"geoms":{},"families":[]}'
    _tot = 0

CSS = """
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden;background:#05080d;color:#dfe9f2;
 font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif}
#app{position:fixed;inset:0}
#hud{position:fixed;left:20px;top:16px;pointer-events:none;max-width:min(560px,50vw)}
#hud h1{font-family:Georgia,"Songti SC",serif;font-size:1.28rem;margin:0 0 4px;font-weight:600}
#hud p{font-size:.8rem;color:#8fb6d4;margin:0;line-height:1.6}
#hud b{color:#ffd479}
#bar{position:fixed;left:50%;transform:translateX(-50%);bottom:18px;display:flex;gap:8px;flex-wrap:wrap;
 background:rgba(10,18,28,.86);border:1px solid #1d3348;border-radius:12px;padding:9px 12px;max-width:94vw}
.btn{background:#14304a;color:#cfe3f2;border:1px solid #27506f;border-radius:8px;padding:8px 14px;
 font-size:.84rem;cursor:pointer;white-space:nowrap}
.btn:hover{background:#1c4467}
.btn.on{background:#2f7fb8;border-color:#3f97d4;color:#fff}
.btn.flow.on{background:#1f8b5a;border-color:#2fb37a}
#legend{position:fixed;right:18px;bottom:18px;font-size:.75rem;color:#8fb6d4;text-align:right;line-height:1.9}
.sw{display:inline-block;width:22px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
#tip{position:fixed;right:18px;top:16px;font-size:.74rem;color:#6d8ba0;text-align:right;line-height:1.7}
"""

JS = r"""
const MODEL = __MODEL__;
const MASSINFO = __MASSINFO__;

const app = document.getElementById('app');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05080d);
scene.fog = new THREE.Fog(0x05080d, 14, 34);

const camera = new THREE.PerspectiveCamera(48, innerWidth/innerHeight, 0.05, 200);
const renderer = new THREE.WebGLRenderer({ antialias:true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.localClippingEnabled = true;
app.appendChild(renderer.domElement);
if (THREE.SRGBColorSpace) renderer.outputColorSpace = THREE.SRGBColorSpace;

// ---------- 环境反射（程序化渐变，离线）----------
function envTexture(){
  const c = document.createElement('canvas'); c.width = 512; c.height = 256;
  const g = c.getContext('2d');
  const grd = g.createLinearGradient(0,0,0,256);
  grd.addColorStop(0.00,'#8fa8c8');
  grd.addColorStop(0.42,'#3a4d66');
  grd.addColorStop(0.55,'#141b26');
  grd.addColorStop(1.00,'#05070b');
  g.fillStyle = grd; g.fillRect(0,0,512,256);
  // 两块亮斑，给金属一点高光变化
  const s1 = g.createRadialGradient(150,60,4,150,60,120); s1.addColorStop(0,'#ffffff'); s1.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle = s1; g.fillRect(0,0,512,256);
  const s2 = g.createRadialGradient(380,90,4,380,90,140); s2.addColorStop(0,'#bcd6ff'); s2.addColorStop(1,'rgba(188,214,255,0)');
  g.fillStyle = s2; g.fillRect(0,0,512,256);
  const t = new THREE.CanvasTexture(c);
  t.mapping = THREE.EquirectangularReflectionMapping;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
scene.environment = envTexture();

// ---------- 灯光 ----------
scene.add(new THREE.AmbientLight(0x8aa4c0, 0.22));
const l1 = new THREE.DirectionalLight(0xffffff, 1.05); l1.position.set(5,7,5); scene.add(l1);
const l2 = new THREE.DirectionalLight(0x88bbff, 0.55); l2.position.set(-6,3,-4); scene.add(l2);
const l3 = new THREE.DirectionalLight(0xffbbdd, 0.35); l3.position.set(2,-5,-6); scene.add(l3);

// ---------- 模型 ----------
const root = new THREE.Group();
root.rotation.x = -Math.PI/2;          // Blender Z-up -> three Y-up

// ============================================================
// 百万零件族：与 _blender/massparts.py 完全同一套算法
// ============================================================
const MHX = 1.62, MHY = 1.86, MHZ = 0.52;
function mSph(th, ph, k){
  return [MHX*k*Math.sin(ph)*Math.cos(th), MHY*k*Math.sin(ph)*Math.sin(th), MHZ*k*Math.cos(ph)];
}
function mNorm(th, ph){
  const p = mSph(th, ph, 1);
  let nx = p[0]/(MHX*MHX), ny = p[1]/(MHY*MHY), nz = p[2]/(MHZ*MHZ);
  const m = Math.hypot(nx, ny, nz) || 1;
  return [nx/m, ny/m, nz/m];
}
function mEll(a, b){
  return Math.PI*(3*(a+b) - Math.sqrt((3*a+b)*(a+3*b)));
}
function genShell(p){
  const out = [];
  let arc = 0, pv = null;
  const Np = 4000;
  for (let i=0;i<=Np;i++){
    const phi = p.phi0 + (p.phi1-p.phi0)*i/Np;
    const q = mSph(0, phi, p.k);
    if (pv) arc += Math.hypot(q[0]-pv[0], q[2]-pv[2]);
    pv = q;
  }
  const rows = Math.max(2, Math.floor(arc / p.pitch));
  for (let r=0;r<=rows;r++){
    const t = r/rows;
    const phi = p.phi0 + (p.phi1-p.phi0)*t;
    const a = MHX*p.k*Math.sin(phi), b = MHY*p.k*Math.sin(phi);
    const n = Math.max(3, Math.floor(mEll(a,b) / p.pitch));
    const off = (p.stagger && (r%2)) ? 0.5 : 0;
    for (let j=0;j<n;j++){
      const th = 2*Math.PI*(j+off)/n;
      const q = mSph(th, phi, p.k);
      const nn = mNorm(th, phi);
      out.push(q[0], q[1], q[2], nn[0], nn[1], nn[2]);
    }
  }
  return out;
}
function genRing(p){
  const out = [];
  for (const rr of p.rings){
    const z = rr[0], kx = rr[1];
    const s = Math.sqrt(Math.max(0, 1-(z/MHZ)*(z/MHZ)));
    const a = MHX*kx*s, b = MHY*kx*s;
    const n = Math.max(8, Math.floor(mEll(a,b) / p.pitch));
    for (let j=0;j<n;j++){
      const th = 2*Math.PI*j/n;
      const x = a*Math.cos(th), y = b*Math.sin(th);
      let nx = x/(MHX*MHX), ny = y/(MHY*MHY), nz = z/(MHZ*MHZ);
      const m = Math.hypot(nx,ny,nz) || 1;
      out.push(x, y, z, nx/m, ny/m, nz/m);
    }
  }
  return out;
}
function genCoil(p){
  const out = [];
  for (let i=0;i<p.turns;i++){
    const z = p.z0 + (i-(p.turns-1)*0.5)*p.dz;
    for (let j=0;j<p.seg;j++){
      const th = 2*Math.PI*j/p.seg;
      out.push(MHX*p.radius_k*Math.cos(th), MHY*p.radius_k*Math.sin(th), z, 0,0,1);
    }
  }
  return out;
}
function genNodes(p){
  const out = [];
  const ring = p.ring || 0.03, dz = p.dz || 0;
  for (const q of p.nodes){
    for (let j=0;j<p.per_node;j++){
      const a = 2*Math.PI*j/p.per_node;
      out.push(q[0]+ring*Math.cos(a), q[1]+ring*Math.sin(a), q[2]+dz, 0,0,1);
    }
  }
  return out;
}
function genFins(p){
  const out = [];
  for (const q of p.row){
    const n = p.per;
    for (let j=0;j<n;j++){
      const t = (j/(n-1)) - 0.5;
      out.push(q[0], q[1]+t*p.span, q[2], 0,1,0);
    }
  }
  return out;
}
function genGrille(p){
  const out = [];
  for (const q of p.centers){
    for (let r=0;r<p.rows;r++)
      for (let c=0;c<p.cols;c++)
        out.push(q[0]+(c-p.cols/2)*p.dw, q[1]+(r-p.rows/2)*p.dd, q[2], 0,0,1);
  }
  return out;
}
function genPcb(p){
  const out = [];
  const bs = [[-0.62,0.52,0.42,0.30],[0.58,0.50,0.38,0.28],[0.58,0.12,0.18,0.12],
              [-0.60,-0.10,0.24,0.16],[-0.60,-0.46,0.20,0.14],[0.60,-0.20,0.16,0.11],
              [0.0,-0.62,0.12,0.30]];
  const st = p.grid*3;
  for (const q of bs){
    const nx = Math.floor(q[2]/st), ny = Math.floor(q[3]/st);
    for (let i=0;i<nx;i++)
      for (let j=0;j<ny;j++)
        out.push(q[0]-q[2]/2+(i+0.5)*st, q[1]-q[3]/2+(j+0.5)*st, -0.04, 0,0,1);
  }
  return out;
}
function genFan(p){
  const out = [];
  let s = p.seed | 0;
  const n = p.count | 0;
  for (let k=0;k<n;k++){
    s = (16807*s) % 2147483647;
    const u1 = s/2147483647;
    s = (16807*s) % 2147483647;
    const u2 = s/2147483647;
    s = (16807*s) % 2147483647;
    const u3 = s/2147483647;
    const th = 2*Math.PI*u1;
    let rk = p.r0 + (p.r1-p.r0)*u2;
    const zz = p.z0 + (p.z1-p.z0)*u3;
    const lim = Math.sqrt(Math.max(0, 1-(zz/MHZ)*(zz/MHZ)));
    if (rk > lim*0.94) rk = lim*0.94;
    out.push(MHX*rk*Math.cos(th), MHY*rk*Math.sin(th), zz, 0,0,1);
  }
  return out;
}
function genSeams(p){
  const out = [];
  for (const phi of p.phis){
    const a = MHX*Math.sin(phi), b = MHY*Math.sin(phi);
    const n = Math.max(8, Math.floor(mEll(a,b) / p.pitch));
    for (let r=0;r<p.rows;r++){
      const dphi = (r-(p.rows-1)/2)*(p.gap/1.75);
      const ph = phi + dphi;
      if (!(ph > 0.03 && ph < Math.PI-0.03)) continue;
      for (let j=0;j<n;j++){
        const th = 2*Math.PI*j/n;
        const q = mSph(th, ph, 0.9995);
        const nn = mNorm(th, ph);
        out.push(q[0], q[1], q[2], nn[0], nn[1], nn[2]);
      }
    }
  }
  const Nphi = 240;
  for (let m=0;m<p.meridians;m++){
    const th0 = 2*Math.PI*m/p.meridians + Math.PI/p.meridians;
    for (let i=0;i<Nphi;i++){
      const ph = 0.2094 + (2.9322-0.2094)*i/Nphi;
      for (let r=0;r<p.rows;r++){
        const dth = (r-(p.rows-1)/2)*(p.gap/Math.max(0.05, MHX*Math.sin(ph)));
        const th = th0 + dth;
        const q = mSph(th, ph, 0.9995);
        const nn = mNorm(th, ph);
        out.push(q[0], q[1], q[2], nn[0], nn[1], nn[2]);
      }
    }
  }
  return out;
}
const MASSGEN = { shell: genShell, ring: genRing, coil: genCoil, nodes: genNodes,
                  fins: genFins, grille: genGrille, pcb_pads: genPcb,
                  node_fan: genFan, seams: genSeams };

const massRoot = new THREE.Group();
root.add(massRoot);
const massMeshes = [];
let massDensity = 0.25;

function buildMass(density){
  for (const m of massMeshes){ massRoot.remove(m); m.geometry.dispose(); m.material.dispose(); }
  massMeshes.length = 0;
  massDensity = density;
  const mtx = new THREE.Matrix4();
  const quat = new THREE.Quaternion();
  const zAxis = new THREE.Vector3(0,0,1);
  const pv = new THREE.Vector3(), nv = new THREE.Vector3(), sc = new THREE.Vector3(1,1,1);
  let total = 0;
  for (const fam of MASSINFO.families){
    const g0 = MASSINFO.geoms[fam.geo];
    if (!g0) continue;
    const pos = new Float32Array(g0.v.length);
    for (let i=0;i<g0.v.length;i++) pos[i] = g0.v[i]*0.001;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setIndex(g0.i);
    geo.computeVertexNormals();

    const fn = MASSGEN[fam.gen];
    if (!fn) continue;
    const inst = fn(fam.params);
    const nAll = inst.length/6;
    const n = Math.max(1, Math.floor(nAll*density));
    const step = nAll / n;

    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(fam.color[0], fam.color[1], fam.color[2]),
      metalness: fam.metal, roughness: fam.rough,
    });
    mat.envMapIntensity = 0.5;
    if (fam.es > 0){
      mat.emissive = new THREE.Color(fam.emit[0], fam.emit[1], fam.emit[2]);
      mat.emissiveIntensity = Math.min(2.0, fam.es*0.3);
    }
    const mesh = new THREE.InstancedMesh(geo, mat, n);
    for (let i=0;i<n;i++){
      const k = Math.floor(i*step)*6;
      pv.set(inst[k], inst[k+1], inst[k+2]);
      nv.set(inst[k+3], inst[k+4], inst[k+5]);
      if (nv.lengthSq() < 1e-9) nv.set(0,0,1); else nv.normalize();
      quat.setFromUnitVectors(zAxis, nv);
      mtx.compose(pv, quat, sc);
      mesh.setMatrixAt(i, mtx);
    }
    mesh.instanceMatrix.needsUpdate = true;
    mesh.userData.fam = fam.id;
    massRoot.add(mesh);
    massMeshes.push(mesh);
    total += nAll;
  }
  return total;
}
scene.add(root);

const materials = [];
const meshes = [];
for (const p of MODEL.parts){
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(p.v, 3));
  if (p.n && p.n.length === p.v.length){
    g.setAttribute('normal', new THREE.Float32BufferAttribute(p.n, 3));
  } else {
    g.setIndex(p.i);
    g.computeVertexNormals();
    g.setIndex(null);
  }
  g.setIndex(p.i);
  g.computeBoundingSphere();
  const m = new THREE.MeshStandardMaterial({
    color: new THREE.Color().setRGB(p.color[0], p.color[1], p.color[2]),
    metalness: p.metal, roughness: p.rough,
    transparent: p.alpha < 0.999, opacity: p.alpha,
    side: p.alpha < 0.999 ? THREE.DoubleSide : THREE.FrontSide,
  });
  m.envMapIntensity = 0.55;
  if (p.es > 0){
    m.emissive = new THREE.Color().setRGB(p.emit[0], p.emit[1], p.emit[2]);
    m.emissiveIntensity = Math.min(2.2, p.es * 0.28);
  }
  const mesh = new THREE.Mesh(g, m);
  mesh.name = p.name;
  root.add(mesh);
  materials.push(m); meshes.push(mesh);
}

// ---------- 机械组（起落架三节伸缩 / 线圈旋转 / 喷口摆动）----------
const mechGroups = {};
const teleMeshes = [];
MODEL.parts.forEach((p, idx) => {
  const mesh = meshes[idx];
  if (!p.mech || !p.pivot) return;
  const isGear = p.mech.indexOf('gear') === 0;
  const isSpin = p.mech.indexOf('spin') === 0;
  root.remove(mesh);

  if (isGear){
    const H = p.pivot;
    // ---- 舱门：每片独立铰接组 ----
    if (p.link === 'door'){
      let dg = mechGroups[p.mech];
      if (!dg){
        dg = new THREE.Group();
        dg.position.set(H[0], H[1], H[2]);
        const ang = Math.atan2(H[1], H[0]);
        dg.userData.kind = 'door';
        dg.userData.axis = new THREE.Vector3(-Math.sin(ang), Math.cos(ang), 0).normalize();
        dg.userData.sign = (p.mech.indexOf('doorL') >= 0) ? 1 : -1;
        root.add(dg);
        mechGroups[p.mech] = dg;
      }
      mesh.position.set(-H[0], -H[1], -H[2]);
      dg.add(mesh);
      return;
    }
    // ---- 整流罩：静态，跟着 root 走 ----
    if (p.link === 'cowl'){
      root.add(mesh);
      return;
    }
    // ---- 腿本体：一个髋组，内部零件按 tele 阶段做轴向平移 ----
    let hip = mechGroups[p.mech];
    if (!hip){
      hip = new THREE.Group();
      hip.position.set(H[0], H[1], H[2]);
      const ang = Math.atan2(H[1], H[0]);
      hip.userData.kind = 'gear';
      hip.userData.axis = new THREE.Vector3(-Math.sin(ang), Math.cos(ang), 0).normalize();
      root.add(hip);
      mechGroups[p.mech] = hip;
    }
    mesh.position.set(-H[0], -H[1], -H[2]);
    hip.add(mesh);
    // 可伸缩零件：记录基准位置 + 行程
    if (p.tele && p.tele[0] > 0 && p.dir){
      mesh.userData.basePos = mesh.position.clone();
      mesh.userData.stroke = p.tele[1];
      mesh.userData.teleDir = new THREE.Vector3(p.dir[0], p.dir[1], p.dir[2]).normalize();
      teleMeshes.push(mesh);
    }
    return;
  }

  let g = mechGroups[p.mech];
  if (!g){
    g = new THREE.Group();
    g.position.set(p.pivot[0], p.pivot[1], p.pivot[2]);
    if (isSpin){
      g.userData.kind = 'spin';
      g.userData.axis = new THREE.Vector3(0, 0, 1);
      g.userData.speed = (p.mech.indexOf('inner') >= 0 ? -1 : 1) * 1.05;
    } else {
      g.userData.kind = 'swing';
      g.userData.axis = new THREE.Vector3(0, 1, 0);
      g.userData.max = (p.pivot[0] > 0 ? 1 : -1) * 0.32;
    }
    g.userData.t = 0; g.userData.ang = 0;
    root.add(g);
    mechGroups[p.mech] = g;
  }
  mesh.position.set(-p.pivot[0], -p.pivot[1], -p.pivot[2]);
  g.add(mesh);
});
let gearT = 0, gearTarget = 0, nozzleTarget = 0;
let spinOn = true, spinRamp = 1;
const sstep = (x) => { x = x < 0 ? 0 : (x > 1 ? 1 : x); return x * x * (3 - 2 * x); };

// ---------- 半剖裁剪平面 ----------
const clipPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0.12).normalize(), 0.02);
let clipOn = false;
function applyClip(){
  for (const m of materials){
    m.clippingPlanes = clipOn ? [clipPlane] : null;
    m.clipShadows = true;
    m.needsUpdate = true;
  }
  for (const mesh of massMeshes){
    mesh.material.clippingPlanes = clipOn ? [clipPlane] : null;
    mesh.material.clipShadows = true;
    mesh.material.needsUpdate = true;
  }
}

// ---------- 原理流向 ----------
const flowGroup = new THREE.Group(); root.add(flowGroup);
const flowMats = [];
function flowPath(pts, color, dash){
  const g = new THREE.BufferGeometry().setFromPoints(pts.map(a => new THREE.Vector3(a[0],a[1],a[2])));
  const m = new THREE.LineDashedMaterial({ color, dashSize:dash||0.07, gapSize:0.05, transparent:true, opacity:0.95,
                                           depthTest:false, blending:THREE.AdditiveBlending });
  const line = new THREE.Line(g, m);
  line.computeLineDistances();
  line.renderOrder = 10;
  flowGroup.add(line); flowMats.push(m);
  // 箭头
  const a = pts[pts.length-2], b = pts[pts.length-1];
  const dir = new THREE.Vector3(b[0]-a[0], b[1]-a[1], b[2]-a[2]).normalize();
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.045, 0.14, 10),
    new THREE.MeshBasicMaterial({ color, transparent:true, opacity:0.95, depthTest:false, blending:THREE.AdditiveBlending }));
  cone.position.set(b[0], b[1], b[2]);
  cone.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0), dir);
  cone.renderOrder = 11;
  flowGroup.add(cone);
}
const CORE = [0, 0, 0.035];
// 能量：核 → 4 电源柜 → 2 喷口
for (const [bx,by] of [[0.72,0.72],[-0.72,0.72],[0.72,-0.72],[-0.72,-0.72]])
  flowPath([CORE, [bx*0.55, by*0.55, -0.02], [bx, by, -0.10]], 0xffc45a);
flowPath([[0.72,0.72,-0.10],[1.05,0.42,-0.06],[1.34,0.10,-0.04]], 0xffc45a);
flowPath([[-0.72,0.72,-0.10],[-1.05,0.42,-0.06],[-1.34,0.10,-0.04]], 0xffc45a);
// 冷却：核 → 2 泵
flowPath([[0.60,0,CORE[2]-0.18],[0.95,-0.10,-0.10],[1.12,-0.32,-0.03]], 0x3fd0ff, 0.05);
flowPath([[-0.60,0,CORE[2]-0.18],[-0.95,-0.10,-0.10],[-1.12,-0.32,-0.03]], 0x3fd0ff, 0.05);
// 场约束：绕核一圈（闭合）
(function(){
  const pts=[]; for(let i=0;i<=48;i++){ const a=i/48*Math.PI*2; pts.push([Math.cos(a)*0.52, Math.sin(a)*0.52, CORE[2]+0.10]); }
  flowPath(pts, 0x9b6bff, 0.05);
})();
flowGroup.visible = false;

// ---------- 爆炸视图 ----------
const explodeItems = [];
for (const m of meshes){
  if (m.parent !== root) continue;          // 起落架在 mech 组里，不参与
  m.geometry.computeBoundingSphere();
  const c = m.geometry.boundingSphere.center;   // Blender 局部坐标（Z-up）
  const rad = m.geometry.boundingSphere.radius;
  const r = Math.hypot(c.x, c.y);
  let dx, dy, dz, amt;
  if (rad > 2.0){ dx = 0; dy = 0; dz = 1; amt = 0.55; }            // 外壳
  else if (r < 0.8 && c.z > 0.02){ dx = 0; dy = 0; dz = 1; amt = 0.95; }  // 核系统
  else if (c.z < -0.12){                                          // 底部设备
    dx = r > 1e-6 ? c.x / r : 0; dy = r > 1e-6 ? c.y / r : 0; dz = -0.5; amt = 0.62;
  } else {                                                         // 其余径向
    dx = r > 1e-6 ? c.x / r : 0; dy = r > 1e-6 ? c.y / r : 0; dz = 0.25; amt = 0.66;
  }
  const L = Math.hypot(dx, dy, dz) || 1;
  explodeItems.push({
    m, base: m.position.clone(),
    dir: new THREE.Vector3(dx / L, dy / L, dz / L),
    amt
  });
}
let explodeOn = false, explodeT = 0;

// ---------- 轨道相机 ----------
let yaw = 0.72, pitch = 0.34, dist = 6.2, autoRot = true;
let drag=false, lx=0, ly=0;
const dom = renderer.domElement;
dom.addEventListener('mousedown', e=>{ drag=true; lx=e.clientX; ly=e.clientY; });
addEventListener('mouseup', ()=>drag=false);
addEventListener('mousemove', e=>{ if(!drag) return;
  yaw -= (e.clientX-lx)*0.006; pitch = Math.max(-0.2, Math.min(1.35, pitch + (e.clientY-ly)*0.006));
  lx=e.clientX; ly=e.clientY; });
dom.addEventListener('wheel', e=>{ e.preventDefault();
  dist = Math.max(3.0, Math.min(24, dist*(e.deltaY>0?1.1:0.9))); }, {passive:false});
function updateCam(){
  if (autoRot && !drag) yaw += 0.0022;
  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  const d2 = dist * (1 + explodeT * 0.62);   // 爆炸时自动拉远
  camera.position.set(d2*cp*Math.sin(yaw), d2*sp, d2*cp*Math.cos(yaw));
  camera.lookAt(0, -0.18, 0);
}

// ---------- UI ----------
const bFull = document.getElementById('bFull');
const bClip = document.getElementById('bClip');
const bFlow = document.getElementById('bFlow');
const bRot  = document.getElementById('bRot');
const bReset= document.getElementById('bReset');
function setClip(on){ clipOn = on; applyClip(); bClip.classList.toggle('on', on); bFull.classList.toggle('on', !on);
  document.getElementById('status').textContent = on ? '半剖视图（点击「整体视图」恢复）' : '整体视图（点击「半剖视图」剖开外壳）'; }
bFull.onclick = ()=> setClip(false);
bClip.onclick = ()=> setClip(true);
bFlow.onclick = ()=>{ flowGroup.visible = !flowGroup.visible; bFlow.classList.toggle('on', flowGroup.visible); };
const bExp = document.getElementById('bExp');
bExp.onclick = function(){ explodeOn = !explodeOn; this.classList.toggle('on', explodeOn); };

// ---------- 电气系统视图 / 板卡抽出 ----------
let elecOnly = false;
const pcbMeshes = [];
const grpOf = idx => (MODEL.parts[idx] && MODEL.parts[idx].grp) || 'body';
MODEL.parts.forEach((p, idx) => {
  const g = p.grp || 'body';
  if (g === 'pcb' || g === 'comp') pcbMeshes.push(meshes[idx]);
});
const bElec = document.getElementById('bElec');
bElec.onclick = function(){
  elecOnly = !elecOnly;
  this.classList.toggle('on', elecOnly);
  MODEL.parts.forEach((p, idx) => {
    const m = meshes[idx];
    if (!m) return;
    const g = p.grp || 'body';
    m.visible = elecOnly ? (g === 'pcb' || g === 'comp' || g === 'rack' || g === 'harness') : true;
  });
  for (const k in mechGroups) mechGroups[k].visible = !elecOnly;
  massRoot.visible = !elecOnly;
  if (elecOnly){ dist = 3.0; pitch = 0.88; setClip(false); }
  else { dist = 6.2; pitch = 0.34; }
  document.getElementById('status').textContent = elecOnly
    ? '电气系统：7 块板卡 · 185 器件 · 铜排 · 线束' : '整体视图';
};

let pcbExpOn = false, pcbExpT = 0;
const pcbBase = new Map();
pcbMeshes.forEach(m => { if (m) pcbBase.set(m, m.position.clone()); });
const bPcb = document.getElementById('bPcb');
bPcb.onclick = function(){
  pcbExpOn = !pcbExpOn;
  this.classList.toggle('on', pcbExpOn);
  if (pcbExpOn && !elecOnly) bElec.onclick();
};

// ---------- 百万零件：密度切换 ----------
let massFull = false;
const bMass = document.getElementById('bMass');
bMass.onclick = function(){
  massFull = !massFull;
  this.classList.toggle('on', massFull);
  const st = document.getElementById('status');
  st.textContent = massFull ? '正在生成百万零件…' : '正在恢复 25% 密度…';
  setTimeout(function(){
    const t0 = performance.now();
    const tot = buildMass(massFull ? 1.0 : 0.25);
    const dt = (performance.now() - t0) / 1000;
    st.textContent = '零件 ' + tot.toLocaleString() + ' 个 · ' +
      Math.round((massFull ? 1 : 0.25) * 100) + '% 密度 · 生成耗时 ' + dt.toFixed(1) + 's';
  }, 40);
};
bRot.onclick  = ()=>{ autoRot = !autoRot; bRot.classList.toggle('on', autoRot); };
bReset.onclick= ()=>{ yaw=0.72; pitch=0.34; dist=6.2; setClip(false); flowGroup.visible=false; bFlow.classList.remove('on'); resetMech(); };
const bGear = document.getElementById('bGear');
const bSpin = document.getElementById('bSpin');
const bNoz  = document.getElementById('bNoz');
bGear.onclick = function(){ gearTarget = gearTarget ? 0 : 1; this.classList.toggle('on', !!gearTarget); };
bSpin.onclick = function(){ spinOn = !spinOn; this.classList.toggle('on', spinOn); };
bNoz.onclick  = function(){ nozzleTarget = nozzleTarget ? 0 : 1; this.classList.toggle('on', !!nozzleTarget); };
function resetMech(){ gearTarget = 0; spinOn = true; nozzleTarget = 0;
  bGear.classList.remove('on'); bSpin.classList.add('on'); bNoz.classList.remove('on'); }

addEventListener('resize', ()=>{ camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight); });

// ---------- 主循环 ----------
const clock = new THREE.Clock();
function tick(){
  requestAnimationFrame(tick);
  const dt = clock.getDelta();
  for (const m of flowMats) m.dashOffset -= dt * 0.55;
  spinRamp += ((spinOn ? 1 : 0) - spinRamp) * Math.min(1, dt * 2.0);
  gearT += (gearTarget - gearT) * Math.min(1, dt * 3.2);
  // 三节伸缩：gearT 0~0.34 内从全伸出缩到最短
  const ext = 1 - sstep((gearT - 0.02) / 0.32);
  for (const m of teleMeshes){
    m.position.copy(m.userData.basePos)
      .addScaledVector(m.userData.teleDir, -m.userData.stroke * (1 - ext));
  }
  // 爆炸视图
  explodeT += ((explodeOn ? 1 : 0) - explodeT) * Math.min(1, dt * 2.6);
  if (explodeT > 0.001)
    for (const it of explodeItems)
      it.m.position.copy(it.base).addScaledVector(it.dir, it.amt * explodeT);
  else
    for (const it of explodeItems) it.m.position.copy(it.base);
  // 板卡抽出（沿板法向上抬）
  pcbExpT += ((pcbExpOn ? 1 : 0) - pcbExpT) * Math.min(1, dt * 2.4);
  if (pcbExpT > 0.001)
    for (const [m, b] of pcbBase){ m.position.copy(b); m.position.y -= pcbExpT * 0.40; }
  else
    for (const [m, b] of pcbBase) m.position.copy(b);
  for (const k in mechGroups){
    const g = mechGroups[k];
    const kind = g.userData.kind;
    if (kind === 'spin'){
      g.userData.ang += g.userData.speed * dt * spinRamp;
      g.quaternion.setFromAxisAngle(g.userData.axis, g.userData.ang);
    } else if (kind === 'gear'){
      // 多相位：三节先缩回 → 再整体翻转到水平贴壳
      const rotT = sstep((gearT - 0.34) / 0.36);
      g.quaternion.setFromAxisAngle(g.userData.axis, -0.68 * rotT);
    } else if (kind === 'door'){
      // 舱门：先开(0.02~0.16)，收好后再关(0.74~0.90)
      const open = sstep((gearT - 0.02) / 0.14) * (1 - sstep((gearT - 0.74) / 0.16));
      g.quaternion.setFromAxisAngle(g.userData.axis, 1.75 * g.userData.sign * open);
    } else {
      g.userData.t += (nozzleTarget - g.userData.t) * Math.min(1, dt * 3.2);
      g.quaternion.setFromAxisAngle(g.userData.axis, g.userData.max * g.userData.t);
    }
  }
  updateCam();
  renderer.render(scene, camera);
}
setClip(false);
bRot.classList.add('on');
tick();

// 首帧之后生成百万零件（避免阻塞首屏）
setTimeout(function(){
  const t0 = performance.now();
  const tot = buildMass(0.25);
  applyClip();
  const dt = (performance.now() - t0) / 1000;
  document.getElementById('status').textContent =
    '零件 ' + tot.toLocaleString() + ' 个（默认 25% 密度，' + dt.toFixed(1) + 's）· 点「零件满载」看全部';
}, 150);

// URL hash 直达视图：#elec 电气 / #cut 半剖 / #pcb 板卡抽出 / #gear 起落架
setTimeout(function(){
  const h = (location.hash || '').toLowerCase();
  if (h === '#elec') bElec.onclick();
  else if (h === '#cut') setClip(true);
  else if (h === '#pcb') bPcb.onclick();
  else if (h === '#gear') bGear.onclick();
  else if (h === '#exp') bExp.onclick();
  else if (h === '#mass'){ if (!massFull) bMass.onclick(); }
}, 300);
"""

HTML = ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>AG-1 结构剖视 · 交互</title>\n<style>" + CSS + "</style>\n</head>\n<body>\n"
        "<div id=\"app\"></div>\n"
        "<div id=\"hud\"><h1>AG-1 · 反重力飞行器结构剖视</h1>"
        "<p>负质量核约束系统 · 能源汇流 · 冷却回路 · 航电 · 座舱 · 推进 · 线束"
        "<br><span id=\"status\">整体视图</span></p></div>\n"
        "<div id=\"tip\">左键拖动旋转 · 滚轮缩放</div>\n"
        "<div id=\"bar\">"
        "<button class=\"btn\" id=\"bFull\">整体视图</button>"
        "<button class=\"btn\" id=\"bClip\">半剖视图</button>"
        "<button class=\"btn\" id=\"bElec\">电气系统</button>"
        "<button class=\"btn\" id=\"bPcb\">板卡抽出</button>"
        "<button class=\"btn\" id=\"bMass\">零件满载</button>"
        "<button class=\"btn\" id=\"bExp\">爆炸图</button>"
        "<button class=\"btn flow\" id=\"bFlow\">原理流向</button>"
        "<button class=\"btn\" id=\"bGear\">起落架收放</button>"
        "<button class=\"btn on\" id=\"bSpin\">线圈旋转</button>"
        "<button class=\"btn\" id=\"bNoz\">喷口摆动</button>"
        "<button class=\"btn\" id=\"bRot\">自动旋转</button>"
        "<button class=\"btn\" id=\"bReset\">重置</button>"
        "</div>\n"
        "<div id=\"legend\">"
        "<div><span class=\"sw\" style=\"background:#ffc45a\"></span>能量：核 → 汇流排 → 喷口</div>"
        "<div><span class=\"sw\" style=\"background:#3fd0ff\"></span>冷却：核 → 泵 → 散热</div>"
        "<div><span class=\"sw\" style=\"background:#9b6bff\"></span>场约束回路</div>"
        "</div>\n"
        "<script>" + THREE + "</script>\n"
        "<script>" + JS.replace("__MODEL__", MODEL).replace("__MASSINFO__", MASS_INFO) + "</script>\n</body>\n</html>\n")

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("wrote:", OUT)
print("size: %.2f MB" % (os.path.getsize(OUT) / 1024 / 1024))
