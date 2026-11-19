"""
Train a prototype four-category spectral classifier.
Place this script in the same folder as cleaned_four_class_dataset.csv.
Run: python train_model_4class.py

Uses only the 18 AS7343 spectral channels.
Validation is grouped by independent fill for RO, soil, and tap water.
Tea readings all come from one batch, so tea generalization cannot be independently validated yet.
This model classifies sample categories only; it does not determine water safety.
"""
from pathlib import Path
import pandas as pd
import joblib
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

DATA_FILE = Path("cleaned_four_class_dataset.csv")
MODEL_FILE = Path("water_sample_classifier_4class.joblib")
SPECTRAL_COLUMNS = [
    "FZ", "FY", "FXL", "NIR", "VIS1L", "VIS1R",
    "F2", "F3", "F4", "F6", "VIS2L", "VIS2R",
    "F1", "F7", "F8", "F5", "VIS3L", "VIS3R"
]
VALIDATED_CLASSES = ["RO_water", "soil_water", "tap_water"]

def make_model():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=3000, class_weight="balanced", random_state=42)
    )

def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Cannot find {DATA_FILE}. Put it in the same folder as this script."
        )
    df = pd.read_csv(DATA_FILE)
    required = SPECTRAL_COLUMNS + ["sample_type", "fill_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # Honest grouped validation only for classes with multiple independent fills.
    val_df = df[df["sample_type"].isin(VALIDATED_CLASSES)].dropna(
        subset=SPECTRAL_COLUMNS + ["sample_type", "fill_id"]
    ).copy()
    Xv = val_df[SPECTRAL_COLUMNS].apply(pd.to_numeric, errors="coerce")
    yv = val_df["sample_type"].astype(str)
    groups = val_df["fill_id"].astype(str)
    n_splits = min(4, groups.nunique())
    predictions = cross_val_predict(
        make_model(), Xv, yv, groups=groups, cv=GroupKFold(n_splits=n_splits)
    )
    print("\\n=== GROUPED VALIDATION: RO, SOIL, TAP ===")
    print(f"Readings evaluated: {len(val_df)}")
    print(f"Independent fills: {groups.nunique()}")
    print(f"Accuracy: {accuracy_score(yv, predictions):.3f}")
    print(classification_report(yv, predictions, zero_division=0))
    print("Confusion matrix (rows/columns RO_water, soil_water, tap_water):")
    print(confusion_matrix(yv, predictions, labels=VALIDATED_CLASSES))

    # Train four-category prototype on all data for demo use.
    full = df.dropna(subset=SPECTRAL_COLUMNS + ["sample_type"]).copy()
    X = full[SPECTRAL_COLUMNS].apply(pd.to_numeric, errors="coerce")
    y = full["sample_type"].astype(str)
    model = make_model()
    model.fit(X, y)
    joblib.dump({
        "model": model,
        "spectral_columns": SPECTRAL_COLUMNS,
        "classes": ["RO_water", "soil_water", "tap_water", "tea_water"],
        "note": "Prototype only. Tea is one batch; not validated on independent tea batches. Not a water safety model."
    }, MODEL_FILE)
    print(f"\\nSaved four-class prototype model: {MODEL_FILE.resolve()}")
    print("Tea readings are from one batch; collect fresh tea batches before trusting tea predictions.")
    print("This predicts sample category, not drinking-water safety.")

if __name__ == "__main__":
    main()
