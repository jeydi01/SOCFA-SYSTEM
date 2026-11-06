"""
SoCFA — Combined crop condition (Soil Random Forest + NDVI CNN)
================================================================
The two models are trained separately (different data sources), so their
results are combined AFTER prediction ("late fusion"):

    1. Each model gives class probabilities for Healthy / Moderate / Poor.
    2. Each is turned into a health score from 0 to 1:
           score = 1.0 × P(Healthy) + 0.5 × P(Moderate) + 0.0 × P(Poor)
    3. Final score = W_NDVI × NDVI score + W_SOIL × soil score
    4. Final class:  score ≥ 2/3 → Healthy
                     score ≥ 1/3 → Moderate
                     otherwise   → Poor

One drone capture covers one zone, and every soil node in that zone is
classified separately; the zone's soil result is the mean of the node
probabilities, so the zone gets ONE final result.

Usage:
    from fusion import predict_soil, predict_soil_zone, combine
    soil = predict_soil(ph=6.4, temperature=28.5, ec_uScm=150, moisture=55)
    zone = predict_soil_zone([{"node_id": "1", "ph": 6.4, "temperature": 28.5,
                               "ec": 150, "humidity": 55}, ...])
    final = combine(zone["probabilities"], ndvi_probabilities)
"""

import os
import joblib
import numpy as np

from soil_rules import label_row

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model", "soil_rf.joblib")

W_NDVI = 0.5      # weight of the aerial NDVI result
W_SOIL = 0.5      # weight of the soil sensor result
HEALTHY_MIN  = 2 / 3   # 0–1 score split into three equal intervals
MODERATE_MIN = 1 / 3
CLASSES = ["Healthy", "Moderate", "Poor"]

_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def outside_training_range(values, train_range):
    """Features whose value is outside what the Random Forest was trained on."""
    return [f for f, v in values.items()
            if f in train_range and not (train_range[f][0] <= v <= train_range[f][1])]


def predict_soil(ph, temperature, ec_uScm, moisture):
    """Classify one soil reading. EC comes from the sensor in µS/cm.

    Safety check: the Random Forest only knows the values it was trained on.
    A reading outside that range (e.g. soil hotter than any training reading)
    is classified by the reference rules instead (soil_rules.py)."""
    b = _load()
    values = {"ph": ph, "temperature": temperature, "ec_dsm": ec_uScm / 1000.0, "moisture": moisture}  # µS/cm → dS/m
    outside = outside_training_range(values, b.get("train_range", {}))

    if outside:
        label = label_row(ph, temperature, values["ec_dsm"], moisture)
        prob_map = {c: 1.0 if c == label else 0.0 for c in CLASSES}
        return {"label": label, "confidence": 1.0, "probabilities": prob_map,
                "method": "rules", "outside_range": outside}

    x = np.array([[values[f] for f in b["features"]]])
    probs = b["model"].predict_proba(x)[0]
    prob_map = {c: float(p) for c, p in zip(b["classes"], probs)}
    prob_map = {c: prob_map.get(c, 0.0) for c in CLASSES}
    label = max(prob_map, key=prob_map.get)
    return {"label": label, "confidence": prob_map[label], "probabilities": prob_map,
            "method": "random_forest", "outside_range": []}


def predict_soil_zone(readings):
    """Classify every node in the drone's zone; the zone result is the mean of the
    node probabilities (same as the CNN, which averages its tile probabilities).
    readings: [{'node_id', 'ph', 'temperature', 'ec' (µS/cm), 'humidity'}, ...]"""
    nodes = [{**r, **predict_soil(r["ph"], r["temperature"], r["ec"], r["humidity"])}
             for r in readings]
    prob_map = {c: float(np.mean([n["probabilities"][c] for n in nodes])) for c in CLASSES}
    label = max(prob_map, key=prob_map.get)
    return {"label": label, "confidence": prob_map[label],
            "probabilities": prob_map, "nodes": nodes}


def health_score(probs):
    """Probabilities → 0..1 score (1 = fully healthy)."""
    p = {k.capitalize(): v for k, v in probs.items()}   # accepts 'healthy' or 'Healthy'
    return 1.0 * p.get("Healthy", 0) + 0.5 * p.get("Moderate", 0) + 0.0 * p.get("Poor", 0)


def score_to_class(score):
    if score >= HEALTHY_MIN:
        return "Healthy"
    if score >= MODERATE_MIN:
        return "Moderate"
    return "Poor"


def combine(soil_probs, ndvi_probs, w_ndvi=W_NDVI, w_soil=W_SOIL):
    """Late fusion of the soil RF and NDVI CNN outputs."""
    s_soil = health_score(soil_probs)
    s_ndvi = health_score(ndvi_probs)
    total = (w_ndvi * s_ndvi + w_soil * s_soil) / (w_ndvi + w_soil)
    return {
        "final_class": score_to_class(total),
        "final_score": round(total, 3),
        "soil_score":  round(s_soil, 3),
        "ndvi_score":  round(s_ndvi, 3),
        "weights":     {"ndvi": w_ndvi, "soil": w_soil},
    }


if __name__ == "__main__":
    # Quick demo with made-up NDVI probabilities
    soil = predict_soil(ph=6.4, temperature=28.5, ec_uScm=150, moisture=55)
    print("Soil RF:", soil)
    ndvi = {"healthy": 0.20, "moderate": 0.70, "poor": 0.10}
    print("NDVI CNN:", ndvi)
    print("Combined:", combine(soil["probabilities"], ndvi))
