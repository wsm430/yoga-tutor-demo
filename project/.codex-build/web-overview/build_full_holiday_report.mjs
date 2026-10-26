import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import sharp from "sharp";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "D:/Projects/Yoga Tutor";
const skillDir = "C:/Users/siemin/.codex/plugins/cache/openai-primary-runtime/presentations/26.903.11726/skills/presentations";
const runtimePython = "C:/Users/siemin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const runtimeNodeModules = "C:/Users/siemin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const runtimeBinDir = "C:/Users/siemin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override";
const buildDir = path.join(workspaceDir, ".codex-build", "web-overview");
const assetDir = path.join(buildDir, "full-report-assets");
const outputDir = path.join(workspaceDir, "outputs");
const finalPptx = path.join(outputDir, "YogaTutor_暑假进展汇报_完整_v6.pptx");
const montagePath = path.join(outputDir, "YogaTutor_暑假进展汇报_完整_v6预览.webp");
const fullScreenshot = path.join(buildDir, "chrome_fullpage.png");

process.env.RUNTIME_NODE_MODULES = runtimeNodeModules;
process.env.RUNTIME_BIN_DIR = runtimeBinDir;
await fs.mkdir(assetDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });

const { resolvePresentationFont, finalizePresentation } = await import(
  pathToFileURL(path.join(skillDir, "container_tools", "artifact_tool_utils.mjs")).href,
);
const fontFamily = resolvePresentationFont({ fontFamily: "Microsoft YaHei" });

const W = 1280;
const H = 720;
const C = {
  bg: "#FFFEFB",
  soft: "#F8F4F0",
  ink: "#201515",
  body: "#605D52",
  line: "#E5DCD4",
  accent: "#FF4F00",
  accentSoft: "#FFE4D6",
  dark: "#1F1112",
  ok: "#27A35C",
  warn: "#C75327",
};

async function readImage(file) {
  return new Uint8Array(await fs.readFile(file));
}

async function cropFromPage(name, rect) {
  const file = path.join(assetDir, `${name}.png`);
  await sharp(fullScreenshot).extract(rect).png().toFile(file);
  return file;
}

async function makePoseGrid() {
  const files = [
    "Warrior II Pose.jpg",
    "Warrior I Pose.jpg",
    "Tree Pose.jpg",
    "Triangle Pose.jpg",
    "Plank Pose.jpg",
    "Downward-Facing Dog Pose.jpg",
    "Wheel Pose.jpg",
    "Seated Meditation Pose.jpg",
    "Upward-Facing Dog Pose.jpg",
  ];
  const cellW = 260;
  const cellH = 170;
  const gap = 16;
  const canvasW = cellW * 3 + gap * 2;
  const canvasH = cellH * 3 + gap * 2;
  const composites = [];
  for (let i = 0; i < files.length; i++) {
    const src = path.join(workspaceDir, "src", "standard_images", files[i]);
    const image = await sharp(src).resize(cellW, cellH, { fit: "cover", position: "center" }).png().toBuffer();
    composites.push({ input: image, left: (i % 3) * (cellW + gap), top: Math.floor(i / 3) * (cellH + gap) });
  }
  const out = path.join(assetDir, "pose-grid.png");
  await sharp({ create: { width: canvasW, height: canvasH, channels: 4, background: "#F8F4F0" } })
    .composite(composites)
    .png()
    .toFile(out);
  return out;
}

async function makeWarriorAngles() {
  const src = path.join(workspaceDir, "src", "standard_images", "Warrior II Pose.jpg");
  const out = path.join(assetDir, "warrior-ii-cover.png");
  await sharp(src).resize(780, 500, { fit: "cover", position: "center" }).png().toFile(out);
  return out;
}

const webCrops = {
  hero: await cropFromPage("hero", { left: 60, top: 0, width: 1320, height: 545 }),
  studio: await cropFromPage("studio", { left: 70, top: 600, width: 1290, height: 760 }),
  joints: await cropFromPage("joints", { left: 70, top: 1380, width: 760, height: 430 }),
  haptic: await cropFromPage("haptic", { left: 850, top: 1380, width: 510, height: 430 }),
  how: await cropFromPage("how", { left: 70, top: 1940, width: 1290, height: 375 }),
};
const poseGrid = await makePoseGrid();
const warriorImage = await makeWarriorAngles();

