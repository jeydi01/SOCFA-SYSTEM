#!/usr/bin/env python3
"""
SoCFA — Soil Condition Random Forest
====================================
Trains a Random Forest that classifies soil condition as Healthy, Moderate
or Poor from the 4 sensor parameters used by the SoCFA soil nodes:

    pH | Temperature (°C) | Electrical Conductivity (EC) | Soil Moisture (%)

DATASET
  "NPK Soil Nutrient Dataset on Horticulture Land" (Kaggle,
  muhammadaryadiwa/npk-soil-nutrient-dataset-on-horticulture-land).
  NPK 7-in-1 soil sensor readings from horticulture land in Padang,
  West Sumatra, Indonesia (chili, cucumber, bok choy). EC is in µS/cm.

LABELS
  The dataset has no health label, so every row is labelled with
  literature-based thresholds: pH (Table 3), EC (Table 4), soil temperature
  (Table 6) and soil moisture for palay on Bulaoen clay loam, derived from
  saturation and wilting point with the FAO-56 rice depletion fraction
  (0.20 of saturation). Each parameter is rated Healthy / Moderate / Poor, then the
  maximum limitation method combines them:
      Healthy  = all four parameters are Healthy
      Poor     = any one parameter is Poor
      Moderate = everything else
  The Random Forest then learns to reproduce this expert labelling from the
  raw readings, so it can be applied to new sensor data.

RUN
  pip install pandas scikit-learn openpyxl matplotlib seaborn joblib
  python train_soil_rf.py

OUTPUT (model/ folder)
  soil_rf.joblib                 trained model (+ feature order)
  soil_rf_confusion_matrix.png
  soil_rf_feature_importance.png
  soil_rf_report.txt             metrics for the paper
  soil_dataset_labeled.csv       the labelled training data
"""

import io
import os
import sys
import zipfile
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))

# Either the downloaded Kaggle zip OR the folder you extracted it to.
DATA_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "npk-soil-nutrient-dataset")

MODEL_DIR = os.path.join(HERE, "model")
SEED      = 42

# The first 1,300 rows of the chili file sit in a perfectly uniform box
# (moisture 40.0–75.0, temp 24.0–33.0, EC 100–220, pH 5.5–6.8), unlike the
# rest of the data — they look generated rather than measured. They are left
# out by default. Set to False to keep them (and say so in the paper).
EXCLUDE_SUSPECT_CHILI_BLOCK = True
SUSPECT_CHILI_ROWS          = 1300

# Readings from the SoCFA soil nodes themselves (snapshot of the Firebase
# soil_data, Apr 28–29 2026). They add dry-soil examples the Kaggle data lacks.
OWN_DATA_PATH = os.path.join(HERE, "own_soil_readings.csv")

# Volumetric moisture cannot exceed saturation (clay loam ≈ 46.4 %); most
# Kaggle moisture values are above it, so those readings are left out.
EXCLUDE_ABOVE_SATURATION = True

FEATURES = ["ph", "temperature", "ec_dsm", "moisture"]
CLASSES  = ["Healthy", "Moderate", "Poor"]

FILES = {  # file inside the zip → crop name
    "cabe_akhir.xlsx":   "chili",
    "pakcoy_akhir.xlsx": "bok choy",
    "timun_akhir.xlsx":  "cucumber",
}

# ─────────────────────────────────────────────
# LABELLING RULES  (soil_rules.py — shared with fusion.py)
# ─────────────────────────────────────────────
from soil_rules import (rate_ph, rate_temperature, rate_ec, rate_moisture, label_row,
                        WILTING_POINT, SATURATION, P_RICE, MOISTURE_HEALTHY_MIN)

# ─────────────────────────────────────────────
# LOAD
# ─────────────────────────────────────────────
def _read_excel_bytes(data):
    try:
        return pd.read_excel(io.BytesIO(data))
    except ImportError:
        sys.exit("Missing package: run  pip install openpyxl")

