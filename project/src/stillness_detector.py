"""
stillness_detector.py
静止检测器 —— 判断用户是否已经保持姿势不动
当用户静止超过设定时长后，触发对比评估
"""

import time
import numpy as np
from config import (
    STILLNESS_THRESHOLD,
    STILLNESS_DURATION,
    STILLNESS_CHECK_POINTS,
)


class StillnessDetector:
    """
    工作原理：
    1. 每帧记录关键点位置
    2. 计算与上一帧的平均位移
    3. 如果连续 N 秒位移都低于阈值 → 判定为"静止"
    4. 一旦用户大幅移动 → 重新计时
    """

    def __init__(self, threshold=STILLNESS_THRESHOLD,
                 duration=STILLNESS_DURATION,
                 check_indices=None):
        """
        参数:
            threshold:     平均移动量阈值（像素）
            duration:      需要持续静止的秒数
            check_indices: 用于判断的关键点索引列表
        """
        self.threshold = threshold
        self.duration = duration
        self.check_indices = check_indices or STILLNESS_CHECK_POINTS

        self._prev_points = None
        self._still_start = None
        self._is_still = False
        self._movement = 0.0         # 当前帧移动量
        self._still_progress = 0.0   # 静止进度 0.0~1.0

    def update(self, landmarks):
        """
        更新检测状态

        参数:
            landmarks: 关键点列表 [{'x','y',...}, ...]
        返回:
            is_ready: 是否已静止足够时间，可以开始对比
        """
        if landmarks is None:
            self._reset()
            return False

        # 提取检测用的关键点坐标
        current = np.array([
            [landmarks[i]['x'], landmarks[i]['y']]
            for i in self.check_indices
            if i < len(landmarks)
        ])

        if self._prev_points is None or len(current) != len(self._prev_points):
            self._prev_points = current
            self._still_start = time.time()
            return False

        # 计算平均位移
        self._movement = float(np.mean(np.linalg.norm(current - self._prev_points, axis=1)))
        self._prev_points = current

        now = time.time()

        if self._movement < self.threshold:
            # 正在静止
            if self._still_start is None:
                self._still_start = now

            elapsed = now - self._still_start
            self._still_progress = min(elapsed / self.duration, 1.0)
            self._is_still = elapsed >= self.duration
        else:
            # 在移动，重置
            self._still_start = now
            self._still_progress = 0.0
            self._is_still = False

        return self._is_still

    def _reset(self):
        """私有方法：内部重置"""
        self._prev_points = None
        self._still_start = None
        self._is_still = False
        self._movement = 0.0
        self._still_progress = 0.0

    # ✅ 添加公开的 reset() 方法
    def reset(self):
        """
        公开方法：重置检测器状态
        用于在识别到新动作或用户操作时调用
        """
        self._reset()

    @property
    def is_still(self):
        return self._is_still

    @property
    def progress(self):
        """静止进度 0.0 ~ 1.0"""
        return self._still_progress

    @property
    def movement(self):
        """当前帧平均移动量（像素）"""
        return self._movement

    @property
    def status_text(self):
        """返回当前状态描述"""
        if self._is_still:
            return "HOLD — Comparing..."
        elif self._still_progress > 0:
            pct = int(self._still_progress * 100)
            return f"Hold still... {pct}%"
        else:
            return "Move into pose"