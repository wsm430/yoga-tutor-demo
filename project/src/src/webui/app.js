"use strict";

// ---------------------------------------------------------------- constants
const FRAME_WIDTH = 640;          // JPEG width sent to Python
const MIN_FRAME_GAP_MS = 80;      // ~12 fps max
const VOICE_GAP_MS = 3500;

const CONNECTIONS = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [25, 27], [24, 26], [26, 28],
  [27, 29], [29, 31], [27, 31], [28, 30], [30, 32], [28, 32],
  [15, 17], [15, 19], [17, 19], [16, 18], [16, 20], [18, 20],
];
const JOINT_VERTEX = {
  left_shoulder: 11, right_shoulder: 12, left_elbow: 13, right_elbow: 14,
  left_hip: 23, right_hip: 24, left_knee: 25, right_knee: 26,
};
const JOINT_ORDER = [
  "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
  "left_hip", "right_hip", "left_knee", "right_knee",
];
const STATE_TEXT = {
  no_pose: "未检测到人", partial: "身体不完整", holding: "保持不动", evaluating: "评估中",
};

// ---------------------------------------------------------------- dom
const $ = (id) => document.getElementById(id);
const video = $("video");
const overlay = $("overlay");
const octx = overlay.getContext("2d");
const grab = document.createElement("canvas");
const gctx = grab.getContext("2d");

// ---------------------------------------------------------------- state
const app = {
  running: false,
  stream: null,
  inFlight: false,
  last: null,             // last server response
  status: null,           // last /api/status
  poses: [],
  mirror: true,
  voice: false,
  lastSpoken: "",
  lastSpokenAt: 0,
  wasGood: false,
  stats: null,
  perf: { ms: 0, server: 0, fps: 0, frames: 0, since: performance.now() },
};

function newStats() {
  return { start: null, active: 0, good: 0, scores: [], lastTick: null };
}
app.stats = newStats();

// ---------------------------------------------------------------- api
async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function toast(text, ms = 2200) {
  const el = $("toast");
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, ms);
}

// ---------------------------------------------------------------- poses
async function loadPoses() {
  const data = await api("/api/poses");
  app.poses = data.poses;
  renderPoseGrid(data.current);
}

function renderPoseGrid(currentId) {
  const grid = $("poseGrid");
  grid.innerHTML = "";
  for (const pose of app.poses) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "pose-card" + (pose.id === currentId ? " current" : "");
    card.innerHTML = `
      <div class="thumb">${pose.image ? `<img loading="lazy" src="${pose.image}" alt="">` : "<span class='muted small'>无参考图</span>"}</div>
      <strong></strong><small></small>`;
    card.querySelector("strong").textContent = pose.label;
    card.querySelector("small").textContent = pose.name;
    card.addEventListener("click", () => selectPose(pose.id));
    grid.appendChild(card);
  }
}

async function selectPose(id) {
  try {
    const status = await api("/api/pose", { id });
    applyStatus(status);
    renderPoseGrid(id);
    $("poseModal").hidden = true;
    app.stats = newStats();
    app.wasGood = false;
    renderStats();
    renderJoints(null);
    toast(`已切换到 ${status.pose.label}`);
  } catch (err) {
    toast(`切换失败：${err.message}`);
  }
}

function applyStatus(status) {
  app.status = status;
  $("poseLabel").textContent = status.pose.label;
  $("refName").textContent = status.pose.name;
  const pose = app.poses.find((p) => p.id === status.pose.id);
  const img = $("refImg");
  if (pose && pose.image) {
    img.src = pose.image;
    img.hidden = false;
    $("refEmpty").hidden = true;
  } else {
    img.hidden = true;
    $("refEmpty").hidden = false;
  }
  renderHaptic(status.haptic, null);
}

