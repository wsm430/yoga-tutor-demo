# API 参考文档

## 配置模块 (config.py)

### 常量

```python
# 摄像头配置
CAMERA_INDEX = 0                    # 摄像头索引
CAMERA_WIDTH = 1280                 # 帧宽度
CAMERA_HEIGHT = 720                 # 帧高度

# MediaPipe 配置
MODEL_COMPLEXITY = 1                # 模型复杂度 (0, 1, 2)
MIN_DETECTION_CONFIDENCE = 0.5      # 最小检测置信度
MIN_TRACKING_CONFIDENCE = 0.5       # 最小跟踪置信度

# 1€ Filter 配置
FILTER_MIN_CUTOFF = 0.5             # 最小截止频率
FILTER_BETA = 0.005                 # 速度增益
FILTER_D_CUTOFF = 1.0               # 导数截止频率

# 静止检测配置
STILLNESS_THRESHOLD = 8.0           # 移动量阈值（像素）
STILLNESS_DURATION = 1.2            # 需保持静止的时长（秒）
STILLNESS_CHECK_POINTS = [...]      # 用于判断的关键点索引

# 动作识别配置
RECOGNITION_MIN_SCORE = 50.0        # 最低识别分数
RECOGNITION_STABLE_FRAMES = 15      # 需连续的稳定帧数
RECOGNITION_CONFIDENCE_THRESHOLD = 70.0  # 高置信度阈值
```

### 关键点索引映射

```python
LANDMARK_INDICES = {
    'nose': 0,
    'left_shoulder': 11, 'right_shoulder': 12,
    'left_elbow': 13, 'right_elbow': 14,
    'left_wrist': 15, 'right_wrist': 16,
    'left_hip': 23, 'right_hip': 24,
    'left_knee': 25, 'right_knee': 26,
    'left_ankle': 27, 'right_ankle': 28,
}
```

### 关节角度定义

```python
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
```

### 评分阈值

```python
ANGLE_THRESHOLDS = {
    'left_elbow': 15, 'right_elbow': 15,
    'left_knee': 20, 'right_knee': 20,
    'left_shoulder': 20, 'right_shoulder': 20,
    'left_hip': 25, 'right_hip': 25,
}
```

---

## 姿态检测模块 (pose_detection.py)

### class PoseDetector

#### `__init__(static_mode=False)`

创建姿态检测器。

**参数**:
- `static_mode`: `True`=图片模式(精度高), `False`=视频模式(速度快)

**示例**:
```python
# 实时检测
detector = PoseDetector(static_mode=False)

# 高精度静态检测
static_detector = PoseDetector(static_mode=True)
```

#### `detect(frame) -> (landmarks, annotated)`

检测图像中的人体姿态。

**参数**:
- `frame`: OpenCV BGR 图像

**返回**:
- `landmarks`: 关键点列表，每个为 `{'x', 'y', 'z', 'visibility'}`，未检测到返回 `None`
- `annotated`: 带姿态标注的图像

**示例**:
```python
landmarks, annotated = detector.detect(frame)
if landmarks:
    print(f"检测到 {len(landmarks)} 个关键点")
```

#### `calculate_angle(landmarks, p1_name, p2_name, p3_name) -> float`

计算指定三点形成的角度，顶点为 p2。

**参数**:
- `landmarks`: 关键点列表
- `p1_name`: 第一个点名称（如 `'left_shoulder'`）
- `p2_name`: 顶点名称
- `p3_name`: 第三个点名称

**返回**: 角度值（度），参数无效返回 `None`

**示例**:
```python
elbow_angle = detector.calculate_angle(
    landmarks,
    'left_shoulder', 'left_elbow', 'left_wrist'
)
```

#### `calculate_all_angles(landmarks) -> Dict[str, float]`

计算所有定义的关节角度。

**返回**: `{'left_elbow': 150.0, 'right_knee': 165.0, ...}`

---

## 角度工具模块 (angle_utils.py)

### `calculate_angle(a, b, c) -> float`

计算由三点 a、b、c 形成的夹角，b 为顶点。

**参数**:
- `a, b, c`: `(x, y)` 元组

**返回**: 角度（度）

### `calculate_multiple_angles(points, triplets) -> List[float]`

批量计算多个关节角度。

**参数**:
- `points`: `[(x, y), ...]` 关键点坐标列表
- `triplets`: `[(idx1, idx2, idx3), ...]` 三元组列表

**返回**: 角度列表

---

## 1€ 滤波模块 (one_euro_filter.py)

### class OneEuroFilter

自适应低通滤波器，适用于实时滤波。

**示例**:
```python
filter = OneEuroFilter(min_cutoff=0.5, beta=0.005)
stable_value = filter(noisy_value, timestamp)
```

### class MultiPointFilter

多关键点同时滤波。

**示例**:
```python
mp_filter = MultiPointFilter(num_points=33)
filtered = mp_filter.filter_landmarks(landmarks)
```

---

## 静止检测模块 (stillness_detector.py)

### class StillnessDetector

#### `__init__(threshold=8.0, duration=1.2, check_indices=None)`

