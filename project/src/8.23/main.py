"""
main.py
Yoga Tutor 主系统（含手环震动反馈）
"""

import os
import sys
import time
import json
import cv2
import numpy as np
from pose_detection import PoseDetector
from one_euro_filter import MultiPointFilter
from pose_comparator import PoseComparator
from stillness_detector import StillnessDetector
from esp32_controller import ESP32Controller
from haptic_feedback import HapticMapper
from config import (
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT,
    STANDARD_POSES_DIR, STANDARD_IMAGES_DIR, JOINT_NAME_CN,
)

class YogaTutorApp:

    def __init__(self, standard_pose_path):
        self.detector = PoseDetector(static_mode=False)
        self.mp_filter = MultiPointFilter(num_points=33)
        self.comparator = PoseComparator(standard_pose_path)
        self.stillness = StillnessDetector()

        # 手环（失败也不影响主流程）
        self.band = ESP32Controller()
        self.band.connect()

        # 加载标准图片用于侧边显示
        self.standard_image = self._load_standard_image(standard_pose_path)

        # 状态
        self.state = "waiting"
        self.last_result = None
        self.best_score = 0.0
        self.score_history = []
        self.fps_t = []

        # UI
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.C = {
            'good': (0, 255, 0),
            'warn': (0, 165, 255),
            'bad': (0, 0, 255),
            'text': (255, 255, 255),
            'bg': (30, 30, 30),
            'cyan': (255, 255, 0),
            'progress_bg': (80, 80, 80),
            'progress_fg': (0, 200, 255),
        }

    def _load_standard_image(self, json_path):
        """尝试加载对应的标准图片"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            src_file = data.get('source_file', '')
            if src_file:
                img_path = os.path.join(STANDARD_IMAGES_DIR, src_file)
                if os.path.exists(img_path):
                    img = cv2.imread(img_path)
                    if img is not None:
                        target_h = 300
                        scale = target_h / img.shape[0]
                        img = cv2.resize(img, None, fx=scale, fy=scale)
                        return img
        except Exception:
            pass
        return None

    # ==================== 主循环 ====================

    def run(self):
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print("Cannot open camera")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

        print(f"\nSystem started - Target pose: {self.comparator.pose_name}")
        print("  Hold a pose steady and the system will auto-evaluate")
        if self.band.connected:
            print("  Haptic band: CONNECTED")
        else:
            print("  Haptic band: not connected (visual feedback only)")
        print("  q=quit  r=reset  s=screenshot")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            self._tick_fps()

            # 检测
            landmarks, annotated = self.detector.detect(frame)

            if landmarks:
                filtered = self.mp_filter.filter_landmarks(landmarks)
                is_ready = self.stillness.update(filtered)

                if is_ready:
                    self.state = "comparing"
                    angles = self.detector.calculate_all_angles(filtered)
                    self.last_result = self.comparator.compare(angles)
                    self._update_stats(self.last_result['score'])
                    # ---- 手环震动 ----
                    self._update_haptic(self.last_result)
                elif self.stillness.progress > 0:
                    self.state = "holding"
                else:
                    self.state = "waiting"
                    self.band.send_stop()   # 没在比较时停止震动

                self._draw_main_ui(annotated, filtered)
            else:
                self.state = "waiting"
                self.band.send_stop()
                self._draw_no_pose(annotated)

            # 拼接标准图片
            display = self._compose_display(annotated)
            cv2.imshow("Yoga Tutor", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                self.best_score = 0
                self.score_history.clear()
                self.last_result = None
                self.band.send_stop()
                print("Stats reset")
            elif key == ord('s'):
                fn = f"screenshot_{int(time.time())}.jpg"
                cv2.imwrite(fn, display)
                print(f"Screenshot saved: {fn}")

        cap.release()
        cv2.destroyAllWindows()
        self.band.disconnect()   # 退出时关闭手环

    # ==================== 手环逻辑 ====================

    def _update_haptic(self, result):
        """
        根据比较结果更新手环震动。
        - 满分（无反馈）→ 停止
        - 有反馈 → 从 feedback message 中推断方向
        """
        if not self.band.connected:
            return

        left, right = HapticMapper.translate(result)
        self.band.send_motor_command(left, right)

    # ==================== UI 绘制 ====================

    def _draw_main_ui(self, frame, landmarks):
        h, w = frame.shape[:2]

        if self.state == "waiting":
            self._draw_status_bar(frame, "Move into the target pose", self.C['cyan'], 0.0)

        elif self.state == "holding":
            progress = self.stillness.progress
            self._draw_status_bar(frame, f"Hold still... {int(progress * 100)}%",
                                  self.C['progress_fg'], progress)

        elif self.state == "comparing" and self.last_result:
            self._draw_comparison(frame, self.last_result)

        # FPS + 移动量 + 手环状态
        fps = self._get_fps()
        mv = self.stillness.movement
        band_str = "Band:ON" if self.band.connected else "Band:--"
        cv2.putText(frame, f"FPS:{fps:.0f} Move:{mv:.1f}px {band_str}",
                    (w - 310, 25), self.font, 0.55, self.C['text'], 1)

    def _draw_status_bar(self, frame, text, color, progress):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 60), self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        cv2.putText(frame, text, (20, 40), self.font, 0.9, color, 2)

        if progress > 0:
            bar_x, bar_y, bar_w, bar_h = 20, 50, w - 40, 6
            cv2.rectangle(frame, (bar_x, bar_y),
                          (bar_x + bar_w, bar_y + bar_h), self.C['progress_bg'], -1)
            fill_w = int(bar_w * progress)
            cv2.rectangle(frame, (bar_x, bar_y),
                          (bar_x + fill_w, bar_y + bar_h), self.C['progress_fg'], -1)

    def _draw_comparison(self, frame, result):
        h, w = frame.shape[:2]
        score = result['score']

        # 顶部分数
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 65), self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        sc = self._score_color(score)
        cv2.putText(frame, f"Score: {score:.0f}/100", (20, 28), self.font, 0.9, sc, 2)
        cv2.putText(frame, f"Best: {self.best_score:.0f}", (20, 55), self.font, 0.5, self.C['good'], 1)

        # 分数条
        bar_x, bar_w = 250, 400
        cv2.rectangle(frame, (bar_x, 15), (bar_x + bar_w, 35), self.C['progress_bg'], -1)
        fill = int(bar_w * score / 100)
        cv2.rectangle(frame, (bar_x, 15), (bar_x + fill, 35), sc, -1)

        # 左侧反馈
        feedback_count = len(result['feedback'][:5])
        panel_h = 50 + feedback_count * 30 + 80
        overlay2 = frame.copy()
        cv2.rectangle(overlay2, (5, 70), (520, 70 + panel_h), self.C['bg'], -1)
        cv2.addWeighted(overlay2, 0.65, frame, 0.35, 0, frame)

        y = 95
        if not result['feedback']:
            cv2.putText(frame, "Perfect! Hold the pose!", (15, y), self.font, 0.7, self.C['good'], 2)
        else:
            cv2.putText(frame, "Adjustments needed:", (15, y), self.font, 0.6, self.C['warn'], 2)
            y += 30
            for item in result['feedback'][:5]:
                c = self.C['bad'] if item['severity'] == 'BAD' else self.C['warn']
                cv2.putText(frame, item['message'], (15, y), self.font, 0.5, c, 1)
                y += 28

            # 纠正建议
            y += 10
            hints = PoseComparator.get_correction_hints(result['deviations'])
            for hint in hints[:3]:
                cv2.putText(frame, hint, (15, y), self.font, 0.48, self.C['cyan'], 1)
                y += 26

        # 右侧关节详情
        self._draw_joint_details(frame, result['deviations'], w)

    def _draw_joint_details(self, frame, deviations, fw):
        x0 = fw - 320
        n = len(deviations)

        overlay = frame.copy()
        cv2.rectangle(overlay, (x0 - 10, 70), (fw - 5, 115 + n * 28),
                      self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        y = 92
        cv2.putText(frame, "Joint Details", (x0, y), self.font, 0.6, self.C['text'], 2)
        y += 30

        for joint, d in deviations.items():
            name = JOINT_NAME_CN.get(joint, joint)
            c = self.C['good'] if d['is_correct'] else self.C['bad']

            icon = "[OK]" if d['is_correct'] else "[X]"
            cv2.putText(frame, icon, (x0, y), self.font, 0.4, c, 1)

            txt = f"{name}: {d['current']:.0f} / {d['standard']:.0f}"
            cv2.putText(frame, txt, (x0 + 40, y), self.font, 0.42, c, 1)

            if not d['is_correct']:
                cv2.putText(frame, f"({d['difference']:+.0f})", (x0 + 230, y),
                            self.font, 0.4, self.C['warn'], 1)
            y += 28

    def _draw_no_pose(self, frame):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 60), self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        cv2.putText(frame, "No pose detected - Please stand in frame",
                    (20, 40), self.font, 0.8, self.C['warn'], 2)

    def _compose_display(self, main_frame):
        if self.standard_image is None:
            return main_frame

        mh, mw = main_frame.shape[:2]
        sh, sw = self.standard_image.shape[:2]

        if sh > mh:
            scale = mh / sh
            ref_img = cv2.resize(self.standard_image, None, fx=scale, fy=scale)
            sh, sw = ref_img.shape[:2]
        else:
            ref_img = self.standard_image

        canvas = np.zeros((mh, mw + sw + 10, 3), dtype=np.uint8)
        canvas[:mh, :mw] = main_frame

        y_offset = max(0, (mh - sh) // 2)
        canvas[y_offset:y_offset + sh, mw + 5:mw + 5 + sw] = ref_img

        cv2.putText(canvas, "Standard", (mw + 10, y_offset - 10),
                    self.font, 0.7, self.C['cyan'], 2)

        return canvas

    # ==================== 辅助 ====================

    def _score_color(self, s):
        if s >= 90: return self.C['good']
        if s >= 70: return self.C['warn']
        return self.C['bad']

    def _update_stats(self, score):
        self.score_history.append(score)
        if score > self.best_score:
            self.best_score = score

    def _tick_fps(self):
        self.fps_t.append(time.time())
        if len(self.fps_t) > 30:
            self.fps_t.pop(0)

    def _get_fps(self):
        if len(self.fps_t) < 2: return 0
        return (len(self.fps_t) - 1) / (self.fps_t[-1] - self.fps_t[0] + 1e-9)


# ==================== 入口 ====================

def _ensure_standard_poses():
    os.makedirs(STANDARD_POSES_DIR, exist_ok=True)
    files = sorted(f for f in os.listdir(STANDARD_POSES_DIR) if f.endswith('.json'))

    if files:
        return files

    if os.path.isdir(STANDARD_IMAGES_DIR):
        imgs = [f for f in os.listdir(STANDARD_IMAGES_DIR)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        if imgs:
            print(f"\nFound {len(imgs)} standard images, extracting...")
            from standard_pose_extractor import StandardPoseExtractor
            extractor = StandardPoseExtractor()
            extractor.extract_all_images()
            files = sorted(f for f in os.listdir(STANDARD_POSES_DIR) if f.endswith('.json'))
            if files:
                return files

    print("\n" + "=" * 60)
    print("  No standard pose data found!")
    print("=" * 60)
    print(f"\n  Put standard pose images in '{STANDARD_IMAGES_DIR}/' folder")
    print("  Supported: jpg, png, bmp")
    print(f"  Example: {STANDARD_IMAGES_DIR}/warrior_1.jpg")
    print(f"\n  Then run: python main.py")
    return []


def _select_pose(files):
    print("\nAvailable poses:")
    for i, f in enumerate(files, 1):
        name = f.replace('.json', '')
        try:
            with open(os.path.join(STANDARD_POSES_DIR, f), 'r', encoding='utf-8') as fp:
                src = json.load(fp).get('source', '?')
        except Exception:
            src = '?'
        print(f"  {i}. {name}  [{src}]")

    choice = input(f"\nSelect (1-{len(files)}, default=1): ").strip() or '1'
    try:
        idx = int(choice) - 1
        return os.path.join(STANDARD_POSES_DIR, files[idx])
    except (ValueError, IndexError):
        return os.path.join(STANDARD_POSES_DIR, files[0])


def main():
    print("=" * 60)
    print("  Yoga Tutor - Smart Yoga Coach")
    print("=" * 60)

    files = _ensure_standard_poses()
    if not files:
        return

    pose_path = _select_pose(files)
    app = YogaTutorApp(pose_path)
    app.run()


if __name__ == "__main__":
    main()
