"""
action_recognizer.py
动作识别器 - 实时识别用户当前做的瑜伽动作
"""

import os
import json
import numpy as np
from collections import deque
from typing import Dict, Optional, Tuple
from config import (
    STANDARD_POSES_DIR,
    RECOGNITION_MIN_SCORE,
    RECOGNITION_STABLE_FRAMES,
    RECOGNITION_CONFIDENCE_THRESHOLD,
    ANGLE_THRESHOLDS
)


class ActionRecognizer:
    """
    智能动作识别器
    通过角度相似度自动识别用户当前做的瑜伽动作
    """

    def __init__(self, pose_dir=STANDARD_POSES_DIR):
        self.pose_dir = pose_dir
        self.pose_library = {}  # {pose_name: standard_angles}
        self._load_all_poses()

        # 识别状态
        self.history = deque(maxlen=RECOGNITION_STABLE_FRAMES)  # 历史识别结果
        self.current_pose = None
        self.current_confidence = 0.0
        self.stable_count = 0

        print(f"✅ Action Recognizer initialized with {len(self.pose_library)} poses")

    def _load_all_poses(self):
        """加载所有标准动作的角度数据"""
        if not os.path.exists(self.pose_dir):
            print(f"⚠️  Warning: {self.pose_dir} not found")
            return

        count = 0
        for filename in os.listdir(self.pose_dir):
            if not filename.endswith('.json'):
                continue

            pose_name = filename.replace('.json', '')
            filepath = os.path.join(self.pose_dir, filename)

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    angles = data['average_pose']['angles']
                    self.pose_library[pose_name] = angles
                    count += 1
            except Exception as e:
                print(f"⚠️  Failed to load {filename}: {e}")

        if count == 0:
            print(f"⚠️  No poses loaded from {self.pose_dir}")

    def recognize(self, user_angles: Dict[str, float]) -> Tuple[Optional[str], float, Dict]:
        """
        识别当前动作

        参数:
            user_angles: 用户当前关节角度 {'left_elbow': 165.0, ...}

        返回:
            (pose_name, confidence, match_details)
            pose_name: 识别出的动作名称（None表示无法识别）
            confidence: 置信度（0-100）
            match_details: 匹配详情
        """
        if not user_angles or not self.pose_library:
            return None, 0.0, {}

        # 计算与所有标准动作的相似度
        scores = {}
        for pose_name, standard_angles in self.pose_library.items():
            score = self._calculate_similarity(user_angles, standard_angles)
            scores[pose_name] = score

        # 找出最佳匹配
        if not scores:
            return None, 0.0, {}

        best_pose = max(scores, key=scores.get)
        best_score = scores[best_pose]

        # 获取详细匹配信息
        match_details = self._get_match_details(
            user_angles,
            self.pose_library[best_pose]
        )

        # 判断是否达到识别阈值
        if best_score < RECOGNITION_MIN_SCORE:
            return None, best_score, match_details

        # 添加到历史记录
        self.history.append((best_pose, best_score))

        # 检查稳定性
        recognized_pose = self._check_stability(best_pose, best_score)

        return recognized_pose, best_score, match_details

    def _calculate_similarity(self, user_angles: Dict[str, float],
                              standard_angles: Dict[str, float]) -> float:
        """
        计算角度相似度（转换为0-100分）

        算法：
        1. 对每个关节计算角度差异
        2. 根据阈值判断是否达标
        3. 达标的关节越多，分数越高
        """
        total_joints = 0
        matched_joints = 0
        total_deviation = 0.0

        for joint, standard_angle in standard_angles.items():
            if joint not in user_angles:
                continue

            total_joints += 1
            user_angle = user_angles[joint]
            deviation = abs(user_angle - standard_angle)
            threshold = ANGLE_THRESHOLDS.get(joint, 20)

            # 计算匹配度
            if deviation <= threshold:
                matched_joints += 1
                # 在阈值内的，根据偏差给分
                joint_score = (1 - deviation / threshold) * 100
            else:
                # 超出阈值的，根据超出程度扣分
                overshoot = deviation - threshold
                joint_score = max(0, 100 - overshoot * 2)

            total_deviation += joint_score

        if total_joints == 0:
            return 0.0

        # 综合评分：匹配率 + 平均关节得分
        match_ratio = matched_joints / total_joints
        avg_joint_score = total_deviation / total_joints

        # 权重：匹配率占60%，平均分占40%
        final_score = match_ratio * 60 + avg_joint_score * 0.4

        return round(final_score, 1)

    def _get_match_details(self, user_angles: Dict[str, float],
                          standard_angles: Dict[str, float]) -> Dict:
        """获取详细匹配信息"""
        details = {}
        for joint, standard_angle in standard_angles.items():
            if joint not in user_angles:
                continue

            user_angle = user_angles[joint]
            deviation = abs(user_angle - standard_angle)
            threshold = ANGLE_THRESHOLDS.get(joint, 20)

            details[joint] = {
                'user': user_angle,
                'standard': standard_angle,
                'deviation': deviation,
                'threshold': threshold,
                'matched': deviation <= threshold
            }

        return details

    def _check_stability(self, current_best: str, current_score: float) -> Optional[str]:
        """
        检查识别稳定性

        要求：连续N帧识别到同一动作，且分数稳定
        """
        if len(self.history) < RECOGNITION_STABLE_FRAMES:
            return None

        # 统计最近N帧中各个动作出现的次数
        pose_counts = {}
        for pose, score in self.history:
            pose_counts[pose] = pose_counts.get(pose, 0) + 1

        # 找出出现最多的动作
        most_common_pose = max(pose_counts, key=pose_counts.get)
        most_common_count = pose_counts[most_common_pose]

        # 如果超过80%的帧识别到同一动作，且分数达标
        if (most_common_count >= RECOGNITION_STABLE_FRAMES * 0.8 and
            current_score >= RECOGNITION_MIN_SCORE):

            # 更新当前识别结果
            if most_common_pose != self.current_pose:
                self.current_pose = most_common_pose
                self.current_confidence = current_score
                self.stable_count = 0
                print(f"🔍 Detected: {most_common_pose} (confidence: {current_score:.1f})")
            else:
                self.stable_count += 1
                self.current_confidence = current_score

            return most_common_pose

        return self.current_pose

    def get_status(self) -> Dict:
        """获取当前识别状态"""
        return {
            'pose': self.current_pose,
            'confidence': self.current_confidence,
            'stable_count': self.stable_count,
            'is_stable': self.stable_count >= RECOGNITION_STABLE_FRAMES,
        }

    def reset(self):
        """重置识别器"""
        self.history.clear()
        self.current_pose = None
        self.current_confidence = 0.0
        self.stable_count = 0