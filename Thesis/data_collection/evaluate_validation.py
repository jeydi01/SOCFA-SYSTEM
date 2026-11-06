#!/usr/bin/env python3
"""
SoCFA — evaluate the field data (objectives 2, 3 and 4)
=======================================================
Reads the two logs filled in after each field day:

  validation_log.csv        one row per zone per visit: system results next to
                            the observer's crop rating (Healthy/Moderate/Poor)
  sensor_reference_log.csv  one row per sensor check: sensor value next to the
                            reference (meter / thermometer / lab)

and writes the results to data_collection/results/:

  results_summary.md            all tables, ready to copy into the paper
  crop_condition_metrics.csv    accuracy / kappa per method
  sensor_accuracy.csv           MAE / RMSE / bias / % error / r per parameter
  confusion_<method>.png        confusion matrices
  sensor_<parameter>.png        sensor vs reference scatter plots
  ndvi_vs_reference.png         camera NDVI vs Sentinel-2 / handheld NDVI
  validation_log_filled.csv     the log with NDVI/CNN/drone columns filled in

NDVI / CNN / drone columns left blank are filled from the flight name
(captures/<flight>/auto_result.json). If the flight is blank, the flight is
found from the date + spot typed on the NDVI page before Take Photos (the
latest flight that day with that spot).

Run:   python data_collection/evaluate_validation.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (accuracy_score, cohen_kappa_score, confusion_matrix,
                             precision_recall_fscore_support)

HERE = os.path.dirname(os.path.abspath(__file__))
THESIS = os.path.dirname(HERE)
CAPTURES = os.path.join(THESIS, "captures")
RESULTS = os.path.join(HERE, "results")
CLASSES = ["Healthy", "Moderate", "Poor"]

# system outputs compared with the observer's rating (the ground truth)
METHODS = [
    ("final_class", "Final result (soil + drone)"),
    ("drone_class", "Drone (NDVI + CNN)"),
    ("ndvi_class",  "NDVI only (NoIR)"),
    ("cnn_class",   "CNN only (RGB)"),
    ("soil_class",  "Soil only (sensor nodes)"),
]
SENSOR_PARAMS = [
    ("ph",           "pH",               ""),
    ("ec_uscm",      "EC",               "µS/cm"),
    ("moisture_pct", "Soil moisture",    "%"),
    ("temp_c",       "Soil temperature", "°C"),
]


def norm_class(v):
    """'H', 'healthy', 'Healthy ' → 'Healthy'; blank → NaN."""
    if pd.isna(v) or str(v).strip() == "":
        return np.nan
    s = str(v).strip().lower()
    for c in CLASSES:
        if s == c.lower() or s == c[0].lower():
            return c
    return np.nan


def norm_spot(spot):
    """'a-03 ' -> 'A-03' (same cleaning as the NDVI page)."""
    return "".join(c for c in str(spot).strip().upper() if c.isalnum() or c in "_-")


def flight_spots():
    """{(yyyymmdd, spot): latest flight} from captures/<flight>/pairs.json."""
    found = {}
    for name in sorted(os.listdir(CAPTURES)) if os.path.isdir(CAPTURES) else []:
        path = os.path.join(CAPTURES, name, "pairs.json")
        if not name.startswith("flight_") or not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            spot = norm_spot(json.load(f).get("spot") or "")
        if spot:
            found[(name.split("_")[1], spot)] = name      # sorted → later flights win
    return found


def fill_from_flights(log):
    """Fill blank flight (from date + spot) and NDVI / CNN / drone columns
    from captures/<flight>/auto_result.json."""
    filled = 0
    spots = flight_spots()
    for col in ["flight", "spot", "observer_class", "ndvi_mean", "lcc_mean", "sentinel_ndvi",
                "handheld_ndvi"] + [c for c, _ in METHODS]:          # older logs may lack some
        if col not in log.columns:
            log[col] = np.nan
    for i, row in log.iterrows():
        flight = str(row.get("flight", "")).strip()
        if not flight or flight == "nan":
            day = str(row.get("date", "")).strip().replace("-", "")
            spot = norm_spot(row.get("spot", "") if pd.notna(row.get("spot")) else "")
            flight = spots.get((day, spot), "") if spot else ""
            if flight:
                log.at[i, "flight"] = flight
                filled += 1
        path = os.path.join(CAPTURES, flight, "auto_result.json")
        if not flight or flight == "nan" or not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        shares, cnn = r.get("ndvi_shares") or {}, r.get("cnn_probabilities") or {}
        values = {
            "ndvi_class": max(shares, key=shares.get).capitalize() if shares else np.nan,
            "ndvi_mean":  r.get("ndvi_value"),
            "cnn_class":  max(cnn, key=cnn.get).capitalize() if cnn else np.nan,
            "drone_class": str(r.get("health_class", "")).capitalize() or np.nan,
        }
        for col, val in values.items():
            if pd.isna(log.at[i, col]) or str(log.at[i, col]).strip() == "":
                log.at[i, col] = val
                filled += 1
    return filled


def plot_confusion(cm, title, path):
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    ax.imshow(cm, cmap="Greens")
    ax.set_xticks(range(3), CLASSES); ax.set_yticks(range(3), CLASSES)
    ax.set_xlabel("System"); ax.set_ylabel("Observer (field rating)")
    for (y, x), n in np.ndenumerate(cm):
        ax.text(x, y, int(n), ha="center", va="center", color="white" if n > cm.max() / 2 else "black")
    ax.set_title(title, fontsize=10)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def scatter(x, y, xlabel, ylabel, title, path):
    fig, ax = plt.subplots(figsize=(4.2, 4))
    ax.scatter(x, y, s=22, color="#1f7a4d")
    lo, hi = float(min(x.min(), y.min())), float(max(x.max(), y.max()))
    pad = (hi - lo) * 0.05 or 1
    ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], "--", color="#888", lw=1, label="1:1 line")
    if len(x) >= 2 and np.ptp(x) > 0:
        a, b = np.polyfit(x, y, 1)
        xx = np.array([lo - pad, hi + pad]); ax.plot(xx, a * xx + b, color="#c0392b", lw=1, label=f"fit: y = {a:.2f}x + {b:.2f}")
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(title, fontsize=10); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def evaluate_crop(log, md):
    log = log.copy()
    for col, _ in METHODS + [("observer_class", "")]:
        log[col] = log[col].map(norm_class)
    rows = []
    md.append("## Crop condition: system vs. field rating (objectives 3 and 4)\n")
    md.append(f"Observations with a field rating: **{log['observer_class'].notna().sum()}**  \n"
              "Field rating distribution: " + ", ".join(f"{c} {int((log['observer_class'] == c).sum())}" for c in CLASSES) + "\n")
    md.append("| Method | n | Accuracy | Cohen's kappa | Macro F1 |\n|---|---|---|---|---|")
    for col, label in METHODS:
        d = log[["observer_class", col]].dropna()
        if d.empty:
            md.append(f"| {label} | 0 | – | – | – |")
            continue
        acc = accuracy_score(d["observer_class"], d[col])
        kap = cohen_kappa_score(d["observer_class"], d[col], labels=CLASSES) if d["observer_class"].nunique() > 1 or d[col].nunique() > 1 else float("nan")
        p, r, f, s = precision_recall_fscore_support(d["observer_class"], d[col], labels=CLASSES, zero_division=0)
        rows.append({"method": label, "n": len(d), "accuracy": round(acc, 4), "kappa": round(kap, 4),
                     "macro_f1": round(float(np.mean(f)), 4),
                     **{f"recall_{c}": round(float(x), 4) for c, x in zip(CLASSES, r)},
                     **{f"precision_{c}": round(float(x), 4) for c, x in zip(CLASSES, p)}})
        md.append(f"| {label} | {len(d)} | {acc * 100:.1f}% | {kap:.3f} | {np.mean(f) * 100:.1f}% |")
        cm = confusion_matrix(d["observer_class"], d[col], labels=CLASSES)
        plot_confusion(cm, label, os.path.join(RESULTS, f"confusion_{col.replace('_class', '')}.png"))
    md.append("\nKappa: < 0.20 slight · 0.21–0.40 fair · 0.41–0.60 moderate · 0.61–0.80 substantial · > 0.80 almost perfect agreement (Landis & Koch, 1977).\n")
    if rows:
        pd.DataFrame(rows).to_csv(os.path.join(RESULTS, "crop_condition_metrics.csv"), index=False)

    # NDVI vs LCC and vs reference NDVI
    md.append("## NDVI agreement\n")
    md.append("| Comparison | n | Pearson r | Mean abs. difference |\n|---|---|---|---|")
    for ref, label in [("lcc_mean", "Camera NDVI vs. LCC reading"),
                       ("sentinel_ndvi", "Camera NDVI vs. Sentinel-2 NDVI"),
                       ("handheld_ndvi", "Camera NDVI vs. handheld NDVI meter")]:
        d = log[["ndvi_mean", ref]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(d) < 3:
            md.append(f"| {label} | {len(d)} | – | – |")
            continue
        r = np.corrcoef(d["ndvi_mean"], d[ref])[0, 1]
        mad = "–" if ref == "lcc_mean" else f"{(d['ndvi_mean'] - d[ref]).abs().mean():.3f}"
        md.append(f"| {label} | {len(d)} | {r:.3f} | {mad} |")
        if ref != "lcc_mean":
            scatter(d[ref], d["ndvi_mean"], label.split("vs. ")[1], "Camera NDVI (NoIR)", label,
                    os.path.join(RESULTS, f"ndvi_vs_{ref.replace('_ndvi', '')}.png"))
    md.append("")


def evaluate_sensors(slog, md):
    md.append("## Soil sensor accuracy (objective 2)\n")
    md.append("| Parameter | n | Mean sensor | Mean reference | Bias (sensor − ref) | MAE | RMSE | Mean abs. % error | Pearson r |\n"
              "|---|---|---|---|---|---|---|---|---|")
    rows = []
    for key, label, unit in SENSOR_PARAMS:
        d = slog[[f"sensor_{key}", f"ref_{key}"]].apply(pd.to_numeric, errors="coerce").dropna()
        if d.empty:
            md.append(f"| {label} | 0 | – | – | – | – | – | – | – |")
            continue
        s, ref = d[f"sensor_{key}"], d[f"ref_{key}"]
        diff = s - ref
        mape = (diff.abs() / ref.abs().replace(0, np.nan)).mean() * 100
        r = np.corrcoef(s, ref)[0, 1] if len(d) >= 3 and s.std() > 0 and ref.std() > 0 else float("nan")
        row = {"parameter": label, "unit": unit, "n": len(d), "mean_sensor": s.mean(), "mean_ref": ref.mean(),
               "bias": diff.mean(), "mae": diff.abs().mean(), "rmse": float(np.sqrt((diff ** 2).mean())),
               "mape_pct": mape, "pearson_r": r}
        rows.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})
        u = f" {unit}" if unit else ""
        md.append(f"| {label} | {len(d)} | {s.mean():.2f}{u} | {ref.mean():.2f}{u} | {diff.mean():+.2f}{u} | "
                  f"{diff.abs().mean():.2f}{u} | {row['rmse']:.2f}{u} | {mape:.1f}% | {r:.3f} |")
        if len(d) >= 2:
            scatter(ref, s, f"Reference {label}{u}", f"Sensor {label}{u}", f"{label}: sensor vs. reference",
                    os.path.join(RESULTS, f"sensor_{key}.png"))
    if rows:
        pd.DataFrame(rows).to_csv(os.path.join(RESULTS, "sensor_accuracy.csv"), index=False)

    # reliability: how consistent the error is per node
    per_node = []
    for key, label, _ in SENSOR_PARAMS:
        d = slog[["node_id", f"sensor_{key}", f"ref_{key}"]].copy()
        d[[f"sensor_{key}", f"ref_{key}"]] = d[[f"sensor_{key}", f"ref_{key}"]].apply(pd.to_numeric, errors="coerce")
        d = d.dropna()
        for node, g in d.groupby("node_id"):
            diff = g[f"sensor_{key}"] - g[f"ref_{key}"]
            per_node.append(f"| {node} | {label} | {len(g)} | {diff.mean():+.2f} | {diff.std(ddof=1) if len(g) > 1 else float('nan'):.2f} |")
    if per_node:
        md.append("\n**Reliability per node** (spread of the error over repeated checks; smaller = more consistent)\n")
        md.append("| Node | Parameter | n | Mean error | Std. dev. of error |\n|---|---|---|---|---|")
        md.extend(per_node)
    md.append("")


def main():
    os.makedirs(RESULTS, exist_ok=True)
    md = ["# SoCFA field validation results\n"]

    vpath = os.path.join(HERE, "validation_log.csv")
    log = pd.read_csv(vpath, dtype=str) if os.path.isfile(vpath) else pd.DataFrame()
    if log.empty:
        md.append("_validation_log.csv has no rows yet._\n")
        print("validation_log.csv: no rows yet")
    else:
        n = fill_from_flights(log)
        log.to_csv(os.path.join(RESULTS, "validation_log_filled.csv"), index=False)
        print(f"validation_log.csv: {len(log)} rows ({n} values filled from flights)")
        evaluate_crop(log, md)

    spath = os.path.join(HERE, "sensor_reference_log.csv")
    slog = pd.read_csv(spath, dtype=str) if os.path.isfile(spath) else pd.DataFrame()
    if slog.empty:
        md.append("_sensor_reference_log.csv has no rows yet._\n")
        print("sensor_reference_log.csv: no rows yet")
    else:
        print(f"sensor_reference_log.csv: {len(slog)} rows")
        evaluate_sensors(slog, md)

    out = os.path.join(RESULTS, "results_summary.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Results written to {RESULTS}")


if __name__ == "__main__":
    sys.exit(main())
