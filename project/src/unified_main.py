"""
unified_main.py
统一的瑜伽教练系统 - 融合 main.py 的 UI 设计和 auto_main.py 的自动识别功能
支持两种模式：
  1. 自动识别模式：无需手动选择，系统自动识别并指导
  2. 手动选择模式：选择特定动作，系统只评估该动作
"""

import os
import sys
import time
import json
import cv2
import numpy as np
from pose_detection import PoseDetector
from one_euro_filter import MultiPointFilter
from action_recognizer import ActionRecognizer
from pose_comparator import PoseComparator
from stillness_detector import StillnessDetector
from haptic_feedback import HapticMapper
from haptic_transport import create_haptic_transport
from config import (
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT,
    STANDARD_POSES_DIR, STANDARD_IMAGES_DIR,
    RECOGNITION_CONFIDENCE_THRESHOLD,
    JOINT_NAME_CN,
)


class UnifiedYogaTutor:
    """统一的瑜伽教练系统"""

    def __init__(self, auto_mode=True, manual_pose_path=None):
        """
        参数:
            auto_mode: True=自动识别模式, False=手动选择模式
            manual_pose_path: 手动模式下的标准动作路径
        """
        print("\n🚀 Initializing Yoga Tutor...")

        self.auto_mode = auto_mode
        
        # 核心模块
        self.detector = PoseDetector(static_mode=False)
        self.mp_filter = MultiPointFilter(num_points=33)
        self.stillness = StillnessDetector()
        
        if auto_mode:
            # 自动模式：加载识别器和所有比较器
            self.recognizer = ActionRecognizer()
            self.comparators = self._load_all_comparators()
            print(f"✅ Load1ed {len(self.comparators)} standard poses")
        else:
            # 手动模式：只加载一个比较器
            self.recognizer = None
            self.comparators = {
                self._get_pose_name(manual_pose_path): PoseComparator(manual_pose_path)
            }
            print(f"✅ Loaded pose: {list(self.comparators.keys())[0]}")

        # 加载标准图片
        self.standard_image = self._load_standard_image(manual_pose_path) if not auto_mode else None

        # 状态管理
        self.current_state = "SEARCHING" if auto_mode else "WAITING"
        self.current_recognized_pose = None
        self.current_confidence = 0.0
        self.current_result = None
        self.pose_locked = False
        self.fps_t = []

        # 统计
        self.pose_history = []
        self.best_score = 0.0
        self.session_start = time.time()

        # 触觉反馈（连接 ESP32 手环）
        self.haptic = create_haptic_transport()  # 默认 USB；设 YOGA_HAPTIC_TRANSPORT=ble 走蓝牙
        self.haptic.connect()
        self._last_haptic_ok = False  # 用于在状态切换时发停止指令

        # UI配置
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
            'detecting': (255, 100, 255),
        }

    def _get_pose_name(self, pose_path):
        """从文件路径获取动作名"""
        return os.path.basename(pose_path).replace('.json', '')

    def _load_all_comparators(self):
        """预加载所有标准动作的比较器"""
        comparators = {}
        for filename in os.listdir(STANDARD_POSES_DIR):
            if not filename.endswith('.json'):
                continue
            pose_name = filename.replace('.json', '')
            filepath = os.path.join(STANDARD_POSES_DIR, filename)
            try:
                comparators[pose_name] = PoseComparator(filepath)
            except Exception as e:
                print(f"⚠️  Failed to load {pose_name}: {e}")
        return comparators

    def _load_standard_image(self, json_path):
        """加载标准姿态的参考图片"""
        if not json_path or not os.path.exists(json_path):
            return None
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
        """主循环"""
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print("❌ Cannot open camera")
            self.haptic.disconnect()
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

        mode_text = "Auto Recognition" if self.auto_mode else f"Manual: {list(self.comparators.keys())[0]}"
        print(f"\n✅ System started - Mode: {mode_text}")
        print("  q=quit  r=reset  s=screenshot  h=help")

        show_help = True

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            self._tick_fps()

            # 检测姿态
            landmarks, annotated = self.detector.detect(frame)

            if landmarks:
                filtered = self.mp_filter.filter_landmarks(landmarks)
                angles = self.detector.calculate_all_angles(filtered)

                if self.auto_mode:
                    # 自动模式：识别 → 等待静止 → 评估
                    self._update_auto_mode(angles, filtered)
                else:
                    # 手动模式：直接等待静止 → 评估
                    self._update_manual_mode(angles, filtered)

                # 绘制UI
                self._draw_main_ui(annotated, filtered)
            else:
                # 未检测到人体 → 停马达
                self.current_state = "SEARCHING" if self.auto_mode else "WAITING"
                self.pose_locked = False
                self.stillness.reset()
                self.current_result = None
                self.haptic.send_stop()
                self._draw_no_pose(annotated)

            # 显示帮助
            if show_help:
                self._draw_help_overlay(annotated)

            # FPS
            fps = self._get_fps()
            cv2.putText(annotated, f"FPS:{fps:.0f}", (annotated.shape[1] - 120, 25),
                        self.font, 0.55, self.C['text'], 1)

            # 拼接标准图片（手动模式）
            display = self._compose_display(annotated) if not self.auto_mode else annotated

            cv2.imshow("Yoga Tutor", display)

            # 键盘控制
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                self._reset_system()
                print("🔄 System reset")
            elif key == ord('s'):
                filename = f"screenshot_{int(time.time())}.jpg"
                cv2.imwrite(filename, display)
                print(f"📸 Screenshot saved: {filename}")
            elif key == ord('h'):
                show_help = not show_help

        cap.release()
        cv2.destroyAllWindows()
        self.haptic.disconnect()
        self._print_session_summary()

    # ==================== 模式管理 ====================

    def _update_auto_mode(self, angles, filtered):
        """自动模式的状态管理"""
        pose_name, confidence, _ = self.recognizer.recognize(angles)

        # 状态转移
        if not pose_name or confidence < RECOGNITION_CONFIDENCE_THRESHOLD:
            self.current_state = "SEARCHING"
            self.pose_locked = False
            self.current_recognized_pose = None
            self.stillness.reset()
            return

        # 识别到动作
        if pose_name != self.current_recognized_pose:
            self.current_recognized_pose = pose_name
            self.current_confidence = confidence
            self.pose_locked = False
            self.stillness.reset()

        # 等待静止
        if not self.pose_locked:
            is_ready = self.stillness.update(filtered)
            
            if is_ready:
                # 静止足够，进行评估
                self.pose_locked = True
                self.current_state = "EVALUATING"
                
                if self.current_recognized_pose in self.comparators:
                    self.current_result = self.comparators[self.current_recognized_pose].compare(angles)
                    self._update_stats(self.current_result['score'])
                    self._send_haptic_feedback()
            else:
                # 还在等待静止
                self.current_state = "HOLDING"
                self.current_confidence = confidence
        else:
            # 已锁定，继续更新评估
            self.current_state = "EVALUATING"
            
            if self.current_recognized_pose in self.comparators:
                self.current_result = self.comparators[self.current_recognized_pose].compare(angles)
                self._update_stats(self.current_result['score'])
                self._send_haptic_feedback()

            # 如果用户动了太多，解锁
            if self.stillness.movement > 50:
                self.pose_locked = False
                self.stillness.reset()

    def _update_manual_mode(self, angles, filtered):
        """手动模式的状态管理"""
        # 直接等待静止
        is_ready = self.stillness.update(filtered)
        
        pose_name = list(self.comparators.keys())[0]
        
        if is_ready and not self.pose_locked:
            # 静止足够，进行评估
            self.pose_locked = True
            self.current_state = "COMPARING"
            self.current_recognized_pose = pose_name
            
            self.current_result = self.comparators[pose_name].compare(angles)
            self._update_stats(self.current_result['score'])
            self._send_haptic_feedback()
        elif is_ready:
            # 已锁定，继续更新
            self.current_state = "COMPARING"
            self.current_result = self.comparators[pose_name].compare(angles)
            self._update_stats(self.current_result['score'])
            self._send_haptic_feedback()

            # 用户移动过多，解锁
            if self.stillness.movement > 50:
                self.pose_locked = False
                self.stillness.reset()
        else:
            # 等待静止
            if self.stillness.progress > 0:
                self.current_state = "HOLDING"
                self.current_recognized_pose = pose_name
            else:
                self.current_state = "WAITING"
                self.current_recognized_pose = pose_name

    # ==================== 触觉反馈 ====================

    def _send_haptic_feedback(self):
        """根据当前评估结果发送马达震动指令"""
        if not self.current_result:
            if self._last_haptic_ok:
                self.haptic.send_stop()
                self._last_haptic_ok = False
            return

        left, right = HapticMapper.translate(self.current_result)

        # 如果完全正确，发个短提示然后停止；否则持续震动
        score = self.current_result.get('score', 0)
        if score >= 95 and not left and not right:
            if self._last_haptic_ok:
                # 之前是震动状态，现在完美了 → 停
                self.haptic.send_stop()
                self._last_haptic_ok = False
            return

        self.haptic.send_motor_command(left, right)
        self._last_haptic_ok = bool(left or right)

    def _reset_system(self):
        """重置系统"""
        self.haptic.send_stop()
        if self.auto_mode and self.recognizer:
            self.recognizer.reset()
        
        self.current_state = "SEARCHING" if self.auto_mode else "WAITING"
        self.current_recognized_pose = None
        self.current_confidence = 0.0
        self.current_result = None
        self.pose_locked = False
        self.stillness.reset()
        self.pose_history.clear()
        self.best_score = 0.0

    # ==================== UI 绘制 ====================

    def _draw_main_ui(self, frame, landmarks):
        """绘制主UI"""
        h, w = frame.shape[:2]

        # 根据模式绘制顶部状态栏
        if self.auto_mode:
            self._draw_auto_mode_ui(frame)
        else:
            self._draw_manual_mode_ui(frame)

        # 绘制左侧评估面板
        if self.current_result:
            self._draw_evaluation_panel(frame)

        # 绘制右侧关节详情
        if self.current_result:
            self._draw_joint_details(frame, w)

    def _draw_auto_mode_ui(self, frame):
        """绘制自动模式的状态栏"""
        h, w = frame.shape[:2]
        
        if self.current_state == "SEARCHING":
            self._draw_status_bar(frame, "SEARCHING - Move into a pose", self.C['cyan'], 0.0)
        
        elif self.current_state == "HOLDING":
            progress = self.stillness.progress
            self._draw_status_bar(frame, f"HOLDING {self.current_recognized_pose} - {int(progress*100)}%", 
                                self.C['progress_fg'], progress)
        
        elif self.current_state == "EVALUATING":
            score = self.current_result['score'] if self.current_result else 0
            color = self._score_color(score)
            self._draw_status_bar(frame, f"EVALUATING {self.current_recognized_pose} - Score: {score:.0f}/100",
                                color, 1.0)

    def _draw_manual_mode_ui(self, frame):
        """绘制手动模式的状态栏（沿用main.py风格）"""
        h, w = frame.shape[:2]
        
        if self.current_state == "WAITING":
            self._draw_status_bar(frame, "Move into the target pose", self.C['cyan'], 0.0)
        
        elif self.current_state == "HOLDING":
            progress = self.stillness.progress
            self._draw_status_bar(frame, f"Hold still... {int(progress*100)}%",
                                self.C['progress_fg'], progress)
        
        elif self.current_state == "COMPARING" and self.current_result:
            self._draw_status_bar(frame, f"Comparing: {self.current_recognized_pose}", 
                                self.C['good'], 1.0)

    def _draw_status_bar(self, frame, text, color, progress):
        """绘制顶部状态栏和进度条"""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 65), self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        cv2.putText(frame, text, (20, 40), self.font, 0.9, color, 2)

        if progress > 0:
            bar_x, bar_y, bar_w, bar_h = 20, 50, w - 40, 6
            cv2.rectangle(frame, (bar_x, bar_y),
                          (bar_x + bar_w, bar_y + bar_h), self.C['progress_bg'], -1)
            fill_w = int(bar_w * progress)
            cv2.rectangle(frame, (bar_x, bar_y),
                          (bar_x + fill_w, bar_y + bar_h), color, -1)

    def _draw_evaluation_panel(self, frame):
        """绘制左侧评估面板"""
        h, w = frame.shape[:2]
        result = self.current_result
        score = result['score']

        # 背景
        feedback_count = len(result['feedback'][:5])
        panel_h = 50 + feedback_count * 30 + 80
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 70), (520, 70 + panel_h), self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        y = 95
        
        # 标题
        cv2.putText(frame, f"Pose: {self.current_recognized_pose}", (15, y), 
                   self.font, 0.7, self.C['text'], 2)
        y += 35

        # 分数
        sc = self._score_color(score)
        cv2.putText(frame, f"Score: {score:.0f}/100", (15, y), self.font, 0.9, sc, 2)
        y += 28

        # 最佳分数
        cv2.putText(frame, f"Best: {self.best_score:.0f}", (15, y), self.font, 0.6, 
                   self.C['good'], 1)
        y += 32

        # 分数条
        bar_x, bar_w = 15, 450
        cv2.rectangle(frame, (bar_x, y), (bar_x + bar_w, y + 18),
                      self.C['progress_bg'], -1)
        fill = int(bar_w * score / 100)
        cv2.rectangle(frame, (bar_x, y), (bar_x + fill, y + 18), sc, -1)
        y += 35

        # 反馈
        if not result['feedback']:
            cv2.putText(frame, "Perfect! Hold the pose!", (15, y), self.font, 0.7, 
                       self.C['good'], 2)
        else:
            cv2.putText(frame, "Adjustments needed:", (15, y), self.font, 0.6, 
                       self.C['warn'], 2)
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

    def _draw_joint_details(self, frame, frame_w):
        """绘制右侧关节详情"""
        result = self.current_result
        if not result:
            return

        deviations = result['deviations']
        x0 = frame_w - 320
        n = len(deviations)

        overlay = frame.copy()
        cv2.rectangle(overlay, (x0 - 10, 70), (frame_w - 5, 115 + n * 28),
                      self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        y = 92
        cv2.putText(frame, "Joint Details", (x0, y), self.font, 0.6, 
                   self.C['text'], 2)
        y += 30

        for joint, d in deviations.items():
            name = JOINT_NAME_CN.get(joint, joint)
            c = self.C['good'] if d['is_correct'] else self.C['bad']

            # 状态标记
            icon = "[OK]" if d['is_correct'] else "[X]"
            cv2.putText(frame, icon, (x0, y), self.font, 0.4, c, 1)

            # 角度
            txt = f"{name}: {d['current']:.0f} / {d['standard']:.0f}"
            cv2.putText(frame, txt, (x0 + 40, y), self.font, 0.42, c, 1)

            # 偏差
            if not d['is_correct']:
                cv2.putText(frame, f"({d['difference']:+.0f})", (x0 + 230, y),
                            self.font, 0.4, self.C['warn'], 1)
            y += 28

    def _draw_no_pose(self, frame):
        """绘制未检测到人体"""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 60), self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        text = "No pose detected - Please stand in frame"
        cv2.putText(frame, text, (20, 40), self.font, 0.8, self.C['warn'], 2)

    def _draw_help_overlay(self, frame):
        """绘制帮助信息"""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (w - 300, h - 150), (w - 10, h - 10),
                      self.C['bg'], -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        y = h - 125
        cv2.putText(frame, "Controls:", (w - 285, y), self.font, 0.6, 
                   self.C['cyan'], 2)
        y += 30
        cv2.putText(frame, "Q - Quit", (w - 280, y), self.font, 0.5, 
                   self.C['text'], 1)
        y += 25
        cv2.putText(frame, "R - Reset", (w - 280, y), self.font, 0.5, 
                   self.C['text'], 1)
        y += 25
        cv2.putText(frame, "S - Screenshot", (w - 280, y), self.font, 0.5, 
                   self.C['text'], 1)
        y += 25
        cv2.putText(frame, "H - Toggle Help", (w - 280, y), self.font, 0.5, 
                   self.C['text'], 1)

    def _compose_display(self, main_frame):
        """拼接主画面和标准图片（手动模式）"""
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

    # ==================== 辅助方法 ====================

    def _score_color(self, score):
        """根据分数返回颜色"""
        if score >= 90:
            return self.C['good']
        elif score >= 70:
            return self.C['warn']
        else:
            return self.C['bad']

    def _update_stats(self, score):
        """更新统计"""
        self.pose_history.append((time.time(), self.current_recognized_pose, score))
        if score > self.best_score:
            self.best_score = score

    def _tick_fps(self):
        self.fps_t.append(time.time())
        if len(self.fps_t) > 30:
            self.fps_t.pop(0)

    def _get_fps(self):
        if len(self.fps_t) < 2:
            return 0
        return (len(self.fps_t) - 1) / (self.fps_t[-1] - self.fps_t[0] + 1e-9)

    def _print_session_summary(self):
        """打印会话总结"""
        print("\n" + "=" * 60)
        print("  Session Summary")
        print("=" * 60)

        duration = time.time() - self.session_start
        print(f"  Duration: {duration / 60:.1f} minutes")
        print(f"  Mode: {'Auto Recognition' if self.auto_mode else 'Manual'}")

        if self.pose_history:
            pose_counts = {}
            pose_scores = {}
            
            for _, pose, score in self.pose_history:
                pose_counts[pose] = pose_counts.get(pose, 0) + 1
                if pose not in pose_scores:
                    pose_scores[pose] = []
                pose_scores[pose].append(score)

            print(f"\n  Total evaluations: {len(self.pose_history)}")
            print(f"  Best score: {self.best_score:.0f}")
            print(f"\n  Poses practiced:")
            
            for pose, count in sorted(pose_counts.items(), key=lambda x: x[1], reverse=True):
                avg_score = sum(pose_scores[pose]) / len(pose_scores[pose])
                print(f"    {pose}: {count} times (avg: {avg_score:.0f})")

        print("=" * 60 + "\n")


