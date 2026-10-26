/*
 * Manual motor test for Seeed Studio XIAO ESP32C3 + ULN2003.
 *
 * Open Serial Monitor at 115200 baud, then send:
 *   0 / 1 / 2 / 3  - run one motor for TEST_MS
 *   a              - run all motors one by one
 *   s              - stop all motors
 */

#define M0 2  // XIAO D0 / GPIO2
#define M1 3  // XIAO D1 / GPIO3
#define M2 4  // XIAO D2 / GPIO4
#define M3 5  // XIAO D3 / GPIO5

#define TEST_MS 5000

const int MOTOR_PINS[] = {M0, M1, M2, M3};
const int MOTOR_COUNT = 4;

void stopAll() {
  for (int i = 0; i < MOTOR_COUNT; i++) {
    digitalWrite(MOTOR_PINS[i], LOW);
  }
}

void runMotor(int idx) {
  if (idx < 0 || idx >= MOTOR_COUNT) {
    Serial.println("ERR: motor index must be 0..3");
    return;
  }

  stopAll();
  Serial.print("RUN M");
  Serial.print(idx);
  Serial.print(" pin GPIO");
  Serial.print(MOTOR_PINS[idx]);
  Serial.println(" for 5 seconds");

  digitalWrite(MOTOR_PINS[idx], HIGH);
  delay(TEST_MS);
  digitalWrite(MOTOR_PINS[idx], LOW);

  Serial.print("DONE M");
  Serial.println(idx);
}

void runAll() {
  Serial.println("RUN ALL: M0 -> M1 -> M2 -> M3");
  for (int i = 0; i < MOTOR_COUNT; i++) {
    runMotor(i);
    delay(1500);
  }
  Serial.println("DONE ALL");
}

void printHelp() {
  Serial.println();
  Serial.println("Motor test ready.");
  Serial.println("Send 0, 1, 2, or 3 to run one motor.");
  Serial.println("Send a to run all motors one by one.");
  Serial.println("Send s to stop all motors.");
}

void setup() {
  Serial.begin(115200);
  delay(500);

  for (int i = 0; i < MOTOR_COUNT; i++) {
    pinMode(MOTOR_PINS[i], OUTPUT);
  }
  stopAll();

  printHelp();
}

void loop() {
  if (!Serial.available()) {
    return;
  }

  char cmd = Serial.read();
  while (Serial.available()) {
    Serial.read();
  }

  if (cmd >= '0' && cmd <= '3') {
    runMotor(cmd - '0');
  } else if (cmd == 'a' || cmd == 'A') {
    runAll();
  } else if (cmd == 's' || cmd == 'S') {
    stopAll();
    Serial.println("STOP");
  } else if (cmd == '\n' || cmd == '\r') {
    // Ignore line endings.
  } else {
    printHelp();
  }
}