// ---------------------------------------------------------------- haptic ui
function renderHaptic(h, response) {
  if (!h) return;
  const pill = $("bandPill");
  const name = h.transport === "ble" ? "蓝牙" : h.transport === "serial" ? "USB" : "";
  let cls = "pill-off", text = "腕带：未启用";
  if (h.transport !== "none") {
    if (h.connected) { cls = "pill-on"; text = `腕带已连接（${name}）`; }
    else if (h.state === "connecting") { cls = "pill-wait"; text = `正在连接腕带（${name}）…`; }
    else { cls = "pill-err"; text = `腕带未连接（${name}）`; }
  }
  pill.className = "pill " + cls;
  $("bandText").textContent = text;
  $("reconnectBtn").hidden = h.transport === "none";
  const chk = $("hapticChk");
  chk.checked = h.enabled;
  chk.disabled = h.transport === "none";

  const working = new Set(h.working_motors);
  const wanted = response && response.guidance ? response.guidance.motor : null;
  document.querySelectorAll(".motor").forEach((btn) => {
    const m = Number(btn.dataset.motor);
    btn.classList.toggle("broken", !working.has(m));
    btn.classList.toggle("active", h.active_motor === m);
    btn.classList.toggle("wanted", wanted === m && h.active_motor !== m);
  });

  let line = "腕带：未震动";
  const hg = response && response.haptic_guidance;
  if (!h.enabled) line = "腕带震动已关闭";
  else if (!h.connected) line = "腕带未连接，仅文字/语音提示";
  else if (hg && hg.sent) line = `正在震动：${hg.motor_label}（${hg.joint_label}）`;
  else if (response && response.guidance && !response.guidance.motor_working)
    line = `该提示需要 ${response.guidance.motor_label}，此马达未接通`;
  $("hapticLine").textContent = line;
}

// ---------------------------------------------------------------- camera
async function listCameras() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const sel = $("cameraSel");
    const current = sel.value;
    sel.innerHTML = "";
    devices.filter((d) => d.kind === "videoinput").forEach((d, i) => {
      const opt = document.createElement("option");
      opt.value = d.deviceId;
      opt.textContent = d.label || `摄像头 ${i + 1}`;
      sel.appendChild(opt);
    });
    if (current) sel.value = current;
    sel.hidden = sel.options.length < 2;
  } catch (_) { /* ignore */ }
}

async function startCamera() {
  const deviceId = $("cameraSel").value;
  const constraints = {
    audio: false,
    video: deviceId ? { deviceId: { exact: deviceId }, width: 1280, height: 720 }
                    : { width: 1280, height: 720, facingMode: "user" },
  };
  app.stream = await navigator.mediaDevices.getUserMedia(constraints);
  video.srcObject = app.stream;
  await video.play();
  $("placeholder").hidden = true;
  app.running = true;
  $("startBtn").textContent = "■ 停止";
  $("startBtn").classList.remove("primary");
  if (!app.stats.start) app.stats.start = performance.now();
  app.stats.lastTick = performance.now();
  listCameras();
  loop();
}

function stopCamera() {
  app.running = false;
  if (app.stream) app.stream.getTracks().forEach((t) => t.stop());
  app.stream = null;
  video.srcObject = null;
  $("placeholder").hidden = false;
  $("startBtn").textContent = "▶ 开始";
  $("startBtn").classList.add("primary");
  octx.clearRect(0, 0, overlay.width, overlay.height);
  setBanner("idle", "已暂停", "点击「开始」继续", null, 0);
  api("/api/reset", {}).catch(() => {});  // stops the motors
}

// ---------------------------------------------------------------- frame loop
async function loop() {
  while (app.running) {
    const t0 = performance.now();
    if (video.readyState >= 2 && !app.inFlight) {
      await sendFrame();
    }
    const wait = Math.max(0, MIN_FRAME_GAP_MS - (performance.now() - t0));
    await new Promise((r) => setTimeout(r, wait));
  }
}

async function sendFrame() {
  const w = video.videoWidth, h = video.videoHeight;
  if (!w || !h) return;
  const scale = FRAME_WIDTH / w;
  grab.width = FRAME_WIDTH;
  grab.height = Math.round(h * scale);
  gctx.drawImage(video, 0, 0, grab.width, grab.height);
  const blob = await new Promise((r) => grab.toBlob(r, "image/jpeg", 0.75));
  if (!blob) return;

  app.inFlight = true;
  const t0 = performance.now();
  try {
    const res = await fetch("/api/frame", { method: "POST", body: blob, headers: { "Content-Type": "image/jpeg" } });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    if (!app.running) return;
    app.perf.ms = performance.now() - t0;
    app.perf.server = data.process_ms || 0;
    app.perf.frames += 1;
    handleResponse(data);
  } catch (err) {
    setBanner("bad", "连接服务器失败", err.message, null, 0);
    await new Promise((r) => setTimeout(r, 800));
  } finally {
    app.inFlight = false;
  }
}

