const video = document.querySelector('#camera');
const overlay = document.querySelector('#pose-overlay');
const overlayContext = overlay.getContext('2d');
const capture = document.createElement('canvas');
const captureContext = capture.getContext('2d');
const empty = document.querySelector('#camera-empty');
const scan = document.querySelector('#scan');
const hold = document.querySelector('#hold');
const holdValue = document.querySelector('#hold-value');
const poseTag = document.querySelector('#pose-tag');
const cameraButton = document.querySelector('#camera-button');
const resetButton = document.querySelector('#reset-button');
const error = document.querySelector('#error');
const connection = document.querySelector('#connection');
const bandLabel = document.querySelector('#band-label');
const hapticCopy = document.querySelector('#haptic-copy');

const POSE_CONNECTIONS = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24], [23, 25], [25, 27],
  [24, 26], [26, 28], [27, 31], [28, 32],
];
const DIRECTION_LABELS = {up: '向上', down: '向下', left: '向左', right: '向右'};
const FALLBACK_STANDARDS = {
  left_elbow: 174.3, right_elbow: 178.7, left_knee: 176.8, right_knee: 100.1,
  left_shoulder: 96.3, right_shoulder: 99.1, left_hip: 117.5, right_hip: 91.6,
};
const JOINT_LABELS = {
  left_elbow: '左肘', right_elbow: '右肘', left_knee: '左膝', right_knee: '右膝',
  left_shoulder: '左肩', right_shoulder: '右肩', left_hip: '左髋', right_hip: '右髋',
};

let stream = null;
let frameTimer = null;
let frameInFlight = false;
let standardAngles = FALLBACK_STANDARDS;

function renderJoints(rows = null) {
  const data = rows || Object.entries(standardAngles).map(([joint, standard]) => ({
    joint, label: JOINT_LABELS[joint], standard, is_correct: null,
  }));
  document.querySelector('#joints').innerHTML = data.map((item) => {
    const stateClass = item.is_correct === null ? '' : item.is_correct ? 'ok' : 'warn';
    const mark = item.is_correct === null ? '·' : item.is_correct ? '✓' : '!';
    const current = item.current === undefined ? '—' : `${item.current.toFixed(1)}°`;
    const delta = item.difference === undefined ? '—' : `${item.difference > 0 ? '+' : ''}${item.difference.toFixed(1)}°`;
    return `<div class="joint-row"><span class="status ${stateClass}">${mark}</span><strong>${item.label}</strong><span class="angle">${current}</span><span class="target">标准 ${Number(item.standard).toFixed(1)}°</span><span class="delta ${item.is_correct ? 'ok-text' : ''}">${delta}</span></div>`;
  }).join('');
}

function setConnection(connected, transport = 'serial') {
  connection.classList.toggle('offline', !connected);
  connection.innerHTML = `<i></i> ${connected ? 'USB 已连接' : transport === 'none' ? '无硬件模式' : 'USB 未连接'}`;
}

function clearHaptic(message = '等待静止评估') {
  document.querySelectorAll('.motor.active').forEach((motor) => motor.classList.remove('active'));
  bandLabel.innerHTML = '等待<br>评估';
  hapticCopy.textContent = message;
}

function renderHaptic(guidance) {
  document.querySelectorAll('.motor.active').forEach((motor) => motor.classList.remove('active'));
  if (!guidance) {
    bandLabel.innerHTML = '姿势<br>达标';
    hapticCopy.textContent = '八个关节均在当前角度容差内，不发送震动。';
    return;
  }
  document.querySelector(`.motor[data-direction="${guidance.direction}"]`)?.classList.add('active');
  bandLabel.innerHTML = `${guidance.joint_label}<br>${DIRECTION_LABELS[guidance.direction]}`;
  hapticCopy.textContent = `${guidance.joint_label}${guidance.correction}；左手环 ${DIRECTION_LABELS[guidance.direction]}侧震动，强度 ${guidance.intensity}/255。`;
}

function drawLandmarks(points = []) {
  overlayContext.clearRect(0, 0, overlay.width, overlay.height);
  if (!points.length) return;
  overlayContext.lineWidth = Math.max(2, overlay.width / 320);
  overlayContext.strokeStyle = '#ff4f00';
  for (const [start, end] of POSE_CONNECTIONS) {
    const a = points[start];
    const b = points[end];
    if (!a || !b || a.visibility < 0.35 || b.visibility < 0.35) continue;
    overlayContext.beginPath();
    overlayContext.moveTo(a.x * overlay.width, a.y * overlay.height);
    overlayContext.lineTo(b.x * overlay.width, b.y * overlay.height);
    overlayContext.stroke();
  }
  overlayContext.fillStyle = '#fffefb';
  for (const point of points) {
    if (point.visibility < 0.35) continue;
    overlayContext.beginPath();
    overlayContext.arc(point.x * overlay.width, point.y * overlay.height, Math.max(3, overlay.width / 210), 0, Math.PI * 2);
    overlayContext.fill();
  }
}

