# 左手环蓝牙迁移方案

## 当前边界

Warrior II MVP 默认走已验证的 USB 串口协议：

```text
L:2,150 R:N
L:N R:N
```

`src/haptic_transport.py` 已把传输层从姿势判断逻辑中隔离。当前 `serial` 和 `none` 可用，`ble` 会明确报错，避免把未验证链路当成完成品。

## 建议的 BLE 协议

- ESP32-C3 提供一个自定义 BLE GATT Service。
- 提供一个可写 Characteristic，内容继续沿用 UTF-8/ASCII 串口命令，不改上层映射。
- 可选增加一个可读/通知 Characteristic，回报电量、固件版本和最后命令状态。
- 保留固件 2 秒无命令自动停震，并由电脑端每 0.75 秒发送一次正在执行的命令。
- BLE 断连回调必须立即关闭全部电机。

## 实施顺序

1. 在 `firmware/yoga_bands` 增加 BLE GATT 收包，复用现有 `parseCommand()`。
2. Python 增加基于 `bleak` 的 `BleHapticTransport`，实现与串口相同的四个方法。
3. 通过设备名称或固定 Service UUID 发现手环，不依赖动态 COM 口。
4. 分层验证 `up/down/left/right/all/stop`，再接入网页闭环。
5. 测试断连停震、自动重连、持续震动保活和 20 分钟运行稳定性。

预计在 USB MVP 实机闭环通过后，蓝牙改造与测试需要 1 到 2 个工作日。
