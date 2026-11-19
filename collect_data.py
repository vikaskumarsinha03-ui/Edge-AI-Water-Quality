
import csv
import time
from pathlib import Path

import serial
from serial.tools import list_ports

# ---------------- SETTINGS ----------------
SERIAL_PORT = "COM3"
BAUD_RATE = 115200
OUTPUT_FILE = Path.home() / "Desktop" /"tea_water_fill_1.csv"


# Collect 50 valid readings
TARGET_READINGS = 150

# Your ESP32 output contains 26 columns
EXPECTED_COLUMNS = 26

# ---------------- FIND SERIAL PORT ----------------
def show_ports():
    ports = list(list_ports.comports())

    print("\nAvailable serial ports:")
    for port in ports:
        print(f"  {port.device} - {port.description}")

    if not any(port.device == SERIAL_PORT for port in ports):
        print(f"\nWARNING: {SERIAL_PORT} was not found.")
        print("Change SERIAL_PORT to the correct port shown above.")
        return False

    return True


# ---------------- COLLECT DATA ----------------
def main():
    print("========================================")
    print("   WATER QUALITY DATA COLLECTION")
    print("========================================")
    print(f"Serial port : {SERIAL_PORT}")
    print(f"Output file : {OUTPUT_FILE}")
    print(f"Target rows : {TARGET_READINGS}")
    print("")

    if not show_ports():
        return

    if OUTPUT_FILE.exists():
        print("\nERROR: The output file already exists:")
        print(OUTPUT_FILE)
        print("Rename or move it before starting a fresh collection.")
        return

    input(
        "\n1. Close Arduino Serial Monitor.\n"
        "2. Fill the cuvette with clean RO water.\n"
        "3. Keep the cuvette and sensor in the same position.\n"
        "4. Press Enter to start collecting.\n"
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    rows_saved = 0
    header = None
    start_time = time.time()

    try:
        with serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=2
        ) as ser:

            # ESP32 may restart when the serial port opens.
            time.sleep(3)
            ser.reset_input_buffer()

            with OUTPUT_FILE.open(
                "w",
                newline="",
                encoding="utf-8"
            ) as csvfile:

                writer = csv.writer(csvfile)

                print("\nWaiting for ESP32 CSV header...")

                while rows_saved < TARGET_READINGS:
                    raw_line = ser.readline()

                    if not raw_line:
                        continue

                    line = raw_line.decode(
                        "utf-8",
                        errors="replace"
                    ).strip()

                    if not line:
                        continue

                    values = [item.strip() for item in line.split(",")]

                    # Find and save the header.
                    if values[0] == "sample_id":
                        if len(values) != EXPECTED_COLUMNS:
                            print(
                                f"Header has {len(values)} columns; "
                                f"expected {EXPECTED_COLUMNS}."
                            )
                            print("Check the ESP32 code before collecting.")
                            return

                        header = values
                        writer.writerow(header)
                        csvfile.flush()
                        print("Header received.")
                        print("Collecting readings...\n")
                        continue

                    # Ignore data until a header is received.
                    if header is None:
                        continue

                    # Skip malformed rows.
                    if len(values) != len(header):
                        print(
                            f"Skipped row: expected {len(header)} columns, "
                            f"received {len(values)}."
                        )
                        continue

                    # Check that measurement fields are numeric.
                    try:
                        float(values[0])
                        float(values[1])
                        for value in values[2:]:
                            float(value)
                    except ValueError:
                        print("Skipped a row containing non-numeric data.")
                        continue

                    writer.writerow(values)
                    csvfile.flush()
                    rows_saved += 1

                    print(
                        f"Saved {rows_saved}/{TARGET_READINGS} readings",
                        end="\r"
                    )

        elapsed = time.time() - start_time

        print("\n\nCollection finished!")
        print(f"Readings saved: {rows_saved}")
        print(f"Time elapsed: {elapsed:.1f} seconds")
        print(f"CSV file: {OUTPUT_FILE}")

    except serial.SerialException as error:
        print("\nSerial port error:")
        print(error)
        print("Check the USB cable, COM port, and Serial Monitor.")

    except KeyboardInterrupt:
        print("\n\nCollection stopped by user.")
        print(f"Readings saved: {rows_saved}")
        print(f"Partial CSV file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