const presentation = Presentation.create({ slideSize: { width: W, height: H } });

function slideBase(title, kicker = "") {
  const slide = presentation.slides.add();
  slide.background.fill = C.bg;
  if (kicker) addText(slide, kicker, 56, 32, 420, 24, { size: 14, bold: true, color: C.accent, tracking: 1 });
  addText(slide, title, 56, 60, 820, 54, { size: 32, bold: true });
  addText(slide, "YogaTutor 暑假进展汇报", 982, 42, 230, 22, { size: 13, color: C.body, align: "right" });
  line(slide, 56, 124, 1168, 1, C.line);
  return slide;
}

function addText(slide, text, left, top, width, height, opt = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    position: { left, top, width, height },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  box.text = text;
  box.text.style = {
    typeface: fontFamily,
    fontSize: Math.max(14, opt.size ?? 24),
    bold: opt.bold ?? false,
    color: opt.color ?? C.ink,
    autoFit: opt.autoFit ?? "none",
    alignment: opt.align ?? "left",
  };
  return box;
}

function rect(slide, left, top, width, height, fill, radius = true, stroke = C.line) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    position: { left, top, width, height },
    fill,
    line: { fill: stroke, width: stroke === "none" ? 0 : 1 },
  });
}

function line(slide, left, top, width, height, color) {
  return slide.shapes.add({
    geometry: "rect",
    position: { left, top, width, height },
    fill: color,
    line: { fill: "none", width: 0 },
  });
}

async function image(slide, file, left, top, width, height, alt, fit = "cover") {
  slide.images.add({
    blob: await readImage(file),
    contentType: "image/png",
    alt,
    position: { left, top, width, height },
    fit,
    geometry: "roundRect",
    borderRadius: 8,
  });
}

function bulletList(slide, items, left, top, width, rowH, opt = {}) {
  items.forEach((item, i) => {
    const y = top + i * rowH;
    rect(slide, left, y + 7, 8, 8, opt.dot ?? C.accent, true, "none");
    addText(slide, item, left + 28, y, width - 28, rowH - 2, { size: opt.size ?? 24, color: opt.color ?? C.ink });
  });
}

function metric(slide, value, label, left, top, width, color = C.accent) {
  rect(slide, left, top, width, 124, C.soft, true);
  addText(slide, value, left + 20, top + 18, width - 40, 44, { size: 38, bold: true, color });
  addText(slide, label, left + 20, top + 72, width - 40, 38, { size: 18, color: C.body });
}

function flowItem(slide, n, title, body, left, top, width) {
  addText(slide, String(n).padStart(2, "0"), left, top, 44, 24, { size: 15, bold: true, color: C.accent });
  line(slide, left, top + 32, width, 2, C.ink);
  addText(slide, title, left, top + 52, width, 30, { size: 24, bold: true });
  addText(slide, body, left, top + 92, width, 94, { size: 22, color: C.body });
}

function processBox(slide, title, body, left, top, width, height, dark = false) {
  rect(slide, left, top, width, height, dark ? C.dark : C.soft, true, dark ? "none" : C.line);
  addText(slide, title, left + 22, top + 22, width - 44, 34, {
    size: 26,
    bold: true,
    color: dark ? C.bg : C.ink,
  });
  addText(slide, body, left + 22, top + 70, width - 44, height - 88, {
    size: 22,
    color: dark ? "#E8D9D1" : C.body,
  });
}

function connector(slide, x1, y, x2) {
  line(slide, x1, y, x2 - x1, 3, C.accent);
  slide.shapes.add({
    geometry: "triangle",
    position: { left: x2 - 10, top: y - 7, width: 14, height: 16 },
    fill: C.accent,
    line: { fill: "none", width: 0 },
  });
}

