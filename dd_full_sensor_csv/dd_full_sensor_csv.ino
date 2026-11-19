/*
  ESP32 water-quality CSV collector
  AS7343 SDA=21, SCL=22; pH=34; TDS=35; serial=115200.
  pH/TDS values are estimates and must be calibrated for your modules.
*/
#include <Wire.h>
#include <Adafruit_AS7343.h>

Adafruit_AS7343 sensor;
const int SDA_PIN=21, SCL_PIN=22, PH_PIN=34, TDS_PIN=35;
const unsigned long SAMPLE_INTERVAL_MS=2000;
const float ADC_MAX_VALUE=4095.0f, ADC_REFERENCE_MV=3300.0f;
const float PH_SLOPE_PER_V=-5.70f, PH_INTERCEPT=21.34f, TDS_FACTOR=0.50f;

uint16_t spectrum[18];
unsigned long sampleID=0, lastSample=0;
bool sensorReady=false;

float estimatePH(float mv) {
  // Placeholder only; calibrate using pH buffer solutions.
  return PH_SLOPE_PER_V*(mv/1000.0f)+PH_INTERCEPT;
}
float estimateTDS(float mv) {
  // Generic approximation only; calibrate for your TDS module.
  float v=mv/1000.0f;
  float ec=133.42f*v*v*v-255.86f*v*v+857.39f*v;
  if (ec<0) ec=0;
  return ec*TDS_FACTOR;
}
void printHeader() {
  Serial.println("sample_id,time_ms,ph_adc,ph_mV,pH_estimated,tds_adc,tds_mV,TDS_estimated_ppm,FZ,FY,FXL,NIR,VIS1L,VIS1R,F2,F3,F4,F6,VIS2L,VIS2R,F1,F7,F8,F5,VIS3L,VIS3R");
}
void setup() {
  Serial.begin(115200);
  delay(1000);
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db);
  analogSetPinAttenuation(TDS_PIN, ADC_11db);
  Wire.begin(SDA_PIN,SCL_PIN);

  sensorReady=sensor.begin();
  if (sensorReady) {
    sensor.setGain(AS7343_GAIN_64X);
    sensor.setATIME(29);
    sensor.setASTEP(599);
    sensor.setSMUXMode(AS7343_SMUX_18CH);
    Serial.println("#INFO,AS7343_detected");
  } else {
    Serial.println("#ERROR,AS7343_not_detected_check_SDA_SCL_power_GND");
  }
  printHeader();
}
void loop() {
  unsigned long now=millis();
  if (now-lastSample<SAMPLE_INTERVAL_MS) return;
  lastSample=now;

  int phADC=analogRead(PH_PIN);
  int tdsADC=analogRead(TDS_PIN);
  float phMilliVolts=(float)analogReadMilliVolts(PH_PIN);
  float tdsMilliVolts=(float)analogReadMilliVolts(TDS_PIN);
  float pHEstimated=estimatePH(phMilliVolts);
  float tdsEstimated=estimateTDS(tdsMilliVolts);
  bool spectralOK=sensorReady && sensor.readAllChannels(spectrum);
  sampleID++;

  Serial.print(sampleID); Serial.print(',');
  Serial.print(now); Serial.print(',');
  Serial.print(phADC); Serial.print(',');
  Serial.print(phMilliVolts,1); Serial.print(',');
  Serial.print(pHEstimated,2); Serial.print(',');
  Serial.print(tdsADC); Serial.print(',');
  Serial.print(tdsMilliVolts,1); Serial.print(',');
  Serial.print(tdsEstimated,2);
  for (int i=0;i<18;i++) {
    Serial.print(',');
    Serial.print(spectralOK ? (long)spectrum[i] : -1L);
  }
  Serial.println();
}
