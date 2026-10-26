# Yoga Tutor Warrior II 网页 MVP

## 本地打开

在 PowerShell 中进入 `web` 目录并运行：

```powershell
.\start-local.ps1
```

然后访问 <http://127.0.0.1:4173>。

该命令会启动 Python 本地服务。浏览器负责笔记本摄像头采集，Python 负责 MediaPipe、静止检测、Warrior II 标准图比较和左手环串口反馈。

默认串口为 `COM9`，可在启动前覆盖：

```powershell
$env:YOGA_HAPTIC_PORT = "COM6"
.\start-local.ps1
```

没有手环时可运行 `.\start-local.ps1 -Haptic none`，只验证视觉链路。`-Haptic ble` 已预留为下一阶段接口，目前会明确报错，避免误以为蓝牙已经接通。
