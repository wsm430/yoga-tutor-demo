"""
pose_detection.py
姿态检测模块
"""

import cv2
import mediapipe as mp
import numpy as np
from config import (
    MODEL_COMPLEXITY, MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE, LANDMARK_INDICES, ANGLE_DEFINITIONS
)


class PoseDetector:

    def __init__(self, static_mode=False):
        """
        参数:
            static_mode: True=图片模式(精度高), False=视频模式(速度快)
        """
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_styles = mp.solutions.drawing_styles

        self.pose = self.mp_pose.Pose(
            static_image_mode=static_mode,
            model_complexity=MODEL_COMPLEXITY,
            smooth_landmarks=True,
            min_detection_confidence=MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
        )

    def detect(self, frame):
        """
        检测姿态
        返回: (landmarks列表 或 None, 标注后的图像)
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)
        annotated = frame.copy()
        landmarks = None

        if results.pose_landmarks:
            self.mp_draw.draw_landmarks(
                annotated,
                results.pose_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                self.mp_styles.get_default_pose_landmarks_style(),
            )
            h, w = frame.shape[:2]
            landmarks = []
            for lm in results.pose_landmarks.landmark:
                landmarks.append({
                    'x': lm.x * w,
                    'y': lm.y * h,
                    'z': lm.z,
                    'visibility': lm.visibility,
                })
        return landmarks, annotated

    @staticmethod
    def _angle_between(a, b, c):
        """计算 a-b-c 三点夹角，b为顶点"""
        if isinstance(a, dict):
            ax, ay = a['x'], a['y']
            bx, by = b['x'], b['y']
            cx, cy = c['x'], c['y']
        else:
            ax, ay = a
            bx, by = b
            cx, cy = c
        v1 = np.array([ax - bx, ay - by])
        v2 = np.array([cx - bx, cy - by])
        cos_val = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        return float(np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0))))

    def calculate_angle(self, landmarks, p1_name, p2_name, p3_name):
        """按关键点名称计算角度"""
        idx1 = LANDMARK_INDICES.get(p1_name)
        idx2 = LANDMARK_INDICES.get(p2_name)
        idx3 = LANDMARK_INDICES.get(p3_name)
        if None in (idx1, idx2, idx3) or landmarks is None:
            return None
        if max(idx1, idx2, idx3) >= len(landmarks):
            return None
        return self._angle_between(landmarks[idx1], landmarks[idx2], landmarks[idx3])

    def calculate_all_angles(self, landmarks):
        """计算所有关节角度"""
        angles = {}
        for joint, (p1, p2, p3) in ANGLE_DEFINITIONS.items():
            val = self.calculate_angle(landmarks, p1, p2, p3)
            if val is not None:
                angles[joint] = val
        return angles