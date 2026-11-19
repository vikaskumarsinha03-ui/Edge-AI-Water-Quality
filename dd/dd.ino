#include <Wire.h>
#include <Adafruit_AS7343.h>

Adafruit_AS7343 sensor;

// Classic ESP32 DevKit pin assignments
const int SDA_PIN = 21;
const int SCL_PIN = 22;
const int PH_PIN = 34;
const int TDS_PIN = 35;

const unsigned long SAMPLE_INTERVAL_MS = 2000;

uint16_t spectrum[18];
unsigned long sampleID = 0;
unsigned long lastSample = 0;

bool readSpectrum() {
  if (!sensor.startMeasurement()) {
    return false;
  }

  unsigned long start = millis();

  while (!sensor.dataReady()) {
    if (millis() - start >= 3000) {
      return false;
    }
    delay(5);
  }

  return sensor.readAllChannels(spectrum);
}

void printHeader() {
  Serial.println(
    "sample_id,time_ms,ph_adc,ph_mV,tds_adc,tds_mV,"
    "FZ,FY,FXL,NIR,VIS1L,VIS1R,F2,F3,F4,F6,"
    "VIS2L,VIS2R,F1,F7,F8,F5,VIS3L,VIS3R"
  );
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(SDA_PIN, SCL_PIN);

  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db);
  analogSetPinAttenuation(TDS_PIN, ADC_11db);

  if (!sensor.begin(0x39, &Wire)) {
    Serial.println("# ERROR: AS7343 not detected");
    while (true) {
      delay(1000);
    }
  }

  sensor.setSMUXMode(AS7343_SMUX_18CH);

  printHeader();
  lastSample = millis();
}

void loop() {
  if (millis() - lastSample < SAMPLE_INTERVAL_MS) {
    return;
  }

  lastSample = millis();

  // Read analog modules
  int phADC = analogRead(PH_PIN);
  uint32_t phMilliVolts = analogReadMilliVolts(PH_PIN);

  int tdsADC = analogRead(TDS_PIN);
  uint32_t tdsMilliVolts = analogReadMilliVolts(TDS_PIN);

  // Read spectral sensor
  if (!readSpectrum()) {
    Serial.println("# ERROR: spectral measurement failed");
    return;
  }

  // Print one complete CSV row
  sampleID++;

  Serial.print(sampleID);
  Serial.print(",");
  Serial.print(millis());
  Serial.print(",");
  Serial.print(phADC);
  Serial.print(",");
  Serial.print(phMilliVolts);
  Serial.print(",");
  Serial.print(tdsADC);
  Serial.print(",");
  Serial.print(tdsMilliVolts);

  for (int i = 0; i < 18; i++) {
    Serial.print(",");
    Serial.print(spectrum[i]);
  }

  Serial.println();
}