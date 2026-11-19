
from pathlib import Path

import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

FOLDER = Path(__file__).resolve().parent

CHANNELS = [
    "FZ", "FY", "FXL", "NIR", "VIS1L", "VIS1R",
    "F2", "F3", "F4", "F6", "VIS2L", "VIS2R",
    "F1", "F7", "F8", "F5", "VIS3L", "VIS3R",
]

FILES = {
    "ro_water": [
        "ro_water_fill_3.csv",
        "ro_water_fill_4.csv",
        "ro_water_fill_5.csv",
    ],
    "soil_water": [
        "soil_water_fill_1.csv",
        "soil_water_fill_2.csv",
        "soil_water_fill_3.csv",
    ],
    "tap_water": [
        "tap_water_fill_1.csv",
        "tap_water_fill_2.csv",
        "tap_water_fill_3.csv",
    ],
}


def load_data():
    frames = []

    for label, filenames in FILES.items():
        for filename in filenames:
            path = FOLDER / filename

            if not path.exists():
                print(f"Missing file: {filename}")
                continue

            df = pd.read_csv(path)
            df.columns = df.columns.astype(str).str.strip()

            missing = [c for c in CHANNELS if c not in df.columns]
            if missing:
                print(f"Skipping {filename}; missing columns: {missing}")
                continue

            for col in CHANNELS:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.dropna(subset=CHANNELS).copy()
            df["sample_type"] = label
            df["fill_group"] = filename

            frames.append(df[CHANNELS + ["sample_type", "fill_group"]])
            print(f"{filename}: {len(df)} readings")

    if not frames:
        raise ValueError("No usable files found in the ml folder.")

    data = pd.concat(frames, ignore_index=True)

    fills = data.groupby("sample_type")["fill_group"].nunique()
    if fills.min() < 2:
        raise ValueError("Each category needs at least two separate fills.")

    return data


def main():
    data = load_data()

    X = data[CHANNELS]
    y = data["sample_type"]
    groups = data["fill_group"]

    cv = StratifiedGroupKFold(
        n_splits=3,
        shuffle=True,
        random_state=42,
    )

    predictions = cross_val_predict(
        make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=42,
            ),
        ),
        X,
        y,
        groups=groups,
        cv=cv,
    )

    labels = ["ro_water", "soil_water", "tap_water"]

    print("\n=== GROUPED EVALUATION: RO / SOIL / TAP ===")
    print(f"Accuracy: {accuracy_score(y, predictions):.3f}")

    print("\nClassification report:")
    print(classification_report(y, predictions, labels=labels, zero_division=0))

    print("\nConfusion matrix (rows=actual, columns=predicted):")
    print(pd.DataFrame(
        confusion_matrix(y, predictions, labels=labels),
        index=labels,
        columns=labels,
    ))

    results = data[["sample_type", "fill_group"]].copy()
    results["predicted_sample_type"] = predictions
    results["correct"] = results["sample_type"] == predictions
    results.to_csv(FOLDER / "three_class_grouped_predictions.csv", index=False)

    print("\nSaved: three_class_grouped_predictions.csv")
    print("This evaluates sample categories, not drinking-water safety.")


if __name__ == "__main__":
    main()