# ==================== 入口 ====================

def _select_mode():
    """选择运行模式"""
    print("\n" + "=" * 70)
    print("  🧘 YOGA TUTOR - Unified System")
    print("=" * 70)
    print("\n  Select mode:")
    print("  1. Auto Recognition Mode (自动识别模式)")
    print("     → System automatically detects and evaluates all poses")
    print("     → No need to select poses manually")
    print("\n  2. Manual Mode (手动选择模式)")
    print("     → Select a specific pose to practice")
    print("     → System focuses on evaluating that pose")
    print("\n" + "=" * 70)
    
    choice = input("\n  Enter choice (1 or 2, default=1): ").strip() or '1'
    
    return choice == '1'


def _select_pose_for_manual_mode():
    """为手动模式选择姿态"""
    pose_dir = STANDARD_POSES_DIR
    
    if not os.path.exists(pose_dir):
        os.makedirs(pose_dir, exist_ok=True)
    
    pose_files = sorted([f for f in os.listdir(pose_dir) if f.endswith('.json')])
    
    if not pose_files:
        print("\n❌ No standard poses found!")
        print(f"   Please add pose files to '{pose_dir}/'")
        return None
    
    print("\n  Available poses:")
    for i, pose_file in enumerate(pose_files, 1):
        pose_name = pose_file.replace('.json', '')
        print(f"    {i}. {pose_name}")
    
    choice = input(f"\n  Select pose (1-{len(pose_files)}, default=1): ").strip() or '1'
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(pose_files):
            return os.path.join(pose_dir, pose_files[idx])
    except ValueError:
        pass
    
    return os.path.join(pose_dir, pose_files[0])