**参数**:
- `threshold`: 移动量阈值（像素）
- `duration`: 需保持静止的时长（秒）
- `check_indices`: 检测用的关键点索引列表

#### `update(landmarks) -> bool`

更新检测状态。

**返回**: `True` 表示用户已静止足够时间

#### `reset()`

重置检测器状态

### 属性

```python
stillness.is_still        # 是否静止
stillness.progress        # 静止进度 0.0~1.0
stillness.movement        # 当前帧平均移动量
```

---

## 姿势对比模块 (pose_comparator.py)

### class PoseComparator

#### `__init__(standard_pose_path)`

加载标准姿势数据。

**参数**:
- `standard_pose_path`: 标准姿势 JSON 文件路径

#### `compare(user_angles) -> Dict`

对比用户角度与标准姿势。

**参数**:
- `user_angles`: `{'left_elbow': 145.0, ...}`

**返回**:
```python
{
    'score': 85.5,
    'pose_name': 'warrior_1',
    'deviations': {...},
    'feedback': [...]
}
```

### `get_correction_hints(deviations) -> List[str]`

生成英文纠正建议。

---

## 动作识别模块 (action_recognizer.py)

### class ActionRecognizer

#### `__init__(pose_dir='standard_poses')`

**参数**:
- `pose_dir`: 标准姿势目录

#### `recognize(user_angles) -> (pose_name, confidence, match_details)`

识别当前动作。

**参数**:
- `user_angles`: 用户当前关节角度

**返回**:
- `pose_name`: 识别的动作名称（None 表示无法识别）
- `confidence`: 置信度 0-100
- `match_details`: 匹配详情

#### `reset()`

重置识别器

#### `get_status() -> Dict`

获取当前识别状态。

---

## DTW 匹配模块 (dtw_matcher.py)

### `dtw_distance(seq_user, seq_standard, window_ratio=0.2)`

计算两个序列的 DTW 距离。

**参数**:
- `seq_user`: 用户角度序列
- `seq_standard`: 标准角度序列
- `window_ratio`: Sakoe-Chiba 窗口比例

**返回**: `(normalized_distance, warp_path)`

### `dtw_score(seq_user, seq_standard, max_dist=50.0)`

将 DTW 距离转换为 0-100 分。

---

## 触觉反馈模块 (haptic_feedback.py)

### class HapticMapper

#### `translate(result) -> (left_motors, right_motors)`

将对比结果转换为马达指令。

**参数**:
- `result`: `PoseComparator.compare()` 的返回值

**返回**: `([(motor_idx, pwm), ...], [(motor_idx, pwm), ...])`

#### `to_command(left_motors, right_motors) -> str`

格式化为串口指令字符串。

**返回**: `'L:0,255;2,128 R:3,180\n'`

### 马达常量

```python
HapticMapper.DOWN = 0  # 手腕下侧
HapticMapper.LEFT = 1  # 手腕左侧
HapticMapper.UP = 2    # 手腕上侧
HapticMapper.RIGHT = 3 # 手腕右侧
HapticMapper.INNER = HapticMapper.LEFT
HapticMapper.OUTER = HapticMapper.RIGHT
```

---

## ESP32 通信模块 (esp32_controller.py)

### class ESP32Controller

#### `__init__(port=None, baud=115200)`

**参数**:
- `port`: 串口名称（如 `'COM3'`），None 表示自动扫描
- `baud`: 波特率

#### `connect() -> bool`

连接到 ESP32。

**返回**: 连接是否成功

#### `send_motor_command(left_motors, right_motors)`

发送马达指令。

#### `send_stop()`

停止所有马达。

#### `disconnect()`

断开连接。

### 属性

```python
esp32.connected  # 是否已连接
```

---

## 标准姿势提取模块 (standard_pose_extractor.py)

### class StandardPoseExtractor

#### `extract_from_image(image_path, output_json, pose_name) -> bool`

从单张图片提取姿势数据。

**参数**:
- `image_path`: 图片路径
- `output_json`: 输出 JSON 路径
- `pose_name`: 姿势名称

#### `extract_all_images(image_dir=None, output_dir=None)`

批量从图片目录提取。

**图片命名规则**: `pose_name.jpg` → 自动命名为 pose_name

#### `extract_from_video(video_path, output_json, pose_name) -> bool`

从视频文件提取。

---

## 统一主程序 (unified_main.py)

### class UnifiedYogaTutor

#### `__init__(auto_mode=True, manual_pose_path=None)`

**参数**:
- `auto_mode`: `True`=自动识别模式, `False`=手动选择模式
- `manual_pose_path`: 手动模式下的标准动作路径

#### `run()`

启动主循环。

---

## 标准姿势 JSON 格式

```json
{
    "pose_name": "warrior_1",
    "source": "image",
    "source_file": "warrior_1.jpg",
    "image_size": [1280, 720],
    "total_frames": 1,
    "average_pose": {
        "landmarks": [
            {"x": 0.5, "y": 0.3, "z": 0, "visibility": 0.9}
        ],
        "angles": {
            "left_elbow": 150.0,
            "right_knee": 165.0
        }
    },
    "frame_sequence": [...]
}
```
