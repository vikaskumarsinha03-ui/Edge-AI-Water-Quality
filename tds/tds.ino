const int TDS_PIN = 34;

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);

  Serial.println("TDS Sensor Test");
}

void loop() {
  int rawValue = analogRead(TDS_PIN);

  float voltage = rawValue * 3.3 / 4095.0;

  Serial.print("Raw ADC: ");
  Serial.print(rawValue);

  Serial.print(" | Voltage: ");
  Serial.print(voltage, 3);
  Serial.println(" V");

  delay(1000);
}