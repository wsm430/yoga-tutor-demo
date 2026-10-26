import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const deck = "D:/Projects/Yoga Tutor/outputs/YogaTutor_暑假进展汇报_完整_v6.pptx";
const outDir = "D:/Projects/Yoga Tutor/outputs/holiday_report_slide_previews_v6";
await fs.mkdir(outDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(deck));

for (const i of [7, 8, 9, 10, 11]) {
  const slide = presentation.slides.getItem(i - 1);
  const blob = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(outDir, `slide_${i}.png`), new Uint8Array(await blob.arrayBuffer()));
}