function renderResponse(data) {
  drawLandmarks(data.landmarks);
  setConnection(data.haptic_connected, data.transport || 'serial');
  hold.hidden = data.state !== 'holding';
  holdValue.textContent = `${Math.round((data.hold_progress || 0) * 100)}%`;
  poseTag.hidden = data.state !== 'evaluating';

  if (data.state === 'no_pose') {
    document.querySelector('#score-state').textContent = '未检测到完整人体';
    document.querySelector('#score-copy').textContent = data.message || '请后退一些，确保全身进入画面。';
    clearHaptic('未检测到完整人体，不发送震动。');
    return;
  }
  if (data.state === 'holding') {
    document.querySelector('#score-state').textContent = '静止检测中';
    document.querySelector('#score-copy').textContent = data.message;
    clearHaptic('保持不动，达到静止条件后才发送震动。');
    return;
  }
  if (data.state === 'evaluating') {
    const score = Math.round(data.score);
    document.querySelector('#score').innerHTML = `${score}<sup>/100</sup>`;
    document.querySelector('#score-state').textContent = '实时评估';
    document.querySelector('#score-bar').style.width = `${score}%`;
    document.querySelector('#score-copy').textContent = data.message;
    document.querySelector('#joint-summary').textContent = `容差内 ${data.correct_count} / ${data.joints.length}`;
    renderJoints(data.joints);
    renderHaptic(data.guidance);
  }
}

async function jpegBlob() {
  return new Promise((resolve) => capture.toBlob(resolve, 'image/jpeg', 0.76));
}

async function processFrame() {
  if (!stream || frameInFlight || video.readyState < 2) return;
  frameInFlight = true;
  try {
    const sourceWidth = video.videoWidth;
    const sourceHeight = video.videoHeight;
    const scale = Math.min(1, 720 / sourceWidth);
    capture.width = Math.round(sourceWidth * scale);
    capture.height = Math.round(sourceHeight * scale);
    if (overlay.width !== capture.width || overlay.height !== capture.height) {
      overlay.width = capture.width;
      overlay.height = capture.height;
    }
    captureContext.drawImage(video, 0, 0, capture.width, capture.height);
    const blob = await jpegBlob();
    const response = await fetch('/api/frame', {method: 'POST', headers: {'Content-Type': 'image/jpeg'}, body: blob});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `识别服务返回 ${response.status}`);
    error.textContent = '';
    renderResponse(data);
  } catch (exception) {
    error.textContent = `${exception.message}。请确认 Python 识别服务仍在运行。`;
  } finally {
    frameInFlight = false;
  }
}

async function resetEvaluation() {
  try {
    const response = await fetch('/api/reset', {method: 'POST'});
    const data = await response.json();
    setConnection(data.haptic_connected, data.transport);
  } catch (exception) {
    error.textContent = `无法重置：${exception.message}`;
  }
  document.querySelector('#score').textContent = '—';
  document.querySelector('#score-state').textContent = stream ? '等待静止' : '等待摄像头';
  document.querySelector('#score-bar').style.width = '0%';
  document.querySelector('#score-copy').textContent = '全身进入画面并保持 Warrior II 姿势。';
  document.querySelector('#joint-summary').textContent = '等待评估';
  renderJoints();
  clearHaptic();
  poseTag.hidden = true;
  hold.hidden = true;
}

async function stopCamera() {
  clearInterval(frameTimer);
  frameTimer = null;
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  video.srcObject = null;
  empty.hidden = false;
  scan.hidden = true;
  overlayContext.clearRect(0, 0, overlay.width, overlay.height);
  cameraButton.textContent = '开启摄像头';
  cameraButton.className = 'button primary';
  document.querySelector('#camera-dot').classList.remove('live');
  document.querySelector('#camera-size').textContent = '等待摄像头';
  await resetEvaluation();
}

cameraButton.addEventListener('click', async () => {
  if (stream) {
    await stopCamera();
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {facingMode: 'user', width: {ideal: 1280}, height: {ideal: 720}},
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    empty.hidden = true;
    scan.hidden = false;
    cameraButton.textContent = '关闭摄像头';
    cameraButton.className = 'button outline';
    document.querySelector('#camera-dot').classList.add('live');
    document.querySelector('#camera-size').textContent = `${video.videoWidth} × ${video.videoHeight}`;
    document.querySelector('#score-state').textContent = '寻找人体';
    error.textContent = '';
    frameTimer = setInterval(processFrame, 180);
  } catch (exception) {
    stream = null;
    error.textContent = `无法访问摄像头：${exception.message}。请允许浏览器摄像头权限。`;
  }
});

resetButton.addEventListener('click', resetEvaluation);
window.addEventListener('beforeunload', () => navigator.sendBeacon('/api/reset'));

renderJoints();
fetch('/api/status').then((response) => response.json()).then((data) => {
  standardAngles = data.standard_angles || FALLBACK_STANDARDS;
  renderJoints();
  setConnection(data.haptic_connected, data.transport);
}).catch(() => {
  error.textContent = '未连接 Python 识别服务，请通过 web/start-local.ps1 启动。';
  setConnection(false);
});
