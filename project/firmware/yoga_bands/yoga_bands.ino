/*
 * yoga_bands.ino
 * Seeed Studio XIAO ESP32C3 haptic wrist band firmware.
 *
 * Current physical layout:
 *   M0 = wrist bottom  -> XIAO D0 / GPIO2
 *   M1 = wrist left    -> XIAO D1 / GPIO3
 *   M2 = wrist top     -> XIAO D2 / GPIO4
 *   M3 = wrist right   -> XIAO D3 / GPIO5
 *
 * Serial protocol:
 *   L:idx,pwm;idx,pwm\n
 *   L:N = stop all motors
 *
 * Index map:
 *   0=DOWN, 1=LEFT, 2=UP, 3=RIGHT
 *
 * pwm is currently used as digital output:
 *   pwm > 128 = ON
 *   pwm <= 128 = OFF
 */

#define MOTOR_DOWN  2  // M0, XIAO D0 / GPIO2
#define MOTOR_LEFT  3  // M1, XIAO D1 / GPIO3
#define MOTOR_UP    4  // M2, XIAO D2 / GPIO4
#define MOTOR_RIGHT 5  // M3, XIAO D3 / GPIO5

#define VERSION "1.3"
#define BAUD 115200
#define TIMEOUT_MS 2000
#define BUF_SIZE 128

unsigned long last_cmd_time = 0;
bool motors_running = false;

const int MOTOR_PINS[] = {
  MOTOR_DOWN,
  MOTOR_LEFT,
  MOTOR_UP,
  MOTOR_RIGHT,
};
const int MOTOR_COUNT = 4;

void setup() {
  Serial.begin(BAUD);
  Serial.setTimeout(50);

  for (int i = 0; i < MOTOR_COUNT; i++) {
    pinMode(MOTOR_PINS[i], OUTPUT);
    digitalWrite(MOTOR_PINS[i], LOW);
  }

  Serial.println("OK");
  Serial.println("Yoga Bands v" VERSION " Ready");
}

void loop() {
  if (Serial.available()) {
    char buf[BUF_SIZE];
    int len = Serial.readBytesUntil('\n', buf, BUF_SIZE - 1);
    buf[len] = '\0';

    String cmd = String(buf);
    cmd.trim();

    if (cmd.length() > 0) {
      processCommand(cmd);
      last_cmd_time = millis();
      motors_running = commandHasActiveMotor(cmd);
      Serial.println("OK");
    }
  }

  if (motors_running && (millis() - last_cmd_time > TIMEOUT_MS)) {
    stopAllMotors();
    motors_running = false;
    Serial.println("AUTO_STOP");
  }
}

void processCommand(const String &cmd) {
  int l_pos = cmd.indexOf("L:");
  if (l_pos < 0) {
    return;
  }

  int l_end = cmd.indexOf(' ', l_pos);
  if (l_end < 0) {
    l_end = cmd.length();
  }

  String l_part = cmd.substring(l_pos + 2, l_end);
  l_part.trim();
  setGroup(MOTOR_PINS, MOTOR_COUNT, l_part);
}

bool commandHasActiveMotor(const String &cmd) {
  int l_pos = cmd.indexOf("L:");
  if (l_pos < 0) {
    return false;
  }

  int l_end = cmd.indexOf(' ', l_pos);
  if (l_end < 0) {
    l_end = cmd.length();
  }

  String l_data = cmd.substring(l_pos + 2, l_end);
  l_data.trim();
  return l_data != "N";
}

void setGroup(const int pins[], int count, const String &data) {
  stopAllMotors();

  if (data == "N") {
    return;
  }

  int start = 0;
  while (start < (int)data.length()) {
    int semi = data.indexOf(';', start);
    if (semi < 0) {
      semi = data.length();
    }

    String seg = data.substring(start, semi);
    int comma = seg.indexOf(',');

    if (comma >= 0) {
      int idx = seg.substring(0, comma).toInt();
      int pwm = seg.substring(comma + 1).toInt();

      if (idx >= 0 && idx < count) {
        digitalWrite(pins[idx], pwm > 128 ? HIGH : LOW);
      }
    }

    start = semi + 1;
  }
}

void stopAllMotors() {
  for (int i = 0; i < MOTOR_COUNT; i++) {
    digitalWrite(MOTOR_PINS[i], LOW);
  }
}