def load_raw(path):
    """Read the 3 Excel files from the Kaggle zip (or an extracted folder)."""
    frames = []
    if os.path.isfile(path) and path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                base = os.path.basename(name)
                if base in FILES:
                    df = _read_excel_bytes(z.read(name))
                    df["crop"] = FILES[base]
                    frames.append(df)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for base in files:
                if base in FILES:
                    with open(os.path.join(root, base), "rb") as f:
                        df = _read_excel_bytes(f.read())
                    df["crop"] = FILES[base]
                    frames.append(df)
    else:
        sys.exit(f"Dataset not found: {path}\n"
                 "Download it from Kaggle and set DATA_PATH at the top of this file.")

    if len(frames) != 3:
        sys.exit(f"Expected 3 Excel files, found {len(frames)} in {path}")

    out = []
    for df in frames:
        df.columns = [c.strip().lower() for c in df.columns]   # timun uses 'EC', 'pH'
        df = df[["crop", "moisture", "temperature", "ec", "ph"]].copy()
        df["source"] = "kaggle"
        out.append(df)
    return pd.concat(out, ignore_index=True), frames


def load_own(path):
    """Readings from the SoCFA nodes (EC in µS/cm, humidity = soil moisture %)."""
    if not os.path.isfile(path):
        sys.exit(f"Own sensor readings not found: {path}")
    df = pd.read_csv(path).rename(columns={"humidity": "moisture"})
    df["crop"] = "palay"
    df["source"] = "socfa nodes"
    return df[["crop", "moisture", "temperature", "ec", "ph", "source"]]


