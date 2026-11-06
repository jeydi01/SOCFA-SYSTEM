"""
SoCFA — Soil rating rules (shared by train_soil_rf.py and fusion.py)
====================================================================
Each parameter is rated Healthy / Moderate / Poor (2 / 1 / 0), then the
maximum limitation method combines them: the worst parameter decides.
Keep in sync with soil.js and field.html.
"""

# 2 = Healthy, 1 = Moderate, 0 = Poor
def rate_ph(v):
    # Table 3: 6.5–7.5 neutral; acidic or alkaline = Moderate (no Poor class)
    if 6.5 <= v <= 7.5:                       return 2
    return 1

def rate_temperature(v):
    # Table 6 (°F converted): ≤90 °F ok, 90–100 °F growth slows, >100 °F moisture lost
    if v <= 32.2:                             return 2
    if v <= 37.8:                             return 1
    return 0

def rate_ec(v_dsm):
    # Table 4: <2 non-saline, 2–8 very slightly / slightly saline,
    # ≥8 moderately–strongly saline
    if v_dsm < 2.0:                           return 2
    if v_dsm < 8.0:                           return 1
    return 0

# Soil moisture for palay (lowland rice) on Bulaoen clay loam, volumetric %
WILTING_POINT = 24.0   # clay loam (Easton & Bock, 2021)
SATURATION    = 46.4   # clay loam porosity (Rawls et al., 1982) — PROVISIONAL: verify or measure in the field
P_RICE        = 0.20   # rice: allowable depletion = 0.20 of saturation (FAO-56, Table 22)
MOISTURE_HEALTHY_MIN = SATURATION - P_RICE * (SATURATION - WILTING_POINT)   # ≈ 41.9 %

def rate_moisture(v):
    # ≥ 41.9 near saturation (no irrigation), 24–41.9 drying (irrigate),
    # ≤ 24 at or below wilting point (dangerously low)
    if v >= MOISTURE_HEALTHY_MIN:             return 2
    if v > WILTING_POINT:                     return 1
    return 0

def probe_not_in_soil(moisture, ec):
    """Exactly 0 % moisture or 0 EC: the probe is not in contact with the soil
    (real soil, even very dry, always reads above 0). Not a soil condition."""
    return moisture <= 0 or ec <= 0

def label_row(ph, temp, ec_dsm, moist):
    # Maximum limitation method: the worst parameter decides
    worst = min(rate_ph(ph), rate_temperature(temp),
                rate_ec(ec_dsm), rate_moisture(moist))
    return {2: "Healthy", 1: "Moderate", 0: "Poor"}[worst]
