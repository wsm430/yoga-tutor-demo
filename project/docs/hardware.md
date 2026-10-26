# 硬件通信协议文档

## 系统概述

当前开发板：**Seeed Studio XIAO ESP32C3**。现有实物左手环使用 D0～D3：

| 马达 | XIAO 丝印 | ESP32-C3 GPIO |
|---|---|---|
| M0 / UP | D0 | GPIO2 |
| M1 / DOWN | D1 | GPIO3 |
| M2 / INNER | D2 | GPIO4 |
| M3 / OUTER | D3 | GPIO5 |

注意：GPIO2 是 ESP32-C3 的启动配置引脚。后续硬件版本应把 M0/IN1 改接到非启动配置引脚（例如 D4/GPIO6），避免驱动输入影响启动和烧录。

本项目的触觉反馈系统由以下硬件组成：

1. **PC 端**: 运行 YogaTutor 软件
2. **ESP32**: 接收 PC 指令，控制手环马达
3. **手环设备**: 每个手环包含 4 个振动马达

## 通信架构

```
┌──────────────┐      USB/Serial       ┌──────────────┐      GPIO      ┌──────────────┐
│   PC (Python) │ ───────────────────▶  │    ESP32     │ ─────────────▶  │ Hand Band    │
│              │    L:0,255;2,128\n     │              │   PWM Signals  │  (4 Motors)  │
└──────────────┘                       └──────────────┘                └──────────────┘
```

## 串口配置

| 参数 | 值 |
|-----|-----|
| 波特率 | 115200 |
| 数据位 | 8 |
| 停止位 | 1 |
| 校验位 | 无 |
| 超时 | 0.5 秒 |

## 指令协议

### 指令格式

```
L:<left_motors> R:<right_motors>\n
```

### 左/右手电机格式

| 格式 | 含义 | 示例 |
|-----|------|------|
| `N` | 无动作（停止所有电机） | `L:N` |
| `<idx>,<pwm>;<idx>,<pwm>` | 多电机同时控制 | `L:0,255;2,128` |

### 指令示例

```bash
# 左手上: M0=255  右手内+外: M2=128, M3=200
L:0,255 R:2,128;3,200

# 停止所有电机
L:N R:N

# 只控制左手
L:1,150 R:N

# 两手各两个电机（对角线引导）
L:0,255;2,128 R:1,255;3,128
```

## 马达索引定义

每个手环（从用户视角，手臂前伸、掌心朝上）:

```
    ┌─────────┐
    │   M0    │  ←  UP (上)
    │  M3 M2  │  ←  OUTER LEFT, INNER RIGHT
    │   M1    │  ←  DOWN (下)
    └─────────┘
```

| 索引 | 名称 | 功能 | 引导方向 |
|-----|------|------|---------|
| 0 | UP | 提示向上 | 手/腿抬高 |
| 1 | DOWN | 提示向下 | 手/腿放低 |
| 2 | INNER | 提示向内 | 关节弯曲（靠近身体） |
| 3 | OUTER | 提示向外 | 关节伸展（远离身体） |

## PWM 强度等级

| 等级 | PWM 值 | 使用场景 |
|-----|--------|---------|
| 强 | 255 | 严重偏差 (>2x 阈值) |
| 中高 | 200 | 较大偏差 (1.5x-2x 阈值) |
| 中 | 150 | 中等偏差 (1x-1.5x 阈值) |
| 弱 | 100 | 轻微偏差 (<1x 阈值) |

## ESP32 端口自动识别

系统自动识别 ESP32 串口，支持以下标识：

- VID/PID: `CP210x`, `CH340`, `FTDI`
- 描述关键词: `Arduino`, `ESP32`, `USB Serial`

扫描优先级:
1. 匹配上述关键词的端口
2. 返回第一个可用端口

## 指令去重机制

为减少串口流量，当连续帧发送相同指令时，自动跳过重复发送：

```python
if cmd_str != self._last_send:
    self._write_raw(cmd_str)
    self._last_send = cmd_str
```

## 错误处理

| 情况 | 处理方式 |
|-----|---------|
| 未找到 ESP32 | 静默降级，程序继续运行，无触觉反馈 |
| 串口断开 | 自动尝试重连 |
| 发送失败 | 标记为断开状态，停止发送 |
| pyserial 未安装 | 提示安装，跳过触觉功能 |

## 固件要求

ESP32 固件需要支持：
- 解析格式: `L:<motors> R:<motors>\n`
- 响应格式: 任意（忽略）

推荐固件框架：
```cpp
// Arduino/ESP-IDF 示例伪代码
void processCommand(String cmd) {
    // 解析 L:N R:0,255;2,128 格式
    // 设置对应 GPIO PWM 输出
}
```

## 测试方法

> 当前 `yoga_bands.ino` 只启用了左手环的 GPIO 4~7。PC 协议已保留左右手字段，接入第二只手环前必须先为右手环确定 4 个不冲突的 GPIO，并扩展固件；不要直接照搬左手引脚。

### 1. 串口连接测试

```python
from esp32_controller import ESP32Controller

esp = ESP32Controller()
if esp.connect():
    print("ESP32 connected!")
    esp.send_stop()
    esp.disconnect()
```

### 2. 马达指令测试

```python
from haptic_feedback import HapticMapper

# 测试所有马达
left = [(0, 255)]  # 手上
right = [(1, 255)]  # 手下
cmd = HapticMapper.to_command(left, right)
print(cmd)  # L:0,255 R:1,255
```

### 3. 完整触觉反馈测试

```python
from esp32_controller import ESP32Controller
from haptic_feedback import HapticMapper

esp = ESP32Controller()
esp.connect()

# 模拟检测结果
mock_result = {
    'deviations': {
        'left_elbow': {'is_correct': False, 'difference': 20, 'abs_difference': 20, 'threshold': 15}
    },
    'score': 70
}

left, right = HapticMapper.translate(mock_result)
esp.send_motor_command(left, right)

import time
time.sleep(2)
esp.send_stop()
esp.disconnect()
```

## 调试技巧

1. **串口监视器**: 使用 Arduino IDE 或 `screen /dev/ttyUSB0 115200` 查看 ESP32 输出
2. **Python 调试**: 在 `esp32_controller.py` 中添加打印语句
3. **信号检测**: 用万用表测量 GPIO 引脚电压
4. **马达测试**: 依次控制每个马达，确认位置映射正确