// ---------------------------------------------------------------- response
function handleResponse(r) {
  app.last = r;
  const now = performance.now();
  const dt = app.stats.lastTick ? (now - app.stats.lastTick) / 1000 : 0;
  app.stats.lastTick = now;
  app.stats.active += dt;

  drawOverlay(r);
  renderHaptic(r.haptic, r);

  const tag = $("stateTag");
  tag.textContent = STATE_TEXT[r.state] || r.state;
  const card = $("guideCard");
  card.classList.remove("good", "bad");

  if (r.state === "evaluating") {
    const good = !r.guidance;
    app.stats.scores.push(r.score);
    if (app.stats.scores.length > 600) app.stats.scores.shift();
    if (good) app.stats.good += dt;
    const level = good ? "good" : r.score >= 70 ? "warn" : "bad";
    setBanner(level, r.message, `${r.correct_count}/${r.joints.length} 个关节达标`, r.score, 1);
    $("guideMain").textContent = r.message;
    card.classList.add(good ? "good" : "bad");
    if (good && !app.wasGood) speak("很好，保持住");
    if (!good) speak(r.message);
    app.wasGood = good;
  } else {
    app.wasGood = false;
    if (r.state === "holding") {
      setBanner("hold", r.message, "静止后开始评估", null, r.hold_progress);
      $("guideMain").textContent = r.message;
    } else {
      setBanner("warn", r.message || "请站到镜头前", "", null, 0);
      $("guideMain").textContent = r.message || "请站到镜头前";
      speak(r.message || "");
    }
  }
  renderJoints(r.joints, r.guidance ? r.guidance.joint : null);
  renderStats();
  renderPerf();
}

function setBanner(level, title, sub, score, progress) {
  const banner = $("banner");
  banner.className = "banner state-" + level;
  $("bannerTitle").textContent = title;
  $("bannerSub").textContent = sub || "";
  $("scoreValue").textContent = score == null ? "--" : Math.round(score);
  $("ringFg").style.strokeDashoffset = String(119.4 * (1 - Math.max(0, Math.min(1, progress || 0))));
}

// ---------------------------------------------------------------- overlay
function drawOverlay(r) {
  const rect = overlay.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  if (overlay.width !== Math.round(rect.width * dpr) || overlay.height !== Math.round(rect.height * dpr)) {
    overlay.width = Math.round(rect.width * dpr);
    overlay.height = Math.round(rect.height * dpr);
  }
  octx.setTransform(dpr, 0, 0, dpr, 0, 0);
  octx.clearRect(0, 0, rect.width, rect.height);
  const pts = r.landmarks || [];
  if (!pts.length) return;

  // Fit the video box (object-fit: contain).
  const vw = video.videoWidth || 4, vh = video.videoHeight || 3;
  const s = Math.min(rect.width / vw, rect.height / vh);
  const dw = vw * s, dh = vh * s;
  const ox = (rect.width - dw) / 2, oy = (rect.height - dh) / 2;
  const P = (p) => ({ x: ox + (app.mirror ? 1 - p.x : p.x) * dw, y: oy + p.y * dh });

  const status = {};
  (r.joints || []).forEach((j) => { status[JOINT_VERTEX[j.joint]] = j; });
  const focusVertex = r.guidance ? JOINT_VERTEX[r.guidance.joint] : null;
  const missing = new Set(r.missing_landmarks || []);

  octx.lineCap = "round";
  for (const [a, b] of CONNECTIONS) {
    if (!pts[a] || !pts[b] || pts[a].visibility < 0.3 || pts[b].visibility < 0.3) continue;
    const pa = P(pts[a]), pb = P(pts[b]);
    const wrong = (status[a] && !status[a].is_correct) || (status[b] && !status[b].is_correct);
    octx.strokeStyle = wrong ? "rgba(214,69,69,.85)" : "rgba(255,255,255,.85)";
    octx.lineWidth = 4;
    octx.beginPath(); octx.moveTo(pa.x, pa.y); octx.lineTo(pb.x, pb.y); octx.stroke();
  }

  const pulse = 0.5 + 0.5 * Math.sin(performance.now() / 150);
  pts.forEach((p, i) => {
    if (i < 11 && i !== 0) return; // skip face details
    if (p.visibility < 0.3 && !missing.has(i)) return;
    const q = P(p);
    const j = status[i];
    let color = "#ffffff", radius = 4;
    if (missing.has(i)) { color = "#e0a100"; radius = 7; }
    if (j) { color = j.is_correct ? "#1f9d55" : "#d64545"; radius = 7; }
    if (i === focusVertex) {
      octx.beginPath();
      octx.arc(q.x, q.y, 14 + pulse * 6, 0, Math.PI * 2);
      octx.strokeStyle = "rgba(214,69,69,.7)"; octx.lineWidth = 3; octx.stroke();
    }
    octx.beginPath(); octx.arc(q.x, q.y, radius, 0, Math.PI * 2);
    octx.fillStyle = color; octx.fill();
    octx.lineWidth = 2; octx.strokeStyle = "rgba(0,0,0,.35)"; octx.stroke();

    if (j) {
      const label = `${j.label} ${Math.round(j.current)}°`;
      octx.font = "600 13px 'Microsoft YaHei', sans-serif";
      const tw = octx.measureText(label).width;
      const lx = q.x + 10, ly = q.y - 12;
      octx.fillStyle = "rgba(0,0,0,.55)";
      octx.fillRect(lx - 4, ly - 13, tw + 8, 18);
      octx.fillStyle = j.is_correct ? "#bff0d2" : "#ffd0d0";
      octx.fillText(label, lx, ly);
    }
  });
}

