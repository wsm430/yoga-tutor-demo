"""腕带硬件接通测试：列出串口 -> 连接 ESP32 -> 逐个震动 M0-M3。

用法（在 src 目录下运行）：
    python test_wristband.py --list            # 只列出串口，找到 XIAO 的 COM 号
    python test_wristband.py --port COM9       # 自动依次震 M0..M3
    python test_wristband.py --port COM9 -i    # 交互模式：输入 0/1/2/3 单独震，a 全部，q 退出

协议与主程序一致：  "L:<马达>,<PWM> R:N\n"，停止为 "L:N R:N\n"。
"""

import argparse
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("缺少 pyserial，请先运行： pip install pyserial")
    sys.exit(1)

NAMES = {0: "M0 手腕下侧", 1: "M1 手腕左侧", 2: "M2 手腕上侧", 3: "M3 手腕右侧"}
STOP = "L:N R:N\n"


def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("没有发现任何串口。检查：数据线是否支持数据传输、驱动是否安装、XIAO 是否上电。")
    for p in ports:
        print(f"  {p.device:10s} {p.description}")
    return ports


def send(ser, cmd):
    ser.write(cmd.encode("ascii"))
    ser.flush()
    time.sleep(0.05)
    echo = ser.read(ser.in_waiting or 0).decode(errors="replace").strip()
    if echo:
        print(f"    固件回复: {echo}")


def buzz(ser, motor, pwm, seconds):
    print(f"-> 震动 {NAMES[motor]}  (PWM={pwm}, {seconds}s)")
    send(ser, f"L:{motor},{pwm} R:N\n")
    time.sleep(seconds)
    send(ser, STOP)


def main():
    ap = argparse.ArgumentParser(description="腕带 4 马达接通测试")
    ap.add_argument("--port", help="串口，如 COM9 或 /dev/ttyACM0")
    ap.add_argument("--list", action="store_true", help="只列出串口")
    ap.add_argument("--pwm", type=int, default=255, help="震动强度 0-255，默认 255")
    ap.add_argument("--seconds", type=float, default=1.5, help="每个马达震动秒数")
    ap.add_argument("-i", "--interactive", action="store_true", help="交互模式")
    args = ap.parse_args()

    print("可用串口：")
    list_ports()
    if args.list:
        return 0
    if not args.port:
        print("\n请用 --port 指定上面列出的 XIAO 串口，例如 --port COM9")
        return 1

    try:
        # 先关掉 DTR/RTS 再打开，避免 ESP32C3 被复位、USB 掉线
        ser = serial.Serial()
        ser.port = args.port
        ser.baudrate = 115200
        ser.timeout = 0.2
        ser.write_timeout = 0.5
        ser.dtr = False
        ser.rts = False
        ser.open()
    except Exception as e:
        print(f"打不开 {args.port}: {e}\n（串口可能被 Arduino 串口监视器或主程序占用，先关掉它们）")
        return 1

    print(f"\n已打开 {args.port}")
    time.sleep(0.5)
    boot = ser.read(ser.in_waiting or 0).decode(errors="replace").strip()
    if boot:
        print(f"    启动输出: {boot}")
    send(ser, STOP)

    try:
        if args.interactive:
            print("输入 0/1/2/3 震对应马达，a 依次全部，q 退出")
            while True:
                k = input("> ").strip().lower()
                if k == "q":
                    break
                if k == "a":
                    for m in range(4):
                        buzz(ser, m, args.pwm, args.seconds)
                        time.sleep(0.5)
                elif k in {"0", "1", "2", "3"}:
                    buzz(ser, int(k), args.pwm, args.seconds)
        else:
            for m in range(4):
                buzz(ser, m, args.pwm, args.seconds)
                time.sleep(0.8)
            print("\n完成。请记下哪几个马达震了、位置是否和名称一致。")
    finally:
        try:
            send(ser, STOP)
        finally:
            ser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
