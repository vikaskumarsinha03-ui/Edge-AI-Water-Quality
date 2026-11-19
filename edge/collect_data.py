
import csv
import time
from pathlib import Path

import serial

# Your Arduino screenshot shows COM3 and 115200 baud.
PORT = "COM3"
BAUD_RATE = 115200

OUTPUT_FILE = Path.home() / "Desktop" / "water_quality_data.csv"

EXPECTED_COLUMNS = 26

print("Edge-AI Water Quality Data Collector")
print(f"Serial port: {PORT}")
print(f"Output file: {OUTPUT_FILE}")
print("\nClose Arduino Serial Monitor before continuing.")
input("Press ENTER to start collecting data...")

try:
    with serial.Serial(PORT, BAUD_RATE, timeout=2) as esp:
        # Allow ESP32 to reboot after opening the serial port.
        time.sleep(2)
        esp.reset_input_buffer()

        header_written = OUTPUT_FILE.exists() and OUTPUT_FILE.stat().st_size > 0
        rows_saved = 0

        with OUTPUT_FILE.open(
            "a", newline="", encoding="utf-8"
        ) as file:
            writer = csv.writer(file)

            print("\nCollecting readings. Press Ctrl+C to stop.")
            print("Keep this terminal open while collecting.\n")

            while True:
                raw = esp.readline()

                if not raw:
                    continue

                line = raw.decode("utf-8", errors="replace").strip()

                if not line:
                    continue

                # Ignore ESP32 boot messages and error messages.
                if line.startswith("#"):
                    print("Device message:", line)
                    continue

                fields = next(csv.reader([line]))

                # Accept the CSV header only once.
                if fields[0].strip() == "sample_id":
                    if not header_written:
                        if len(fields) != EXPECTED_COLUMNS:
                            print(
                                f"Unexpected header length: {len(fields)}"
                            )
                            continue

                        writer.writerow(fields)
                        file.flush()
                        header_written = True
                        print("CSV header saved.")
                    continue

                # Ignore incomplete or non-numeric rows.
                if len(fields) != EXPECTED_COLUMNS:
                    print(f"Skipped incomplete row: {line[:80]}")
                    continue

                try:
                    int(fields[0])
                    int(fields[1])
                    [float(value) for value in fields[2:]]
                except ValueError:
                    print(f"Skipped invalid row: {line[:80]}")
                    continue

                if not header_written:
                    print("Waiting for CSV header from ESP32...")
                    continue

                writer.writerow(fields)
                file.flush()
                rows_saved += 1

                print(
                    f"Saved {rows_saved} new readings | "
                    f"Sample ID: {fields[0]} | "
                    f"pH estimate: {fields[4]} | "
                    f"TDS estimate: {fields[7]} ppm"
                )

except serial.SerialException as error:
    print("\nCould not open the ESP32 serial port.")
    print("Check that the USB cable is connected and COM3 is correct.")
    print("Close Arduino Serial Monitor and try again.")
    print("Details:", error)

except KeyboardInterrupt:
    print("\nCollection stopped.")

finally:
    print(f"\nCSV file location: {OUTPUT_FILE}")