// ---------------------------------------------------------------- side panels
function renderJoints(rows, focusJoint) {
  const box = $("joints");
  if (!rows || !rows.length) {
    box.innerHTML = "<p class='muted small'>站到画面中后显示各关节的实时角度。</p>";
    $("correctCount").textContent = "";
    return;
  }
  const byJoint = Object.fromEntries(rows.map((r) => [r.joint, r]));
  const ordered = JOINT_ORDER.filter((j) => byJoint[j]).map((j) => byJoint[j]);
  const pct = (deg) => `${Math.max(0, Math.min(180, deg)) / 180 * 100}%`;
  box.innerHTML = "";
  for (const r of ordered) {
    const el = document.createElement("div");
    el.className = "joint" + (r.is_correct ? "" : " wrong") + (r.joint === focusJoint ? " focus" : "");
    el.title = r.hint ? `${r.label}：${r.hint}` : `${r.label}：在容差内`;
    const lo = r.standard - r.threshold, hi = r.standard + r.threshold;
    el.innerHTML = `
      <span class="jname"></span>
      <div class="jbar">
        <div class="jtol" style="left:${pct(lo)};width:calc(${pct(hi)} - ${pct(lo)})"></div>
        <div class="jstd" style="left:${pct(r.standard)}"></div>
        <div class="jcur" style="left:${pct(r.current)}"></div>
      </div>
      <span class="jval">${Math.round(r.current)}° / ${Math.round(r.standard)}°</span>`;
    el.querySelector(".jname").textContent = r.label;
    box.appendChild(el);
  }
  const ok = rows.filter((r) => r.is_correct).length;
  $("correctCount").textContent = `${ok}/${rows.length} 达标`;
}

