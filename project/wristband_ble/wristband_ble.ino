// 腕带固件 v2（XIAO ESP32C3）：USB 串口 + 蓝牙（BLE）都能控制
// 协议与 Python 端一致： "L:0,255;2,128 R:N\n"   停止： "L:N R:N\n"
// 蓝牙名 "YogaBand"，使用 Nordic UART 服务（NUS）。
// 蓝牙连上后，四个马达一起震 1 秒作为提示。
// 接线：D0/GPIO2->M0  D1/GPIO3->M1  D2/GPIO4->M2  D3/GPIO5->M3
// Arduino IDE：开发板 XIAO_ESP32C3；USB CDC On Boot = Enabled；
//              Partition Scheme 默认即可（若提示空间不够，选 "Huge APP"）

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLE2902.h>

#define DEVICE_NAME "YogaBand"
#define NUS_SERVICE "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX      "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  // 电脑 -> 腕带
#define NUS_TX      "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  // 腕带 -> 电脑

const int MOTOR_PINS[4] = {2, 3, 4, 5};
const unsigned long TIMEOUT_MS = 2000;     // 2 秒没收到指令就自动停止
const unsigned long HELLO_MS = 1000;       // 蓝牙连上时全震时长

String usbLine, bleLine;
unsigned long lastCmd = 0;
volatile bool bleConnected = false;
volatile bool helloPending = false;
volatile bool needAdvertise = false;
unsigned long helloUntil = 0;
BLECharacteristic *txChar = nullptr;
BLEServer *server = nullptr;

void writeMotors(const int pwm[4]) {
  for (int i = 0; i < 4; i++) analogWrite(MOTOR_PINS[i], pwm[i]);
}

void setAll(int p) {
  int pwm[4] = {p, p, p, p};
  writeMotors(pwm);
}

void reply(const String &msg) {
  Serial.println(msg);
  if (bleConnected && txChar) {
    txChar->setValue((uint8_t *)msg.c_str(), msg.length());
    txChar->notify();
  }
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
  helloUntil = 0;  // 收到正式指令就结束开机提示
  writeMotors(pwm);
  lastCmd = millis();
  reply("OK M0=" + String(pwm[0]) + " M1=" + String(pwm[1]) +
        " M2=" + String(pwm[2]) + " M3=" + String(pwm[3]));
}

void feed(String &buf, char c) {
  if (c == '\n') {
    handleLine(buf);
    buf = "";
  } else if (c != '\r' && buf.length() < 64) {
    buf += c;
  }
}

class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer *) override {
    bleConnected = true;
    helloPending = true;
  }
  void onDisconnect(BLEServer *) override {
    bleConnected = false;
    needAdvertise = true;
  }
};

String pendingBle;
portMUX_TYPE bleMux = portMUX_INITIALIZER_UNLOCKED;

class RxCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String v = String(c->getValue().c_str());
    portENTER_CRITICAL(&bleMux);
    pendingBle += v;
    portEXIT_CRITICAL(&bleMux);
  }
};

void setup() {
  // 第一件事：所有马达引脚拉低，避免上电乱震
  for (int i = 0; i < 4; i++) {
    pinMode(MOTOR_PINS[i], OUTPUT);
    digitalWrite(MOTOR_PINS[i], LOW);
  }
  Serial.begin(115200);

  BLEDevice::init(DEVICE_NAME);
  server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());
  BLEService *svc = server->createService(NUS_SERVICE);
  txChar = svc->createCharacteristic(NUS_TX, BLECharacteristic::PROPERTY_NOTIFY);
  txChar->addDescriptor(new BLE2902());
  BLECharacteristic *rx = svc->createCharacteristic(
      NUS_RX, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rx->setCallbacks(new RxCB());
  svc->start();
  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(NUS_SERVICE);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();

  Serial.println("WRISTBAND READY (USB + BLE \"" DEVICE_NAME "\")");
}

void loop() {
  // USB 串口
  while (Serial.available()) feed(usbLine, (char)Serial.read());

  // 蓝牙收到的数据
  if (pendingBle.length()) {
    portENTER_CRITICAL(&bleMux);
    String chunk = pendingBle;
    pendingBle = "";
    portEXIT_CRITICAL(&bleMux);
    for (unsigned i = 0; i < chunk.length(); i++) feed(bleLine, chunk[i]);
  }

  // 蓝牙刚连上：四个马达一起震 1 秒
  if (helloPending) {
    helloPending = false;
    setAll(255);
    helloUntil = millis() + HELLO_MS;
    Serial.println("BLE connected");
  }
  if (helloUntil && (long)(millis() - helloUntil) >= 0) {
    setAll(0);
    helloUntil = 0;
  }

  // 蓝牙断开：停马达并重新广播
  if (needAdvertise) {
    needAdvertise = false;
    setAll(0);
    lastCmd = 0;
    delay(200);
    BLEDevice::startAdvertising();
    Serial.println("BLE disconnected, advertising again");
  }

  // 超时保护
  if (lastCmd && millis() - lastCmd > TIMEOUT_MS) {
    setAll(0);
    lastCmd = 0;
  }
  delay(2);
}
