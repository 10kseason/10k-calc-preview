# BMS Difficulty Calculator (Antigravity v0.1)

A scientifically calibrated difficulty calculator for 10-key rhythm game charts (BMS/Osu!mania).

## Key Features
*   **Advanced Difficulty Model**: Uses a weighted combination of NPS, LN Strain, Jack Penalty, Roll Penalty, Alt Cost, Hand Strain, and Chord Weight.
*   **Band-wise Calibration**: Implements a sophisticated band-wise correction logic to address S-shaped bias, ensuring accurate ratings across the full difficulty spectrum (Lv.1 - Lv.25+).
*   **Calibrated Parameters**: Optimized on a large dataset of GCS and 10k2s charts (MAE: 1.70).
    *   `D_min`: 11.52 (Level 1 Reference)
    *   `D_max`: 185.91 (Level 25 Reference)
    *   `gamma`: 0.47 (Curve Shape)
*   **Uncapped Levels**: Supports level calculation beyond the traditional Lv.25 cap, useful for "Overjoy" or "Insane" difficulty charts.
*   **HP Analysis**: Includes a Qwilight result converter and HP9 survival analysis.

## Installation & Usage
1.  **Download**: Get the latest release from the `dist` folder.
2.  **Run**: Execute `BMSCalculator.exe`.
3.  **Calculate**:
    *   Click "Browse" to select a `.bms`, `.bme`, or `.osu` file.
    *   Click "Calculate" to see the estimated level and detailed metrics.
    *   Use "Optimized Weights" (default) for the most accurate results.

## Developer Notes
*   **Build**: Run `pyinstaller BMSCalculator.spec` to build the executable.
*   **Calibration**: Use `calibrate_levels.py` to recalibrate parameters if new data is available.
*   **Analysis**: Run `run_full_analysis.py` to generate a comprehensive report on your local chart collection.

## Latest Updates (v0.1)
*   **Refined Calibration**: Excluded outliers (Lv.25+) during calibration for better mid-range accuracy.
*   **Band-wise Correction**: Added specific logic to fix under-prediction at high levels and over-prediction at low levels.
*   **GUI Update**: Hardcoded the latest parameters into the application for immediate use.

## Credits
Developed by gemini & User.
