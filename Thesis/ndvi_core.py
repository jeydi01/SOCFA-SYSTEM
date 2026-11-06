"""
SoCFA — NDVI from the drone cameras (shared by app.py and the check/calibration scripts)
=========================================================================================
Two NDVI values are computed for every drone pair:

BLUE NDVI (NoIR photo only)
  Raspberry Pi NoIR Camera V2 with the supplied blue filter: the filter blocks
  red light, so the red channel records near-infrared and the blue channel
  records visible (blue) light.
      NDVI_blue = (NIR - Blue) / (NIR + Blue) = (R - B) / (R + B)   of the NoIR photo
  Blue is used instead of red, so values approximate standard NDVI.
  Both channels are linearised (JPEG gamma removed) and divided by the NoIR
  camera's red/blue colour gains (fixed by pi_capture.py, recorded per flight),
  so values are comparable between flights.

RED NDVI (NoIR + RGB photos, aligned with pair_align.py)
  Standard NDVI: near-infrared from the NoIR photo, red from the RGB photo.
      NDVI_red = (NIR - Red) / (NIR + Red)
  The two cameras have different settings and sensitivities, so each value is
  linearised (JPEG gamma removed), divided by that camera's exposure x gain x
  red colour gain (recorded by pi_capture.py), and NIR is scaled by a factor
  measured once on a white target (calibrate_red_ndvi.py). Without that
  calibration the values are marked "uncalibrated".

NDVI_SOURCE chooses which of the two decides the Healthy/Moderate/Poor class.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# NDVI classes (thesis Table 7, USGS / NASA ranges, gaps split at the midpoints).
# If check_ndvi_thresholds.py shows your camera reads differently, change them here.
NDVI_POOR_MAX     = 0.15   # below → Poor
NDVI_MODERATE_MAX = 0.55   # below → Moderate, at or above → Healthy

# Which NDVI decides the class: 'blue' (NoIR only) or 'red' (NoIR + RGB).
# Kept on 'blue' until field tests show red NDVI agrees better with the references.
NDVI_SOURCE = 'blue'

RED_CAL_FILE = os.path.join(HERE, 'red_ndvi_calibration.json')

CLASSES = ['healthy', 'moderate', 'poor']


def _linear(channel):
    """JPEG value 0–255 → approximately linear light (sRGB gamma removed)."""
    c = channel.astype(np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def ndvi_from_noir(noir_rgb, settings=None):
    """Per-pixel BLUE NDVI from a NoIR photo (RGB array, uint8). settings = the NoIR
    camera's recorded settings (colour gains); NaN where it can't be measured
    (overexposed or too dark)."""
    gains = (settings or {}).get('colour_gains') or [1.0, 1.0]
    r, b = noir_rgb[..., 0], noir_rgb[..., 2]
    nir = _linear(r) / gains[0]
    vis = _linear(b) / gains[1]
    ok = (r < 250) & (b < 250) & ((r.astype(np.int32) + b) > 10)
    ndvi = (nir - vis) / (nir + vis + 1e-12)
    return np.where(ok, ndvi, np.nan).astype(np.float32)


def class_shares(ndvi):
    """Share of pixels in each NDVI class (Table 7). Unmeasurable pixels (NaN) are left out."""
    valid = ndvi[~np.isnan(ndvi)] if np.isnan(ndvi).any() else ndvi
    if valid.size == 0:
        return {'healthy': 0.0, 'moderate': 0.0, 'poor': 0.0}
    return {
        'healthy':  float((valid >= NDVI_MODERATE_MAX).mean()),
        'moderate': float(((valid >= NDVI_POOR_MAX) & (valid < NDVI_MODERATE_MAX)).mean()),
        'poor':     float((valid < NDVI_POOR_MAX).mean()),
    }


# ── Red NDVI ─────────────────────────────────────────────────────────────────
def _camera_factor(settings):
    """Exposure x gains for the red channel; 1 when the flight has no recorded settings."""
    if not settings:
        return 1.0
    return (settings.get('exposure_us', 1) * settings.get('analogue_gain', 1.0)
            * settings.get('digital_gain', 1.0) * (settings.get('colour_gains') or [1.0])[0])


def load_red_calibration():
    try:
        with open(RED_CAL_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def red_bands(rgb_aligned, noir_aligned, cameras=None):
    """Linear, exposure-corrected NIR (NoIR red channel) and red (RGB red channel), plus
    a mask of pixels that can be measured (not overexposed, not too dark)."""
    cameras = cameras or {}
    nir = _linear(noir_aligned[..., 0]) / _camera_factor(cameras.get('noir'))
    red = _linear(rgb_aligned[..., 0]) / _camera_factor(cameras.get('rgb'))
    ok = ((noir_aligned[..., 0] < 250) & (rgb_aligned[..., 0] < 250)
          & ((noir_aligned[..., 0].astype(np.int32) + rgb_aligned[..., 0]) > 10))
    return nir, red, ok


def ndvi_red(rgb_aligned, noir_aligned, cameras=None):
    """Per-pixel RED NDVI (NaN where it can't be measured) and whether it is calibrated."""
    nir, red, ok = red_bands(rgb_aligned, noir_aligned, cameras)
    cal = load_red_calibration()
    nir = nir * (cal['nir_scale'] if cal else 1.0)
    ndvi = (nir - red) / (nir + red + 1e-12)
    ndvi = np.where(ok, np.clip(ndvi, -1, 1), np.nan).astype(np.float32)
    return ndvi, cal is not None and bool(cameras)
