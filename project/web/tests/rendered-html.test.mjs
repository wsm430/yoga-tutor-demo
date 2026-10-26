import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("MVP exposes the real Warrior II camera workflow", async () => {
  const [html, script] = await Promise.all([
    readFile(new URL("index.html", root), "utf8"),
    readFile(new URL("app.js", root), "utf8"),
  ]);

  assert.match(html, /Warrior II · 手动目标/);
  assert.match(html, /id="pose-overlay"/);
  assert.match(html, /左手环引导/);
  assert.doesNotMatch(html, /自动识别|运行演示评估|右手腕/);
  assert.match(script, /navigator\.mediaDevices\.getUserMedia/);
  assert.match(script, /fetch\('\/api\/frame'/);
  assert.match(script, /fetch\('\/api\/status'/);
  assert.doesNotMatch(script, /jointData|82<sup>/);
});

test("physical motor directions stay visible and stable", async () => {
  const html = await readFile(new URL("index.html", root), "utf8");
  assert.match(html, /上 M2、下 M0、左 M1、右 M3/);
  for (const direction of ["up", "down", "left", "right"]) {
    assert.match(html, new RegExp(`data-direction="${direction}"`));
  }
});