// 1 Cover
{
  const slide = presentation.slides.add();
  slide.background.fill = C.bg;
  await image(slide, warriorImage, 638, 78, 572, 500, "Warrior II 标准姿势");
  rect(slide, 638, 78, 572, 500, "none", true, "#00000000");
  addText(slide, "视觉感知 × 单腕触觉引导", 72, 104, 460, 30, { size: 18, bold: true, color: C.accent });
  addText(slide, "YogaTutor\n暑假进展汇报", 72, 156, 510, 150, { size: 50, bold: true });
  addText(slide, "基于视觉感知和多方向触觉引导的实时动作矫正系统", 76, 344, 470, 68, { size: 22, color: C.body });
  line(slide, 76, 444, 160, 5, C.accent);
  addText(slide, "2026 年 7-8 月阶段成果", 76, 468, 300, 28, { size: 18, color: C.body });
  slide.speakerNotes.textFrame.setText("封面。标准姿势图来自 src/standard_images/Warrior II Pose.jpg。");
}

// 2 Background
{
  const slide = slideBase("项目目标：让用户看见偏差，感受调整方向", "01 背景与目标");
  processBox(slide, "练习痛点", "视频教学无法实时指出角度偏差，用户低头看屏幕也会破坏动作保持。", 72, 170, 312, 220, false);
  processBox(slide, "视觉判断", "摄像头识别人体关键点，系统把动作转成可比较的关节角。", 446, 170, 312, 220, true);
  processBox(slide, "触觉引导", "手环不只提醒错误，而是把纠正方向传到身体上。", 820, 170, 312, 220, false);
  connector(slide, 386, 280, 446);
  connector(slide, 760, 280, 820);
  rect(slide, 158, 462, 860, 86, C.accentSoft, true, "#FFD1BB");
  addText(slide, "项目目标", 188, 484, 130, 34, { size: 26, bold: true, color: C.accent });
  addText(slide, "让用户在练习过程中完成“识别偏差、理解方向、即时调整”的闭环。", 338, 482, 620, 38, { size: 28, bold: true });
  slide.speakerNotes.textFrame.setText("项目目标根据 docs/README.md 和网页文案整理。");
}

// 3 Timeline
{
  const slide = slideBase("暑假工作总览：从主程序到可演示网页 MVP", "02 暑假进展");
  const xs = [70, 300, 530, 760, 990];
  const titles = ["7月中旬", "7月中旬", "8月23日", "8月23日", "下一步"];
  const bodies = [
    "统一主程序\n自动识别与手动评估共存",
    "ESP32 固件\n串口协议与左手环控制",
    "Web MVP\nWarrior II 实时练习界面",
    "闭环强化\n串口保活、测试、BLE 方案",
    "产品化扩展\nBLE、双手环、多动作选择",
  ];
  line(slide, 98, 284, 1010, 4, C.accent);
  xs.forEach((x, i) => {
    rect(slide, x, 190, 188, 250, i === 4 ? C.dark : C.soft, true, i === 4 ? "none" : C.line);
    addText(slide, titles[i], x + 20, 218, 140, 32, { size: 24, bold: true, color: i === 4 ? C.bg : C.accent });
    addText(slide, bodies[i], x + 20, 284, 140, 120, { size: 20, color: i === 4 ? C.bg : C.ink });
    if (i < xs.length - 1) connector(slide, x + 188, 315, xs[i + 1]);
  });
  addText(slide, "4-6 月标准姿势库和申报材料作为基础；暑假重点是把系统收束成可演示闭环。", 76, 524, 1030, 44, { size: 26, color: C.body });
  slide.speakerNotes.textFrame.setText("时间线基于项目文件修改时间和 docs/README.md、docs/hardware.md、web/README.md、docs/BLE_MIGRATION.md。");
}

