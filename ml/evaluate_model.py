from pathlib import Path

import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

# Put this script and the CSV files listed below in the same folder.
DATA_FOLDER = Path(__file__).resolve().parent
OUTPUT_FILE = DATA_FOLDER / "four_class_evaluation_predictions.csv"

SPECTRAL_COLUMNS = [
    "FZ", "FY", "FXL", "NIR", "VIS1L", "VIS1R",
    "F2", "F3", "F4", "F6", "VIS2L", "VIS2R",
    "F1", "F7", "F8", "F5", "VIS3L", "VIS3R",
]

# As requested, RO Fill 1 and RO Fill 2 are excluded.
# If your actual filenames differ, edit the names below to match exactly.
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
    # These 150 readings came from one tea-water batch.
    "tea_water": [
        "tea_water_fill_1.csv",
    ],
}


def make_model():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=42,
        ),
    )


def load_data():
    frames = []
    missing_files = []

    for label, filenames in FILES.items():
        for filename in filenames:
            path = DATA_FOLDER / filename

            if not path.exists():
                missing_files.append(filename)
                continue

            try:
                df = pd.read_csv(path)
            except Exception as exc:
                print(f"WARNING: Could not read {filename}: {exc}")
                continue

            df.columns = df.columns.astype(str).str.strip()

            missing_columns = [
                col for col in SPECTRAL_COLUMNS if col not in df.columns
            ]
            if missing_columns:
                print(
                    f"WARNING: Skipping {filename}; missing columns: "
                    + ", ".join(missing_columns)
                )
                continue

            # Remove any repeated CSV header accidentally captured as a data row.
            if "sample_id" in df.columns:
                df = df[
                    df["sample_id"].astype(str).str.strip() != "sample_id"
                ].copy()

            for col in SPECTRAL_COLUMNS:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            before = len(df)
            df = df.dropna(subset=SPECTRAL_COLUMNS).copy()
            df["sample_type"] = label
            df["source_file"] = filename
            frames.append(
                df[SPECTRAL_COLUMNS + ["sample_type", "source_file"]]
            )
            print(
                f"{filename}: {len(df)} valid readings "
                f"({before - len(df)} rows removed)"
            )

    if missing_files:
        print("\nWARNING: These expected files were not found in:")
        print(DATA_FOLDER)
        for filename in missing_files:
            print(f"  - {filename}")

    if not frames:
        raise ValueError(
            "\nNo usable CSV files were loaded. Put the listed CSV files in "
            "the same folder as evaluate_model.py, or edit FILES to use "
            "their actual filenames."
        )

    data = pd.concat(frames, ignore_index=True)
    counts = data["sample_type"].value_counts()

    print("\nLoaded readings by category:")
    print(counts.to_string())

    if data["sample_type"].nunique() < 2:
        raise ValueError(
            "At least two categories with valid files are needed to evaluate."
        )

    return data


def main():
    data = load_data()

    # Split rows at random while preserving approximate class proportions.
    # NOTE: readings from the same physical fill can land in both sets.
    # This is a preliminary demonstration, not an independent-fill validation.
    X = data[SPECTRAL_COLUMNS]
    y = data["sample_type"]

    class_counts = y.value_counts()
    if class_counts.min() < 2:
        raise ValueError(
            "Each included category needs at least two valid readings for "
            "a stratified train/test split."
        )

    X_train, X_test, y_train, y_test, source_train, source_test = (
        train_test_split(
            X,
            y,
            data["source_file"],
            test_size=0.25,
            random_state=42,
            stratify=y,
        )
    )

    model = make_model()
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    labels = ["ro_water", "soil_water", "tap_water", "tea_water"]

    print("\n=== FOUR-CATEGORY PRELIMINARY EVALUATION ===")
    print("Training readings:", len(X_train))
    print("Test readings:", len(X_test))
    print(f"Accuracy: {accuracy_score(y_test, predictions):.3f}")

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            labels=labels,
            zero_division=0,
        )
    )

    print("Confusion matrix (rows=actual, columns=predicted):")
    print(
        pd.DataFrame(
            confusion_matrix(y_test, predictions, labels=labels),
            index=labels,
            columns=labels,
        )
    )

    results = X_test.copy()
    results["source_file"] = source_test
    results["actual_sample_type"] = y_test
    results["predicted_sample_type"] = predictions
    results["correct"] = (
        results["actual_sample_type"] == results["predicted_sample_type"]
    )
    results.to_csv(OUTPUT_FILE, index=False)

    print(f"\nSaved predictions to: {OUTPUT_FILE}")
    print(
        "\nIMPORTANT LIMITATIONS:\n"
        "- RO Fill 1 and RO Fill 2 were excluded as requested.\n"
        "- Tea readings come from one batch, so tea performance on new batches "
        "has not been independently validated.\n"
        "- Random row splitting may overestimate performance because readings "
        "from the same fill can appear in both training and test sets.\n"
        "- This predicts sample category, not drinking-water safety."
    )


if __name__ == "__main__":
    main()
