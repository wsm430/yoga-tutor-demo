"""
pose_comparator.py
动作对比评估
"""

import json
from typing import Dict, List
from config import ANGLE_THRESHOLDS, JOINT_NAME_CN


class PoseComparator:

    def __init__(self, standard_pose_path: str):
        with open(standard_pose_path, 'r', encoding='utf-8') as f:
            self.standard_data = json.load(f)

        self.pose_name = self.standard_data['pose_name']
        self.standard_angles = self.standard_data['average_pose']['angles']
        self.source = self.standard_data.get('source', 'unknown')

        print(f"[Pose] Loaded: {self.pose_name} (source: {self.source}, "
              f"{len(self.standard_angles)} joints)")

    def compare(self, user_angles: Dict[str, float]) -> Dict:
        deviations = {}
        feedback = []
        total_score = 100.0

        for joint, std_angle in self.standard_angles.items():
            if joint not in user_angles:
                continue

            diff = user_angles[joint] - std_angle
            abs_diff = abs(diff)
            threshold = ANGLE_THRESHOLDS.get(joint, 20)
            is_ok = abs_diff <= threshold

            deviations[joint] = {
                'standard': std_angle,
                'current': user_angles[joint],
                'difference': diff,
                'abs_difference': abs_diff,
                'threshold': threshold,
                'is_correct': is_ok,
            }

            if not is_ok:
                name = JOINT_NAME_CN.get(joint, joint)
                if abs_diff > threshold * 1.5:
                    severity = "BAD"
                    severity_en = "major"
                else:
                    severity = "WARN"
                    severity_en = "minor"

                if diff > 0:
                    direction = "decrease"
                else:
                    direction = "increase"

                feedback.append({
                    'joint': joint,
                    'severity': severity,
                    'message': f"{name}: {severity_en} deviation, {direction} {abs_diff:.0f} deg",
                    'difference': diff,
                })
                total_score -= min(abs_diff / threshold * 20, 30)

        feedback.sort(key=lambda x: abs(x['difference']), reverse=True)

        return {
            'score': max(0.0, total_score),
            'pose_name': self.pose_name,
            'deviations': deviations,
            'feedback': feedback,
        }

    @staticmethod
    def get_correction_hints(deviations: Dict) -> List[str]:
        """生成英文纠正建议"""
        hints = []
        templates = {
            'elbow': ("Bend your arm more", "Straighten your arm a bit"),
            'knee': ("Bend your knee more", "Straighten your knee a bit"),
            'shoulder': ("Raise/open your arm more", "Lower your arm a bit"),
            'hip': ("Open your legs wider", "Close your legs a bit"),
        }
        for joint, d in deviations.items():
            if d['is_correct']:
                continue
            name = JOINT_NAME_CN.get(joint, joint)
            for key, (pos_msg, neg_msg) in templates.items():
                if key in joint:
                    msg = pos_msg if d['difference'] > 0 else neg_msg
                    hints.append(f"-> {name}: {msg}")
                    break
        return hints
