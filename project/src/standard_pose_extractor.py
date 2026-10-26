"""
standard_pose_extractor.py
标准动作提取器 —— 支持图片 / 视频 / 摄像头
"""

import os
import cv2
import json
import numpy as np
from pose_detection import PoseDetector
from config import ANGLE_DEFINITIONS, STANDARD_POSES_DIR, STANDARD_IMAGES_DIR


class StandardPoseExtractor:

    def __init__(self):
        # 图片模式用 static_image_mode=True 精度更高
        self.detector_static = PoseDetector(static_mode=True)
        self.detector_video = PoseDetector(static_mode=False)

    # ==================== 从图片提取（核心新功能） ====================

    def extract_from_image(self, image_path, output_json, pose_name="unknown"):
        """
        从单张标准图片提取姿势数据

        参数:
            image_path:  图片路径（jpg/png）
            output_json: 输出JSON路径
            pose_name:   姿势名称
        返回:
            成功与否
        """
        img = cv2.imread(image_path)
        if img is None:
            print(f"❌ 无法读取图片: {image_path}")
            return False

        print(f"📸 从图片提取 [{pose_name}]: {image_path}")
        print(f"   图片尺寸: {img.shape[1]}x{img.shape[0]}")

        # 检测姿态
        landmarks, annotated = self.detector_static.detect(img)

        if landmarks is None:
            print("❌ 未检测到人体姿态！请确认：")
            print("   1. 图片中有完整的人体")
            print("   2. 光线充足、背景简洁")
            print("   3. 人体没有严重遮挡")
            return False

        # 检查关键点可见度
        low_vis = [i for i, lm in enumerate(landmarks) if lm['visibility'] < 0.5]
        if len(low_vis) > 10:
            print(f"⚠️  警告: {len(low_vis)} 个关键点可见度低，结果可能不准确")

        # 计算角度
        angles = self.detector_static.calculate_all_angles(landmarks)

        if len(angles) < 4:
            print(f"❌ 仅检测到 {len(angles)} 个角度，数据不足")
            return False

        # 归一化关键点
        h, w = img.shape[:2]
        norm_lm = [{
            'x': lm['x'] / w, 'y': lm['y'] / h,
            'z': lm['z'], 'visibility': lm['visibility'],
        } for lm in landmarks]

        # 构造数据
        data = {
            'pose_name': pose_name,
            'source': 'image',
            'source_file': os.path.basename(image_path),
            'image_size': [w, h],
            'total_frames': 1,
            'average_pose': {
                'landmarks': norm_lm,
                'angles': {k: float(v) for k, v in angles.items()},
            },
            'frame_sequence': [{
                'frame_id': 0,
                'landmarks': norm_lm,
                'angles': {k: float(v) for k, v in angles.items()},
            }],
        }

        # 保存
        os.makedirs(os.path.dirname(output_json) or '.', exist_ok=True)
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✅ 提取成功 → {output_json}")
        print(f"📊 标准角度:")
        for k, v in angles.items():
            print(f"   {k}: {v:.1f}°")

        # 显示检测结果
        self._show_result(annotated, angles, pose_name)

        return True

    # ==================== 批量从图片目录提取 ====================

    def extract_all_images(self, image_dir=None, output_dir=None):
        """
        扫描图片目录，批量提取所有图片

        图片文件名即为姿势名称：
            warrior_1.jpg → pose_name = warrior_1
        """
        image_dir = image_dir or STANDARD_IMAGES_DIR
        output_dir = output_dir or STANDARD_POSES_DIR

        if not os.path.isdir(image_dir):
            print(f"❌ 图片目录不存在: {image_dir}")
            print(f"   请创建目录并放入标准动作图片")
            return

        extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
        files = sorted(f for f in os.listdir(image_dir)
                       if f.lower().endswith(extensions))

        if not files:
            print(f"❌ {image_dir} 中没有图片文件")
            return

        print(f"\n{'=' * 60}")
        print(f"  批量提取标准姿势（共 {len(files)} 张图片）")
        print(f"{'=' * 60}")

        success, fail = 0, 0

        for fname in files:
            pose_name = os.path.splitext(fname)[0]
            img_path = os.path.join(image_dir, fname)
            json_path = os.path.join(output_dir, f"{pose_name}.json")

            print(f"\n{'─' * 50}")

            if os.path.exists(json_path):
                print(f"⚠️  跳过（已存在）: {json_path}")
                continue

            ok = self.extract_from_image(img_path, json_path, pose_name)
            if ok:
                success += 1
            else:
                fail += 1

        print(f"\n{'=' * 60}")
        print(f"  完成! 成功: {success}  失败: {fail}")
        print(f"{'=' * 60}")

    # ==================== 从视频提取 ====================

    def extract_from_video(self, video_path, output_json, pose_name="unknown"):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ 无法打开视频: {video_path}")
            return False

        print(f"🎬 从视频提取 [{pose_name}]")
        frames_data = []
        count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            count += 1
            if count % 5 != 0:
                continue

            landmarks, _ = self.detector_video.detect(frame)
            if landmarks is None:
                continue

            h, w = frame.shape[:2]
            angles = self.detector_video.calculate_all_angles(landmarks)
            norm_lm = [{'x': lm['x']/w, 'y': lm['y']/h,
                        'z': lm['z'], 'visibility': lm['visibility']}
                       for lm in landmarks]

            frames_data.append({
                'frame_id': len(frames_data),
                'landmarks': norm_lm,
                'angles': angles,
            })

        cap.release()
        return self._save_sequence(frames_data, output_json, pose_name, 'video')

    # ==================== 内部方法 ====================

    def _save_sequence(self, frames_data, output_json, pose_name, source):
        if not frames_data:
            print("❌ 未采集到有效帧")
            return False

        avg = self._calc_average(frames_data)
        data = {
            'pose_name': pose_name,
            'source': source,
            'total_frames': len(frames_data),
            'average_pose': avg,
            'frame_sequence': frames_data,
        }
        os.makedirs(os.path.dirname(output_json) or '.', exist_ok=True)
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✅ 完成！共 {len(frames_data)} 帧 → {output_json}")
        for k, v in avg['angles'].items():
            print(f"   {k}: {v:.1f}°")
        return True

    @staticmethod
    def _calc_average(frames_data):
        n = len(frames_data)
        start = n // 4
        end = max(3 * n // 4, start + 1)
        stable = frames_data[start:end] or frames_data

        avg_angles = {}
        for key in ANGLE_DEFINITIONS:
            vals = [f['angles'][key] for f in stable if key in f['angles']]
            if vals:
                avg_angles[key] = float(np.mean(vals))

        num_lm = len(stable[0]['landmarks'])
        avg_lm = []
        for i in range(num_lm):
            avg_lm.append({
                'x': float(np.mean([f['landmarks'][i]['x'] for f in stable])),
                'y': float(np.mean([f['landmarks'][i]['y'] for f in stable])),
                'z': float(np.mean([f['landmarks'][i]['z'] for f in stable])),
                'visibility': stable[0]['landmarks'][i]['visibility'],
            })
        return {'landmarks': avg_lm, 'angles': avg_angles}

    @staticmethod
    def _show_result(annotated, angles, pose_name):
        """显示提取结果预览"""
        h, w = annotated.shape[:2]
        scale = min(800 / w, 600 / h, 1.0)
        if scale < 1.0:
            annotated = cv2.resize(annotated, None, fx=scale, fy=scale)

        y = 30
        cv2.putText(annotated, f"Pose: {pose_name}", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        y += 35
        for k, v in angles.items():
            cv2.putText(annotated, f"{k}: {v:.1f}", (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            y += 25

        cv2.imshow("Extracted Pose (press any key)", annotated)
        cv2.waitKey(3000)
        cv2.destroyWindow("Extracted Pose (press any key)")


# ==================== 命令行入口 ====================
if __name__ == "__main__":
    extractor = StandardPoseExtractor()

    print("=" * 60)
    print("  瑜伽标准动作提取工具")
    print("=" * 60)
    print("  1. 从单张图片提取")
    print("  2. 批量提取图片目录")
    print("  3. 从视频文件提取")

    choice = input("\n请选择模式 (1/2/3): ").strip()

    if choice == '1':
        img = input("图片路径: ").strip()
        name = input("姿势名称: ").strip() or "unknown"
        out = os.path.join(STANDARD_POSES_DIR, f"{name}.json")
        extractor.extract_from_image(img, out, name)

    elif choice == '2':
        img_dir = input(f"图片目录 (默认 {STANDARD_IMAGES_DIR}): ").strip()
        extractor.extract_all_images(img_dir or None)

    elif choice == '3':
        vid = input("视频路径: ").strip()
        name = input("姿势名称: ").strip() or "unknown"
        out = os.path.join(STANDARD_POSES_DIR, f"{name}.json")
        extractor.extract_from_video(vid, out, name)

    else:
        print("❌ 无效选择")