// 4 Architecture
{
  const slide = slideBase("系统架构：视觉、评分和触觉反馈形成闭环", "03 核心系统");
  const items = [
    ["摄像头帧", "浏览器或 OpenCV 采集"],
    ["姿态检测", "MediaPipe 提取 33 个关键点"],
    ["稳定处理", "滤波与静止检测"],
    ["角度评分", "8 个关节角比较"],
    ["触觉映射", "偏差转成马达方向"],
    ["ESP32 手环", "USB 串口驱动左手环"],
  ];
  items.forEach(([t, b], i) => {
    const x = 72 + i * 184;
    processBox(slide, t, b, x, 190, 156, 220, i >= 4);
    if (i < items.length - 1) connector(slide, x + 156, 300, x + 184);
  });
  rect(slide, 92, 500, 1000, 72, C.accentSoft, true, "#FFD1BB");
  addText(slide, "算法汇报边界", 122, 518, 180, 34, { size: 26, bold: true, color: C.accent });
  addText(slide, "只讲输入、处理节点和输出，把主要时间留给网页 MVP 和硬件闭环。", 322, 516, 700, 38, { size: 26, bold: true });
  slide.speakerNotes.textFrame.setText("架构依据 docs/architecture.md。");
}

// 5 Vision
{
  const slide = slideBase("姿态感知：从 33 个关键点提取 8 个关节角", "03 核心系统");
  await image(slide, webCrops.hero, 704, 168, 420, 210, "网页入口截图");
  metric(slide, "33", "MediaPipe 人体关键点", 74, 180, 246);
  metric(slide, "8", "肩、肘、髋、膝关节角", 352, 180, 246);
  metric(slide, "1.2s", "静止后触发评估", 74, 346, 246);
  metric(slide, "0.5", "检测与跟踪置信度", 352, 346, 246);
  processBox(slide, "输入输出", "输入是摄像头画面，输出是可比较的关节角。滤波和静止检测用于减少误判。", 704, 420, 420, 120, false);
  slide.speakerNotes.textFrame.setText("参数来自 src/config.py 和 docs/architecture.md。");
}

// 6 Pose library
{
  const slide = slideBase("标准姿势库：前期基础支撑假期 MVP 演示", "03 核心系统");
  await image(slide, poseGrid, 72, 164, 600, 392, "标准姿势缩略图");
  addText(slide, "项目已有 18 个标准姿势 JSON", 726, 176, 430, 42, { size: 30, bold: true });
  bulletList(slide, [
    "每个标准姿势保存 landmarks 和 average angles",
    "网页 MVP 当前固定使用 Warrior II Pose",
    "后续网页端可扩展为多姿势选择",
  ], 728, 252, 430, 66, { size: 24 });
  addText(slide, "4-6 月成果在这里作为基础，不抢占暑假工作篇幅。", 728, 506, 410, 54, { size: 24, color: C.body });
  slide.speakerNotes.textFrame.setText("标准姿势列表来自 src/standard_poses 和 src/standard_images。");
}

// 7 Web B/S
{
  const slide = slideBase("网页 MVP：采用 B/S 本地架构", "04 网页与闭环");
  processBox(slide, "Browser 客户端", "摄像头采集\n页面展示\n交互按钮", 72, 170, 278, 250, true);
  processBox(slide, "HTTP 本地接口", "POST /api/frame\nGET /api/status\nPOST /api/reset", 410, 170, 278, 250, false);
  processBox(slide, "Python Server", "MediaPipe\n静止检测\n角度评分\n触觉指令", 748, 170, 278, 250, false);
  rect(slide, 402, 464, 296, 152, C.dark, true, "none");
  addText(slide, "ESP32 手环", 434, 494, 230, 34, { size: 28, bold: true, color: C.bg });
  addText(slide, "USB 串口\n方向强度驱动马达", 434, 542, 220, 64, { size: 24, color: "#E8D9D1" });
  connector(slide, 350, 294, 410);
  connector(slide, 688, 294, 748);
  line(slide, 887, 420, 3, 54, C.accent);
  line(slide, 550, 474, 337, 3, C.accent);
  rect(slide, 72, 474, 278, 130, C.accentSoft, true, "#FFD1BB");
  addText(slide, "当前传输内容", 96, 498, 210, 34, { size: 26, bold: true, color: C.accent });
  addText(slide, "JPEG 摄像头帧\n不是肢体点阵", 96, 540, 210, 58, { size: 24, bold: true });
  rect(slide, 748, 474, 278, 130, C.soft, true);
  addText(slide, "后续跨设备", 772, 498, 210, 34, { size: 26, bold: true, color: C.accent });
  addText(slide, "跨设备访问时\n建议 HTTPS 或 WSS", 772, 540, 210, 58, { size: 24, bold: true });
  slide.speakerNotes.textFrame.setText("网页架构来自 web/app.js、src/web_mvp_server.py 和 web/README.md。当前是 localhost HTTP；跨设备部署建议 HTTPS/WSS。");
}

