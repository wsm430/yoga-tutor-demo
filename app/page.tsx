"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const poses = [
  "Warrior II Pose",
  "Tree Pose",
  "Triangle Pose",
  "Downward-Facing Dog Pose",
  "Plank Pose",
  "Upward-Facing Dog Pose",
  "Wheel Pose",
  "Bow Pose1",
];

const joints = [
  ["左肩", 92, 108], ["右肩", 91, 74], ["左肘", 164, 151], ["右肘", 170, 165],
  ["左髋", 128, 142], ["右髋", 132, 129], ["左膝", 118, 93], ["右膝", 171, 168],
];

type Phase = "idle" | "camera" | "holding" | "evaluating";

export default function Home() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [pose, setPose] = useState(poses[0]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [hold, setHold] = useState(0);
  const [cameraError, setCameraError] = useState("");

  const score = useMemo(() => phase === "evaluating" ? 82 : 0, [phase]);

  useEffect(() => {
    if (phase !== "holding") return;
    const timer = window.setInterval(() => {
      setHold((value) => {
        if (value >= 100) {
          window.clearInterval(timer);
          setPhase("evaluating");
          return 100;
        }
        return value + 2;
      });
    }, 40);
    return () => window.clearInterval(timer);
  }, [phase]);

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), []);

  async function startCamera() {
    setCameraError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setPhase("camera");
    } catch {
      setCameraError("无法访问摄像头，请允许浏览器摄像头权限。你仍可使用演示模式。 ");
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setPhase("idle");
    setHold(0);
  }

  function runDemo() {
    setHold(0);
    setPhase("holding");
  }

  return (
    <main>
      <nav className="nav shell">
        <a className="brand" href="#top" aria-label="Yoga Tutor 首页"><span>YT</span>Yoga Tutor</a>
        <div className="nav-links"><a href="#practice">实时练习</a><a href="#how">工作原理</a><a href="#hardware">触觉手环</a></div>
        <span className="local-badge"><i /> 本地原型</span>
      </nav>

      <section id="top" className="hero shell">
        <div>
          <p className="eyebrow">视觉感知 × 多方向触觉引导</p>
          <h1>看见偏差，<br /><em>感受</em>正确方向。</h1>
        </div>
        <div className="hero-copy">
          <p>通过摄像头理解你的瑜伽姿势，量化八个关键关节，并把纠正方向发送到腕部触觉设备。</p>
          <a className="button primary" href="#practice">开始一次练习 <span>↗</span></a>
        </div>
      </section>

      <section id="practice" className="studio-band">
        <div className="shell">
          <div className="section-head">
            <div><p className="eyebrow">LIVE STUDIO</p><h2>实时姿势工作台</h2></div>
            <div className="mode-switch" role="group" aria-label="练习模式">
              <button className={mode === "auto" ? "active" : ""} onClick={() => setMode("auto")}>自动识别</button>
              <button className={mode === "manual" ? "active" : ""} onClick={() => setMode("manual")}>手动选择</button>
            </div>
          </div>

          <div className="studio-grid">
            <div className="camera-card">
              <div className="camera-top"><span><i className={phase !== "idle" ? "live" : ""} /> CAMERA 01</span><span>1280 × 720</span></div>
              <div className="camera-stage">
                <video ref={videoRef} autoPlay muted playsInline />
                {phase === "idle" && <div className="camera-empty"><div className="aperture">◎</div><strong>摄像头尚未开启</strong><p>站在画面中央，确保全身可见</p></div>}
                {phase !== "idle" && <div className="scan-frame"><b className="c1"/><b className="c2"/><b className="c3"/><b className="c4"/></div>}
                {phase === "holding" && <div className="hold-overlay"><span>保持不动</span><strong>{hold}%</strong></div>}
                {phase === "evaluating" && <div className="pose-tag"><i /> 已识别 · {pose}</div>}
              </div>
              <div className="camera-actions">
                {phase === "idle" ? <button className="button primary" onClick={startCamera}>开启摄像头</button> : <button className="button outline" onClick={stopCamera}>关闭摄像头</button>}
                <button className="button dark" onClick={runDemo}>{phase === "evaluating" ? "重新评估" : "运行演示评估"}</button>
              </div>
              {cameraError && <p className="error">{cameraError}</p>}
            </div>

            <aside className="control-stack">
              <div className="pose-card card">
                <label htmlFor="pose">目标姿势</label>
                <select id="pose" value={pose} onChange={(e) => setPose(e.target.value)} disabled={mode === "auto"}>
                  {poses.map((name) => <option key={name}>{name}</option>)}
                </select>
                <div className="pose-preview" style={{backgroundImage: `linear-gradient(180deg, transparent 45%, rgba(32,21,21,.78)), url("/poses/${encodeURIComponent(pose)}.jpg")`}}>
                  <span>{mode === "auto" ? "系统将自动匹配姿势" : "当前标准参考"}</span>
                </div>
              </div>

              <div className="score-card card dark-card">
                <div><span>当前评分</span><small>{phase === "evaluating" ? "评估完成" : "等待评估"}</small></div>
                <strong>{score || "—"}<sup>{score ? "/100" : ""}</sup></strong>
                <div className="score-track"><i style={{width: `${score}%`}} /></div>
                <p>{score ? "动作整体良好，优先调整左膝与左肩。" : "完成静止检测后，这里会显示姿势得分。"}</p>
              </div>
            </aside>
          </div>

          <div className="feedback-grid">
            <div className="feedback card">
              <div className="card-title"><div><p className="eyebrow">JOINT ANALYSIS</p><h3>关节偏差</h3></div><span>容差内 5 / 8</span></div>
              <div className="joint-list">
                {joints.map(([name, current, target], index) => {
                  const diff = Number(current) - Number(target); const ok = Math.abs(diff) <= (index < 4 ? 20 : 25);
                  return <div className="joint-row" key={String(name)}><span className={ok ? "status ok" : "status warn"}>{ok ? "✓" : "!"}</span><strong>{name}</strong><span className="angle">{phase === "evaluating" ? `${current}°` : "—"}</span><span className="target">标准 {target}°</span><span className={ok ? "delta ok-text" : "delta"}>{phase === "evaluating" ? `${diff > 0 ? "+" : ""}${diff}°` : "—"}</span></div>
                })}
              </div>
            </div>

            <div id="hardware" className="haptic card dark-card">
              <div className="card-title"><div><p className="eyebrow light">HAPTIC GUIDANCE</p><h3>触觉引导</h3></div><span className="connection"><i /> 演示连接</span></div>
              <div className="band-visuals">
                <div className="wrist"><span>左手腕</span><div className="band"><i className={phase === "evaluating" ? "motor active up" : "motor up"}>↑</i><i className="motor right">→</i><i className={phase === "evaluating" ? "motor active down" : "motor down"}>↓</i><i className="motor left">←</i><b>左肩<br />向上</b></div></div>
                <div className="wrist"><span>右手腕</span><div className="band"><i className="motor up">↑</i><i className="motor right">→</i><i className="motor down">↓</i><i className={phase === "evaluating" ? "motor active left" : "motor left"}>←</i><b>右肘<br />向内</b></div></div>
              </div>
              <p className="haptic-note"><span>01</span> 震动位置表示调整方向，强度随角度偏差增大。</p>
            </div>
          </div>
        </div>
      </section>

      <section id="how" className="how shell">
        <p className="eyebrow">HOW IT WORKS</p><h2>一次评估，四个步骤。</h2>
        <div className="steps">{[
          ["01", "捕捉", "MediaPipe 从摄像头画面中提取 33 个人体关键点。"],
          ["02", "稳定", "1€ Filter 抑制抖动，静止检测等待动作稳定。"],
          ["03", "比较", "八个关节角与标准姿势逐一比较并量化评分。"],
          ["04", "引导", "角度偏差映射为上下、内外四个触觉方向。"],
        ].map(([n,t,d]) => <article key={n}><span>{n}</span><h3>{t}</h3><p>{d}</p></article>)}</div>
      </section>

      <footer><div className="shell"><div className="brand inverse"><span>YT</span>Yoga Tutor</div><p>基于视觉感知和多方向触觉引导的实时动作矫正系统</p><small>LOCAL PROTOTYPE · 2026</small></div></footer>
    </main>
  );
}
