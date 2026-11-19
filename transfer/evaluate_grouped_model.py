
from pathlib import Path

import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

DATA_FOLDER = Path(__file__).resolve().parent

CHANNELS = [
    "FZ", "FY", "FXL", "NIR", "VIS1L", "VIS1R",
    "F2", "F3", "F4", "F6", "VIS2L", "VIS2R",
    "F1", "F7", "F8", "F5", "VIS3L", "VIS3R",
]

# RO Fill 1 and RO Fill 2 are intentionally excluded.
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

    for label, filenames in FILES.items():
        for filename in filenames:
            path = DATA_FOLDER / filename

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

            # Each CSV is treated as one physical fill.
            df["fill_group"] = filename

            frames.append(df[CHANNELS + ["sample_type", "fill_group"]])
            print(f"{filename}: {len(df)} readings")

    if not frames:
        raise ValueError(
            "No CSV files loaded. Put the listed CSV files in this folder."
        )

    data = pd.concat(frames, ignore_index=True)

    print("\nReadings per category:")
    print(data.groupby("sample_type").size())

    print("\nIndependent CSV fills per category:")
    print(data.groupby("sample_type")["fill_group"].nunique())

    return data


def main():
    data = load_data()

    # A group-aware split needs multiple independent fills in every category.
    groups_per_class = data.groupby("sample_type")["fill_group"].nunique()

    if groups_per_class.min() < 2:
        print("\nGROUPED FOUR-CLASS EVALUATION CANNOT BE COMPLETED HONESTLY.")
        print("Each category needs at least two independent physical fills.")
        print(
            "Tea water currently has only one batch, so it cannot be "
            "tested on an unseen tea batch. Collect another independently "
            "prepared tea sample before evaluating all four categories "
            "with fill-level separation."
        )
        print(
            "No four-class accuracy is reported because it would be misleading."
        )
        return

    X = data[CHANNELS]
    y = data["sample_type"]
    groups = data["fill_group"]

    n_splits = min(3, int(groups_per_class.min()))

    cv = StratifiedGroupKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=42,
    )

    predictions = cross_val_predict(
        make_model(),
        X,
        y,
        groups=groups,
        cv=cv,
    )

    labels = ["ro_water", "soil_water", "tap_water", "tea_water"]

    print("\n=== GROUPED FOUR-CLASS EVALUATION ===")
    print(f"Accuracy: {accuracy_score(y, predictions):.3f}")

    print("\nClassification report:")
    print(classification_report(y, predictions, labels=labels, zero_division=0))

    print("Confusion matrix (rows=actual, columns=predicted):")
    print(pd.DataFrame(
        confusion_matrix(y, predictions, labels=labels),
        index=labels,
        columns=labels,
    ))

    results = data[["sample_type", "fill_group"]].copy()
    results["predicted_sample_type"] = predictions
    results["correct"] = results["sample_type"] == predictions
    results.to_csv(DATA_FOLDER / "grouped_model_predictions.csv", index=False)

    print("\nSaved: grouped_model_predictions.csv")
    print(
        "This evaluates sample categories, not drinking-water safety."
    )


if __name__ == "__main__":
    main()