def _ensure_standard_poses():
    """确保标准姿态数据存在"""
    os.makedirs(STANDARD_POSES_DIR, exist_ok=True)
    files = sorted([f for f in os.listdir(STANDARD_POSES_DIR) if f.endswith('.json')])
    
    if files:
        return True
    
    # 尝试自动提取
    if os.path.isdir(STANDARD_IMAGES_DIR):
        imgs = [f for f in os.listdir(STANDARD_IMAGES_DIR)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        if imgs:
            print(f"\n  Found {len(imgs)} standard images, extracting...")
            try:
                from standard_pose_extractor import StandardPoseExtractor
                extractor = StandardPoseExtractor()
                extractor.extract_all_images()
                files = sorted([f for f in os.listdir(STANDARD_POSES_DIR) if f.endswith('.json')])
                return len(files) > 0
            except Exception as e:
                print(f"  ⚠️  Extraction failed: {e}")
    
    return False


def main():
    """主入口"""
    # 检查标准数据
    if not _ensure_standard_poses():
        print("\n" + "=" * 70)
        print("  ❌ No standard pose data found!")
        print("=" * 70)
        print(f"\n  1. Put standard pose images in '{STANDARD_IMAGES_DIR}/'")
        print("     Supported formats: jpg, png, bmp")
        print(f"     Example: {STANDARD_IMAGES_DIR}/warrior_1.jpg")
        print("\n  2. Run: python standard_pose_extractor.py")
        print("\n  3. Then run: python unified_main.py")
        print("=" * 70 + "\n")
        return

    # 选择模式
    auto_mode = _select_mode()
    
    if auto_mode:
        # 自动模式
        app = UnifiedYogaTutor(auto_mode=True)
    else:
        # 手动模式
        pose_path = _select_pose_for_manual_mode()
        if pose_path is None:
            return
        app = UnifiedYogaTutor(auto_mode=False, manual_pose_path=pose_path)
    
    # 启动应用
    app.run()


if __name__ == "__main__":
    main()
