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
const cropDir = path.join(buildDir, "crops");
const outputDir = path.join(workspaceDir, "outputs");
const finalPptx = path.join(outputDir, "YogaTutor_网页MVP分块展示_v2.pptx");
const previewPath = path.join(outputDir, "YogaTutor_网页MVP分块展示_v2_preview.png");
const fullScreenshot = path.join(buildDir, "chrome_fullpage.png");

await fs.mkdir(cropDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });
process.env.RUNTIME_NODE_MODULES = runtimeNodeModules;
process.env.RUNTIME_BIN_DIR = runtimeBinDir;

const cropPaths = {};

const crops = [
  ["hero", { left: 60, top: 0, width: 1320, height: 545 }],
  ["studio", { left: 70, top: 600, width: 1290, height: 760 }],
  ["joints", { left: 70, top: 1380, width: 760, height: 430 }],
  ["haptic", { left: 850, top: 1380, width: 510, height: 430 }],
  ["how", { left: 70, top: 1940, width: 1290, height: 375 }],
];

for (const [name, rect] of crops) {
  const file = path.join(cropDir, `${name}.png`);
  await sharp(fullScreenshot).extract(rect).png().toFile(file);
  cropPaths[name] = file;
}

const { resolvePresentationFont, finalizePresentation } = await import(
  pathToFileURL(path.join(skillDir, "container_tools", "artifact_tool_utils.mjs")).href,
);
const fontFamily = resolvePresentationFont({ fontFamily: "Microsoft YaHei" });

const presentation = Presentation.create({
  slideSize: { width: 1280, height: 720 },
});

const slide = presentation.slides.add();
slide.background.fill = "#FFFEFB";

function addText(text, left, top, width, height, style = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    position: { left, top, width, height },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  box.text = text;
  box.text.style = {
    typeface: fontFamily,
    fontSize: style.fontSize ?? 18,
    bold: style.bold ?? false,
    color: style.color ?? "#201515",
    autoFit: "shrinkText",
  };
  return box;
}

function addShape(left, top, width, height, fill, line = "none") {
  return slide.shapes.add({
    geometry: "roundRect",
    position: { left, top, width, height },
    fill,
    line: line === "none" ? { fill: "none", width: 0 } : line,
  });
}

async function addImageBlock(name, label, left, top, width, height) {
  const buffer = await sharp(cropPaths[name]).png().toBuffer();
  addShape(left - 4, top - 4, width + 8, height + 34, "#F8F4F0", { fill: "#E3D8CE", width: 1 });
  addText(label, left, top - 1, width, 24, { fontSize: 15, bold: true, color: "#201515" });
  slide.images.add({
    blob: new Uint8Array(buffer),
    contentType: "image/png",
    alt: label,
    position: { left, top: top + 28, width, height },
    fit: "cover",
    geometry: "roundRect",
    borderRadius: 6,
  });
}

addText("网页 MVP 界面与本地闭环", 40, 28, 660, 46, { fontSize: 34, bold: true });
addText("第四部分重点展示页", 1030, 34, 200, 28, { fontSize: 17, bold: true, color: "#FF4F00" });

addShape(38, 92, 278, 554, "#201515");
addText("当前网页采用 B/S 本地 MVP", 58, 116, 236, 60, { fontSize: 24, bold: true, color: "#FFFEFB" });
addText(
  "Browser 客户端\n采集摄像头画面，按帧发送 JPEG。\n\nPython Server\n在本机运行 MediaPipe，计算关键点、关节角和评分。\n\nESP32 手环\n服务器通过 USB 串口发送震动方向。\n\n现阶段是 localhost HTTP；跨设备部署时建议 HTTPS 或 WSS。",
  58,
  196,
  236,
  350,
  { fontSize: 17, color: "#FFFEFB" },
);
addText("关键结论：当前传输的是摄像头帧，不是浏览器端已计算好的肢体点阵。", 58, 570, 232, 52, {
  fontSize: 15,
  bold: true,
  color: "#FFB38A",
});

await addImageBlock("hero", "入口与主题", 348, 94, 372, 128);
await addImageBlock("studio", "实时练习工作台", 740, 94, 492, 292);
await addImageBlock("joints", "关节偏差列表", 348, 266, 372, 160);
await addImageBlock("haptic", "左手环引导", 348, 474, 372, 126);
await addImageBlock("how", "四步工作原理", 740, 438, 492, 162);

addText("截图来源：项目 web/index.html，按页面模块分块截取。", 40, 666, 760, 22, { fontSize: 13, color: "#605D52" });

slide.speakerNotes.textFrame.setText(
  "本页用于第四部分网页 MVP 汇报。当前网页为 B/S 本地 MVP：浏览器端负责摄像头采集和界面展示，本机 Python 服务通过 /api/frame 接收 JPEG 帧并运行 MediaPipe、静止检测、Warrior II 角度评分和触觉指令生成，再通过 USB Serial 控制 ESP32 左手环。当前演示采用 localhost HTTP；若后续让手机或其他电脑作为客户端访问，应使用 HTTPS 或 WSS 传输摄像头帧或人体关键点数据。",
);

const stagingDir = path.join(workspaceDir, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
const candidatePath = path.join(stagingDir, "web-overview-candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const result = await finalizePresentation({
  explicitTotalSlideCount: 1,
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
  fontPolicy: {
    basis: "design",
    families: [fontFamily],
  },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "YogaTutor_网页MVP分块展示.validation.json"),
});

const preview = await presentation.export({ slide, format: "png", scale: 1 });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

console.log(JSON.stringify({ finalPptx: result.finalPath ?? finalPptx, previewPath }, null, 2));