// 8 Data flow
{
  const slide = slideBase("本机服务器负责计算，浏览器负责采集和展示", "04 网页与闭环");
  flowItem(slide, 1, "采集", "浏览器调用摄像头，生成 JPEG 帧。", 74, 178, 235);
  flowItem(slide, 2, "传输", "POST 到本机 /api/frame。", 338, 178, 235);
  flowItem(slide, 3, "计算", "Python 服务计算关键点、关节角和评分。", 602, 178, 235);
  flowItem(slide, 4, "反馈", "页面更新结果，服务器发送手环指令。", 866, 178, 260);
  connector(slide, 274, 252, 338);
  connector(slide, 538, 252, 602);
  connector(slide, 802, 252, 866);
  rect(slide, 112, 442, 458, 160, C.soft, true);
  addText(slide, "为什么先做本地服务器", 142, 468, 360, 34, { size: 26, bold: true, color: C.accent });
  addText(slide, "延迟低，摄像头画面不离开电脑，USB 手环控制也更直接。", 142, 520, 370, 58, { size: 24, color: C.ink });
  rect(slide, 640, 442, 458, 160, C.dark, true, "none");
  addText(slide, "后续网络化改造", 670, 468, 360, 34, { size: 26, bold: true, color: C.bg });
  addText(slide, "跨设备接入时，用 HTTPS/WSS 保护摄像头帧或关键点数据。", 670, 520, 370, 58, { size: 24, color: "#E8D9D1" });
  slide.speakerNotes.textFrame.setText("当前接口来自 src/web_mvp_server.py：/api/status、/api/frame、/api/reset。");
}

// 9 Web overview screenshot
{
  const slide = slideBase("网页界面：一页完成练习、评分和手环状态展示", "04 网页与闭环");
  await image(slide, webCrops.studio, 56, 148, 640, 378, "实时练习工作台截图", "contain");
  await image(slide, webCrops.joints, 728, 148, 430, 196, "关节偏差截图", "contain");
  await image(slide, webCrops.haptic, 728, 382, 430, 196, "左手环引导截图", "contain");
  rect(slide, 74, 560, 1050, 54, C.accentSoft, true, "#FFD1BB");
  addText(slide, "页面模块", 98, 574, 130, 28, { size: 24, bold: true, color: C.accent });
  addText(slide, "摄像头画面、目标姿势、评分条、关节列表、USB 状态和左手环方向在同一工作台中展示。", 246, 572, 820, 30, { size: 24, color: C.ink });
  slide.speakerNotes.textFrame.setText("截图由 web/index.html 分块截取。静态截图显示未开启摄像头状态，实际演示需使用 web/start-local.ps1 启动 Python 识别服务。");
}

// 10 Haptic
{
  const slide = slideBase("触觉反馈：把最大角度偏差转成一个震动方向", "04 网页与闭环");
  await image(slide, webCrops.haptic, 708, 166, 430, 326, "左手环引导截图");
  bulletList(slide, [
    "当前 MVP 使用已验证的左手环",
    "每次只发送优先级最高的一个纠正方向",
    "方向映射：上 M2、下 M0、左 M1、右 M3",
    "强度随偏差比例提升：150、200、255",
  ], 84, 178, 540, 68, { size: 26 });
  rect(slide, 86, 486, 520, 112, C.soft, true);
  addText(slide, "反馈流程", 116, 512, 130, 34, { size: 26, bold: true, color: C.accent });
  addText(slide, "偏差排序  选最大偏差  映射方向  发送指令", 260, 510, 300, 58, { size: 24, bold: true });
  slide.speakerNotes.textFrame.setText("触觉反馈映射来自 src/haptic_feedback.py 和 tests/test_mvp_logic.py。");
}

