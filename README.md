# Edge-AI Based Water Quality Assessment

An embedded water-quality assessment project combining spectral sensing, sensor measurements, machine-learning experiments, and ESP32 firmware.

## Repository structure

- `firmware/` — ESP32 Arduino sketches for sensor acquisition
- `python/` — data collection and edge/dashboard applications
- `ml/` — model training, evaluation, and dashboard scripts
- `data/` — sample water-sensor datasets and evaluation outputs
- `docs/` — project design report

## Hardware

- ESP32 development board
- AS7343 spectral sensor
- TDS sensor
- pH probe/interface (where configured)

## Getting started

1. Review the firmware sketches in `firmware/` and confirm the board, sensor wiring, and I2C pins match your hardware.
2. Install Python dependencies with `pip install -r requirements.txt`.
3. Run the relevant data-collection, model-evaluation, or dashboard script from its folder.

## Notes

This repository contains experimental project code and sample datasets. Sensor calibration, wiring, model compatibility, and dependency versions should be checked for your specific setup before relying on measurements. The sample data and model outputs are not a substitute for certified laboratory water testing.
