
#include <Wire.h>
#include <Adafruit_AS7343.h>

Adafruit_AS7343 sensor;

const int SDA_PIN = 21;
const int SCL_PIN = 22;

uint16_t readings[18];

const char* channelNames[18] = {
  "FZ 450nm Blue",
  "FY 555nm Yellow-Green",
  "FXL 600nm Orange",
  "NIR 855nm",
  "VIS Top-Left 1",
  "VIS Bottom-Right 1",
  "F2 425nm Violet-Blue",
  "F3 475nm Blue-Cyan",
  "F4 515nm Green",
  "F6 640nm Red",
  "VIS Top-Left 2",
  "VIS Bottom-Right 2",
  "F1 405nm Violet",
  "F7 690nm Deep-Red",
  "F8 745nm Near-IR",
  "F5 550nm Green-Yellow",
  "VIS Top-Left 3",
  "VIS Bottom-Right 3"
};

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println();
  Serial.println("Water Quality Monitoring");
  Serial.println("AS7343 Sensor Test");
  Serial.println("------------------------");

  if (!sensor.begin(0x39, &Wire)) {
    Serial.println("ERROR: AS7343 not detected!");
    Serial.println("Check power, SDA, SCL and wiring.");
    while (true) {
      delay(1000);
    }
  }

  Serial.println("AS7343 detected successfully!");

  sensor.setSMUXMode(AS7343_SMUX_18CH);

  Serial.println("Starting spectral measurements...");
}

void loop() {
  if (!sensor.startMeasurement()) {
    Serial.println("ERROR: Could not start measurement.");
    delay(1000);
    return;
  }

  unsigned long startTime = millis();

  while (!sensor.dataReady()) {
    if (millis() - startTime > 3000) {
      Serial.println("ERROR: Measurement timeout.");
      delay(1000);
      return;
    }
    delay(5);
  }

  if (!sensor.readAllChannels(readings)) {
    Serial.println("ERROR: Could not read channels.");
    delay(1000);
    return;
  }

  Serial.println();
  Serial.println("---- SPECTRAL READINGS ----");

  for (int i = 0; i < 18; i++) {
    Serial.print(channelNames[i]);
    Serial.print(": ");
    Serial.println(readings[i]);
  }

  Serial.println("---------------------------");

  delay(1000);
}