def clean(df, frames):
    n0 = len(df)
    notes = []

    if EXCLUDE_SUSPECT_CHILI_BLOCK:
        chili_idx = df.index[df["crop"] == "chili"][:SUSPECT_CHILI_ROWS]
        df = df.drop(index=chili_idx)
        notes.append(f"excluded {len(chili_idx)} suspected generated chili rows")

    df = df.copy()
    for col in ["moisture", "temperature", "ec", "ph"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["moisture", "temperature", "ec", "ph"])
    notes.append(f"dropped {before - len(df)} rows with missing values")

    # Physically impossible readings (sensor glitches)
    before = len(df)
    df = df[(df["ec"] >= 0) &
            (df["ph"].between(0, 14)) &
            (df["moisture"].between(0, 100)) &
            (df["temperature"].between(-10, 60))]
    notes.append(f"dropped {before - len(df)} impossible readings (e.g. negative EC)")

    # Exactly 0 % moisture or 0 EC: probe not in the soil
    before = len(df)
    df = df[(df["moisture"] > 0) & (df["ec"] > 0)]
    notes.append(f"dropped {before - len(df)} zero readings (probe not in soil)")

    if EXCLUDE_ABOVE_SATURATION:
        before = len(df)
        df = df[df["moisture"] <= SATURATION]
        notes.append(f"dropped {before - len(df)} readings above saturation ({SATURATION}% moisture)")

    # Sensor reports EC in µS/cm → convert to dS/m (1 dS/m = 1000 µS/cm)
    df = df.copy()
    df["ec_dsm"] = df["ec"] / 1000.0
    return df.reset_index(drop=True), n0, notes

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    os.makedirs(MODEL_DIR, exist_ok=True)
    print("=" * 60)
    print("SoCFA — Soil Condition Random Forest")
    print("=" * 60)

    raw, frames = load_raw(DATA_PATH)
    raw = pd.concat([raw, load_own(OWN_DATA_PATH)], ignore_index=True)
    df, n0, notes = clean(raw, frames)
    print(f"Loaded {n0} readings")
    for n in notes:
        print(f"  - {n}")
    print(f"Usable readings: {len(df)}  " +
          ", ".join(f"{s}: {c}" for s, c in df["source"].value_counts().items()) + "\n")
    notes.append("usable by source: " + json.dumps(df["source"].value_counts().to_dict()))

    df["label"] = [label_row(*r) for r in df[["ph", "temperature", "ec_dsm", "moisture"]].values]
    df.to_csv(os.path.join(MODEL_DIR, "soil_dataset_labeled.csv"), index=False)

    counts = df["label"].value_counts().reindex(CLASSES, fill_value=0)
    print("Class distribution (after labelling):")
    for c in CLASSES:
        print(f"  {c:9s} {counts[c]:5d}  ({counts[c] / len(df) * 100:.1f}%)")
    print()

    X = df[FEATURES].values
    y = df["label"].values

    # 70% train / 15% validation / 15% test, stratified
    X_train, X_tmp, y_train, y_tmp = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=SEED)
    X_val, X_test, y_val, y_test = train_test_split(
        X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=SEED)
    print(f"Train: {len(X_train)} | Validation: {len(X_val)} | Test: {len(X_test)}\n")

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_leaf=2,
        class_weight="balanced",   # Healthy is the smallest class (~4%)
        random_state=SEED,
        n_jobs=-1,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="accuracy")
    print(f"5-fold CV accuracy (train set): {cv_scores.mean() * 100:.2f}% ± {cv_scores.std() * 100:.2f}%")

    model.fit(X_train, y_train)

    val_pred  = model.predict(X_val)
    test_pred = model.predict(X_test)
    val_acc   = accuracy_score(y_val, val_pred)
    test_acc  = accuracy_score(y_test, test_pred)
    test_f1   = f1_score(y_test, test_pred, average="macro")

    report = classification_report(y_test, test_pred, labels=CLASSES, digits=4)
    print(f"Validation accuracy: {val_acc * 100:.2f}%")
    print(f"Test accuracy:       {test_acc * 100:.2f}%")
    print(f"Test macro F1:       {test_f1 * 100:.2f}%\n")
    print("Classification report (test set):")
    print(report)

    importances = dict(zip(["pH", "Temperature", "EC", "Moisture"], model.feature_importances_))
    print("Feature importance:")
    for k, v in sorted(importances.items(), key=lambda kv: -kv[1]):
        print(f"  {k:12s} {v:.4f}")

    # ── Confusion matrix ──
    cm = confusion_matrix(y_test, test_pred, labels=CLASSES)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Greens",
                xticklabels=CLASSES, yticklabels=CLASSES, cbar=False)
    plt.title("Soil Random Forest — Confusion Matrix (Test Set)")
    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    plt.tight_layout()
    plt.savefig(os.path.join(MODEL_DIR, "soil_rf_confusion_matrix.png"), dpi=150)
    plt.close()

    # ── Feature importance ──
    items = sorted(importances.items(), key=lambda kv: kv[1])
    plt.figure(figsize=(6, 3.2))
    plt.barh([k for k, _ in items], [v for _, v in items], color="#16a34a")
    plt.title("Soil Random Forest — Feature Importance")
    plt.xlabel("Importance")
    plt.tight_layout()
    plt.savefig(os.path.join(MODEL_DIR, "soil_rf_feature_importance.png"), dpi=150)
    plt.close()

    # ── Save model + report ──
    # Range of each feature the model was trained on — fusion.py falls back to
    # the rules for readings outside it (the model never saw such values)
    train_range = {f: [float(X_train[:, i].min()), float(X_train[:, i].max())]
                   for i, f in enumerate(FEATURES)}
    print("\nTraining range (outside it, fusion.py uses the rules):")
    for f, (lo, hi) in train_range.items():
        print(f"  {f:12s} {lo:.2f} – {hi:.2f}")

    joblib.dump({"model": model, "features": FEATURES, "classes": list(model.classes_),
                 "train_range": train_range,
                 "ec_unit_in": "uS/cm (converted to dS/m before prediction)"},
                os.path.join(MODEL_DIR, "soil_rf.joblib"))

    with open(os.path.join(MODEL_DIR, "soil_rf_report.txt"), "w", encoding="utf-8") as f:
        f.write("SoCFA Soil Random Forest\n")
        f.write(f"Readings used: {len(df)} (from {n0})\n")
        for n in notes:
            f.write(f"  - {n}\n")
        f.write("Class distribution: " + json.dumps(counts.to_dict()) + "\n")
        f.write(f"Split: train {len(X_train)} / val {len(X_val)} / test {len(X_test)}\n")
        f.write(f"5-fold CV accuracy: {cv_scores.mean() * 100:.2f}% ± {cv_scores.std() * 100:.2f}%\n")
        f.write(f"Validation accuracy: {val_acc * 100:.2f}%\n")
        f.write(f"Test accuracy: {test_acc * 100:.2f}%\nTest macro F1: {test_f1 * 100:.2f}%\n\n")
        f.write(report + "\nFeature importance:\n")
        for k, v in sorted(importances.items(), key=lambda kv: -kv[1]):
            f.write(f"  {k:12s} {v:.4f}\n")

    print("\nSaved to model/:")
    print("  soil_rf.joblib, soil_rf_report.txt, soil_dataset_labeled.csv")
    print("  soil_rf_confusion_matrix.png, soil_rf_feature_importance.png")


if __name__ == "__main__":
    main()