// 11 Hardware protocol
{
  const slide = slideBase("硬件通信：USB 串口闭环和停震保护", "04 网页与闭环");
  rect(slide, 78, 156, 1030, 110, C.dark, true, "none");
  addText(slide, "L:2,150 R:N", 116, 184, 280, 44, { size: 38, bold: true, color: C.accent });
  addText(slide, "左手环 M2 以 150 强度震动，右手环无动作。", 430, 190, 560, 40, { size: 26, color: C.bg });
  metric(slide, "115200", "串口波特率", 82, 330, 230);
  metric(slide, "0.75s", "电脑端保活间隔", 348, 330, 230);
  metric(slide, "2s", "固件无命令自动停震", 614, 330, 230);
  metric(slide, "COM9", "默认手环串口，可覆盖", 880, 330, 230);
  rect(slide, 82, 500, 476, 126, C.soft, true);
  addText(slide, "通信流程", 112, 528, 130, 34, { size: 26, bold: true, color: C.accent });
  addText(slide, "生成命令，解析后控制 GPIO 和马达。", 258, 526, 250, 60, { size: 24, color: C.ink });
  rect(slide, 620, 500, 476, 126, C.dark, true, "none");
  addText(slide, "边界说明", 650, 528, 130, 34, { size: 26, bold: true, color: C.bg });
  addText(slide, "BLE 已有方案，当前不要说成已完成。", 796, 526, 250, 60, { size: 24, color: "#E8D9D1" });
  slide.speakerNotes.textFrame.setText("串口协议来自 docs/hardware.md、src/esp32_controller.py、firmware/yoga_bands/yoga_bands.ino、docs/BLE_MIGRATION.md。");
}

// 12 Summary
{
  const slide = slideBase("总结与下一步：从可演示 MVP 走向无线化和多动作", "05 总结与计划");
  addText(slide, "暑假完成的核心成果", 82, 168, 400, 36, { size: 28, bold: true });
  bulletList(slide, [
    "形成 Warrior II 网页练习工作台",
    "跑通本机视觉计算到左手环震动的闭环",
    "明确 USB MVP、BLE 待迁移和双手环待扩展的边界",
  ], 84, 228, 520, 58, { size: 21 });
  addText(slide, "后续计划", 720, 168, 260, 36, { size: 28, bold: true });
  bulletList(slide, [
    "BLE GATT 替代 USB 串口",
    "扩展双手环 GPIO 和固件协议",
    "网页端支持多姿势选择",
    "补充真实用户测试和长期稳定性验证",
  ], 722, 228, 430, 54, { size: 21 });
  rect(slide, 84, 558, 996, 60, C.accentSoft, true, "#FFD1BB");
  addText(slide, "一句话收束：暑假阶段把 YogaTutor 从算法模块推进到边界清晰、可演示的本地 MVP。", 112, 574, 900, 28, { size: 21, bold: true, color: C.ink });
  slide.speakerNotes.textFrame.setText("总结结合 docs/README.md、web/README.md 和 BLE_MIGRATION.md。");
}

const stagingDir = path.join(workspaceDir, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
const candidatePath = path.join(stagingDir, "holiday-report-candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const result = await finalizePresentation({
  explicitTotalSlideCount: 12,
  workspaceDir,
  candidatePath,
  finalPath: finalPptx,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu",
    "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  fontPolicy: { basis: "design", families: [fontFamily] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "YogaTutor_暑假进展汇报_完整_v6.validation.json"),
});

const montage = await presentation.export({ format: "webp", montage: true, scale: 0.55 });
await fs.writeFile(montagePath, new Uint8Array(await montage.arrayBuffer()));

console.log(JSON.stringify({ finalPptx: result.finalPath ?? finalPptx, montagePath }, null, 2));
