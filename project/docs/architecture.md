# 系统架构文档

## 模块概述

### 1. 姿态检测模块 (pose_detection.py)

**功能**: 使用 MediaPipe 检测人体 33 个关键点

**类**: `PoseDetector`

**主要方法**:
- `detect(frame)`: 返回 (关键点列表, 标注图像)
- `calculate_angle(landmarks, p1, p2, p3)`: 计算指定三点角度
- `calculate_all_angles(landmarks)`: 计算所有定义的关节角度

**配置参数**:
```python
MODEL_COMPLEXITY = 1          # 模型复杂度 0/1/2
MIN_DETECTION_CONFIDENCE = 0.5  # 检测置信度阈值
MIN_TRACKING_CONFIDENCE = 0.5    # 跟踪置信度阈值
```

### 2. 信号滤波模块 (one_euro_filter.py)

**功能**: 1€ Filter 自适应滤波，平滑关键点数据

**类**: `OneEuroFilter`, `MultiPointFilter`

**1€ Filter 算法原理**:
```
alpha = 1 / (1 + tau / dt)  # tau = 1 / (2 * pi * cutoff)
cutoff = min_cutoff + beta * |d_x|
x_filtered = alpha * x + (1 - alpha) * x_prev
```

**参数调优建议**:
- `min_cutoff`: 越小越平滑，典型值 0.5-1.0
- `beta`: 对速度变化的敏感度，典型值 0.005-0.1

### 3. 静止检测模块 (stillness_detector.py)

**功能**: 检测用户是否保持姿势静止，用于触发评估

**类**: `StillnessDetector`

**工作流程**:
1. 记录每帧关键点位置
2. 计算与上一帧的平均位移
3. 位移 < 阈值持续 N 秒 → 判定静止
4. 移动量 > 阈值 → 重置计时

**配置参数**:
```python
STILLNESS_THRESHOLD = 8.0    # 像素，低于此值认为静止
STILLNESS_DURATION = 1.2     # 秒，需保持静止的时长
```

### 4. 姿势对比模块 (pose_comparator.py)

**功能**: 将用户姿势与标准姿势进行量化对比

**类**: `PoseComparator`

**评分算法**:
```
总分 = 100 - Σ(偏差角度 / 阈值 * 20)
每个关节单独判定，超过阈值 1.5 倍标记为严重
```

**输出格式**:
```python
{
    'score': 85.5,                    # 总分 0-100
    'pose_name': 'warrior_1',         # 姿势名称
    'deviations': {                    # 每个关节详情
        'left_elbow': {
            'standard': 150.0,
            'current': 145.0,
            'difference': -5.0,
            'threshold': 15,
            'is_correct': True
        }
    },
    'feedback': [                      # 需调整的关节
        {
            'joint': 'left_knee',
            'severity': 'WARN',
            'message': 'L.Knee: minor deviation, increase 12 deg'
        }
    ]
}
```

### 5. 动作识别模块 (action_recognizer.py)

**功能**: 自动识别用户当前做的瑜伽动作

**类**: `ActionRecognizer`

**识别算法**:
1. 计算与所有标准动作的角度相似度
2. 相似度 = 匹配率(60%) + 平均关节得分(40%)
3. 连续 15 帧识别为同一动作 → 确认识别

**稳定性要求**:
- 至少 80% 的连续帧识别相同动作
- 分数达到 RECOGNITION_MIN_SCORE (50)

### 6. DTW 匹配模块 (dtw_matcher.py)

**功能**: 动态时间规整，用于动作序列匹配

**算法**: Sakoe-Chiba 带约束的 DTW

**参数**:
```python
DTW_WINDOW_RATIO = 0.2  # 窗口占序列长度比例
```

**用途**:
- 评估完整动作执行的质量
- 考虑动作的速度变化
- 允许时间偏移对齐

### 7. 触觉反馈模块 (haptic_feedback.py)

**功能**: 将姿势偏差映射为马达震动指令

**类**: `HapticMapper`

**马达映射逻辑**:

| 关节类型 | 偏差方向 | 马达 | 提示 |
|---------|---------|-----|------|
| elbow/knee | 太大（需减小） | INNER | 弯一点 |
| elbow/knee | 太小（需增大） | OUTER | 伸直 |
| shoulder/hip | 太大（需减小） | DOWN | 放低 |
| shoulder/hip | 太小（需增大） | UP | 抬高 |

**强度计算**:
```
偏差 >= 2x阈值 → PWM 255
偏差 >= 1.5x阈值 → PWM 200
偏差 >= 1x阈值 → PWM 150
否则 → PWM 100
```

### 8. ESP32 通信模块 (esp32_controller.py)

**功能**: 管理 PC 与 ESP32 间的串口通信

**类**: `ESP32Controller`

**特性**:
- 自动端口扫描（识别 CP210x, CH340, Arduino 等）
- 自动重连机制
- 静默降级（无硬件时程序继续运行）
- 指令去重（减少串口流量）

**通信格式**:
```
L:0,255;2,128 R:3,180\n   # 左:M0=255,M2=128 右:M3=180
L:N R:N\n                 # 全部停止
```

## 数据流

```
摄像头帧
    ↓
姿态检测 (MediaPipe)
    ↓
1€ Filter 平滑
    ↓
[自动模式] → 动作识别
    ↓
静止检测 (等待用户静止)
    ↓
角度计算 (所有关节)
    ↓
姿势对比 (计算偏差和评分)
    ↓
触觉映射 (生成马达指令)
    ↓
ESP32 发送
    ↓
手环震动
```

## 配置管理

所有配置集中在 `config.py`：

- **摄像头**: 分辨率、索引
- **MediaPipe**: 模型复杂度、置信度阈值
- **滤波**: 1€ Filter 参数
- **静止检测**: 阈值、持续时间
- **姿态计算**: 关键点索引、关节三元组、评分阈值
- **路径**: 标准姿势目录、图片目录