function fmtTime(sec) {
  sec = Math.floor(sec);
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

function renderStats() {
  const s = app.stats;
  $("statTime").textContent = fmtTime(s.active);
  $("statGood").textContent = fmtTime(s.good);
  $("statBest").textContent = s.scores.length ? Math.round(Math.max(...s.scores)) : "--";
  $("statAvg").textContent = s.scores.length
    ? Math.round(s.scores.reduce((a, b) => a + b, 0) / s.scores.length) : "--";
  drawSpark(s.scores.slice(-120));
}

function drawSpark(values) {
  const c = $("spark");
  const dpr = window.devicePixelRatio || 1;
  const w = c.clientWidth, h = 70;
  c.width = w * dpr; c.height = h * dpr;
  const ctx = c.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#e2e8e6"; ctx.lineWidth = 1;
  [0, 50, 100].forEach((v) => {
    const y = h - 4 - (v / 100) * (h - 8);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  });
  ctx.fillStyle = "#9aa6a3"; ctx.font = "10px sans-serif";
  ctx.fillText("100", 2, 12); ctx.fillText("得分曲线", w - 50, 12);
  if (values.length < 2) return;
  ctx.strokeStyle = "#0f8a7a"; ctx.lineWidth = 2; ctx.beginPath();
  values.forEach((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - 4 - (v / 100) * (h - 8);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}

function renderPerf() {
  const p = app.perf;
  const now = performance.now();
  if (now - p.since > 1000) {
    p.fps = p.frames * 1000 / (now - p.since);
    p.frames = 0; p.since = now;
  }
  $("perf").textContent = `${p.fps.toFixed(1)} fps · 往返 ${Math.round(p.ms)} ms · 识别 ${Math.round(p.server)} ms`;
}

// ---------------------------------------------------------------- voice
function speak(text) {
  if (!app.voice || !text || !("speechSynthesis" in window)) return;
  const now = performance.now();
  if (text === app.lastSpoken && now - app.lastSpokenAt < VOICE_GAP_MS * 2) return;
  if (now - app.lastSpokenAt < VOICE_GAP_MS) return;
  app.lastSpoken = text;
  app.lastSpokenAt = now;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "zh-CN";
  u.rate = 1.05;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

// ---------------------------------------------------------------- events
$("startBtn").addEventListener("click", async () => {
  if (app.running) { stopCamera(); return; }
  try { await startCamera(); }
  catch (err) { toast(`无法打开摄像头：${err.message}`, 4000); }
});
$("resetBtn").addEventListener("click", async () => {
  try { applyStatus(await api("/api/reset", {})); toast("已重新计时"); } catch (e) { toast(e.message); }
});
$("mirrorChk").addEventListener("change", (e) => {
  app.mirror = e.target.checked;
  video.classList.toggle("mirror", app.mirror);
});
$("voiceChk").addEventListener("change", (e) => {
  app.voice = e.target.checked;
  if (app.voice) { app.lastSpokenAt = 0; speak("语音提示已开启"); }
  else if ("speechSynthesis" in window) speechSynthesis.cancel();
});
$("hapticChk").addEventListener("change", async (e) => {
  try { applyStatus(await api("/api/haptic", { enabled: e.target.checked })); }
  catch (err) { toast(err.message); }
});
$("reconnectBtn").addEventListener("click", async () => {
  try { applyStatus(await api("/api/haptic/reconnect", {})); toast("正在重新搜索腕带…"); }
  catch (err) { toast(err.message); }
});
document.querySelectorAll(".motor").forEach((btn) => {
  btn.addEventListener("click", async () => {
    try { const r = await api("/api/haptic/test", { motor: Number(btn.dataset.motor) }); toast(r.message); }
    catch (err) { toast(err.message); }
  });
});
$("cameraSel").addEventListener("change", async () => {
  if (app.running) { stopCamera(); await startCamera().catch((e) => toast(e.message)); }
});
$("poseButton").addEventListener("click", () => { $("poseModal").hidden = false; });
$("closeModal").addEventListener("click", () => { $("poseModal").hidden = true; });
$("poseModal").addEventListener("click", (e) => { if (e.target.id === "poseModal") e.target.hidden = true; });
$("clearStats").addEventListener("click", () => {
  app.stats = newStats();
  app.stats.lastTick = app.running ? performance.now() : null;
  renderStats();
});
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (e.code === "Space") { e.preventDefault(); $("startBtn").click(); }
  if (e.key === "r" || e.key === "R") $("resetBtn").click();
  if (e.key === "Escape") $("poseModal").hidden = true;
});
window.addEventListener("resize", () => { if (app.last) drawOverlay(app.last); renderStats(); });

// Keep the band status fresh while the camera is off.
setInterval(async () => {
  if (app.running) return;
  try { const s = await api("/api/status"); renderHaptic(s.haptic, null); } catch (_) { /* offline */ }
}, 2000);

// ---------------------------------------------------------------- init
(async function init() {
  video.classList.add("mirror");
  setBanner("idle", "等待开始", "点击「开始」或按空格键", null, 0);
  renderJoints(null);
  renderStats();
  try {
    await loadPoses();
    applyStatus(await api("/api/status"));
  } catch (err) {
    toast(`连接服务器失败：${err.message}`, 5000);
  }
  listCameras();
})();
