"""Yoga Tutor shared configuration."""

import os

# ==================== 摄像头 ====================
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# ==================== MediaPipe ====================
MODEL_COMPLEXITY = 1
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

# ==================== 1€ Filter ====================
FILTER_MIN_CUTOFF = 0.5
FILTER_BETA = 0.005
FILTER_D_CUTOFF = 1.0

# ==================== 静止检测 ====================
STILLNESS_THRESHOLD = 8.0
STILLNESS_DURATION = 1.2
STILLNESS_CHECK_POINTS = [
    11, 12, 13, 14, 15, 16,
    23, 24, 25, 26, 27, 28,
]

# ==================== 动作识别参数 ====================
RECOGNITION_MIN_SCORE = 50.0        # 最低识别分数阈值
RECOGNITION_STABLE_FRAMES = 15      # 需要连续稳定的帧数
RECOGNITION_CONFIDENCE_THRESHOLD = 70.0  # 高置信度阈值

# ==================== 关键点索引 ====================
LANDMARK_INDICES = {
    'nose': 0,
    'left_shoulder': 11, 'right_shoulder': 12,
    'left_elbow': 13, 'right_elbow': 14,
    'left_wrist': 15, 'right_wrist': 16,
    'left_hip': 23, 'right_hip': 24,
    'left_knee': 25, 'right_knee': 26,
    'left_ankle': 27, 'right_ankle': 28,
}

# ==================== 关节角度定义 ====================
ANGLE_DEFINITIONS = {
    'left_elbow': ('left_shoulder', 'left_elbow', 'left_wrist'),
    'right_elbow': ('right_shoulder', 'right_elbow', 'right_wrist'),
    'left_knee': ('left_hip', 'left_knee', 'left_ankle'),
    'right_knee': ('right_hip', 'right_knee', 'right_ankle'),
    'left_shoulder': ('left_elbow', 'left_shoulder', 'left_hip'),
    'right_shoulder': ('right_elbow', 'right_shoulder', 'right_hip'),
    'left_hip': ('left_shoulder', 'left_hip', 'left_knee'),
    'right_hip': ('right_shoulder', 'right_hip', 'right_knee'),
}

# ==================== 评分阈值（度） ====================
ANGLE_THRESHOLDS = {
    'left_elbow': 15,
    'right_elbow': 15,
    'left_knee': 20,
    'right_knee': 20,
    'left_shoulder': 20,
    'right_shoulder': 20,
    'left_hip': 25,
    'right_hip': 25,
}

# ==================== 关节名称 ====================
JOINT_NAME_CN = {
    'left_elbow': 'L.Elbow',
    'right_elbow': 'R.Elbow',
    'left_knee': 'L.Knee',
    'right_knee': 'R.Knee',
    'left_shoulder': 'L.Shoulder',
    'right_shoulder': 'R.Shoulder',
    'left_hip': 'L.Hip',
    'right_hip': 'R.Hip',
}

# ==================== 路径 ====================
# 始终相对于本文件定位，避免必须先 cd 到 src 才能运行。
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SRC_DIR.parent
STANDARD_POSES_DIR = str(SRC_DIR / "standard_poses")
STANDARD_IMAGES_DIR = str(SRC_DIR / "standard_images")

# ==================== 触觉硬件 ====================
HAPTIC_PORT = os.getenv("YOGA_HAPTIC_PORT", "COM9") or None
HAPTIC_BAUD = 115200
HAPTIC_RECONNECT_INTERVAL = 3.0
HAPTIC_KEEPALIVE_INTERVAL = 0.75
HAPTIC_DEBUG = False
HAPTIC_TRANSPORT = os.getenv("YOGA_HAPTIC_TRANSPORT", "serial")
