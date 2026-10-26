// 腕带固件（XIAO ESP32C3）
// 串口协议与 Python 端一致：  "L:0,255;2,128 R:N\n"   停止： "L:N R:N\n"
// 只用 L 部分驱动本腕带的 M0-M3。
// 接线：D0/GPIO2->IN1->M0  D1/GPIO3->IN2->M1  D2/GPIO4->IN3->M2  D3/GPIO5->IN4->M3
// Arduino IDE 设置：开发板选 "XIAO_ESP32C3"，Tools -> USB CDC On Boot -> Enabled

const int MOTOR_PINS[4] = {2, 3, 4, 5};
const unsigned long TIMEOUT_MS = 2000;  // 2 秒没收到指令就自动停止

String line;
unsigned long lastCmd = 0;

void setAll(int pwm) {
  for (int i = 0; i < 4; i++) analogWrite(MOTOR_PINS[i], pwm);
}

void handleLine(const String &s) {
  int l = s.indexOf("L:");
  if (l < 0) return;
  int end = s.indexOf(' ', l);
  String part = (end < 0) ? s.substring(l + 2) : s.substring(l + 2, end);
  part.trim();

  int pwm[4] = {0, 0, 0, 0};
  if (part != "N") {
    int start = 0;
    while (start < (int)part.length()) {
      int semi = part.indexOf(';', start);
      String item = (semi < 0) ? part.substring(start) : part.substring(start, semi);
      int comma = item.indexOf(',');
      if (comma > 0) {
        int m = item.substring(0, comma).toInt();
        int p = constrain(item.substring(comma + 1).toInt(), 0, 255);
        if (m >= 0 && m < 4) pwm[m] = p;
      }
      if (semi < 0) break;
      start = semi + 1;
    }
  }
  for (int i = 0; i < 4; i++) analogWrite(MOTOR_PINS[i], pwm[i]);
  lastCmd = millis();
  Serial.printf("OK M0=%d M1=%d M2=%d M3=%d\n", pwm[0], pwm[1], pwm[2], pwm[3]);
}

void setup() {
  // 第一件事：所有马达引脚拉低，避免上电乱震
  for (int i = 0; i < 4; i++) {
    pinMode(MOTOR_PINS[i], OUTPUT);
    digitalWrite(MOTOR_PINS[i], LOW);
  }
  Serial.begin(115200);
  delay(300);
  Serial.println("WRISTBAND READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handleLine(line);
      line = "";
    } else if (c != '\r' && line.length() < 64) {
      line += c;
    }
  }
  if (lastCmd && millis() - lastCmd > TIMEOUT_MS) {
    setAll(0);
    lastCmd = 0;
  }
  delay(2);
}
