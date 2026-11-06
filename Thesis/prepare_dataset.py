#!/usr/bin/env python3
"""
NDVI Dataset Preparation Script - NDVI Threshold Based
Uses ALL flight session data and classifies by actual NDVI values:
  healthy:  NDVI > 0.10
  moderate: NDVI -0.008 to 0.10
  poor:     NDVI < -0.008
"""

import os
import shutil
import glob
import random
import numpy as np
import cv2
from PIL import Image

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

SESSION_01 = r"C:\Users\facun\Downloads\Component 1 - part 1-2\Component 1 - part 1-2\flight_session_01\flight_session_01"
SESSION_02 = r"C:\Users\facun\Downloads\Component 1 - part 1-2\Component 1 - part 1-2\flight_session_02\filght_session_02"

OUTPUT_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset')
MAX_PER_CLASS = 500

# NDVI thresholds based on actual data distribution
NDVI_HEALTHY  =  0.1004  # top third
NDVI_MODERATE = -0.0078  # middle third
                          # below = poor

random.seed(42)

# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────

for cls in ['healthy', 'moderate', 'poor']:
    cls_dir = os.path.join(OUTPUT_DIR, cls)
    if os.path.exists(cls_dir):
        shutil.rmtree(cls_dir)
    os.makedirs(cls_dir)

print("=" * 65)
print("NDVI Dataset Preparation — Threshold Based")
print("=" * 65)
print(f"  healthy:  NDVI > {NDVI_HEALTHY}")
print(f"  moderate: NDVI {NDVI_MODERATE} to {NDVI_HEALTHY}")
print(f"  poor:     NDVI < {NDVI_MODERATE}")
print(f"  Output:   {OUTPUT_DIR}")
print()

totals = {'healthy': 0, 'moderate': 0, 'poor': 0}

# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

def save_ndvi_image(red_path, nir_path, out_path):
    red = np.array(Image.open(red_path)).astype(np.float32)
    nir = np.array(Image.open(nir_path)).astype(np.float32)

    if red.ndim == 3:
        red = red[:, :, 0]
    if nir.ndim == 3:
        nir = nir[:, :, 0]

    ndvi      = (nir - red) / (nir + red + 1e-8)
    ndvi_mean = float(np.mean(ndvi))

    ndvi_norm    = np.clip((ndvi + 1) / 2 * 255, 0, 255).astype(np.uint8)
    ndvi_resized = cv2.resize(ndvi_norm, (64, 64))
    ndvi_3ch     = cv2.merge([ndvi_resized, ndvi_resized, ndvi_resized])
    cv2.imwrite(out_path, ndvi_3ch)
    return ndvi_mean

# ─────────────────────────────────────────────
# PROCESS ALL SESSIONS
# ─────────────────────────────────────────────

all_sources = [
    (SESSION_01, ['2022-05-17', '2022-05-18']),
    (SESSION_02, ['2022-06-08', '2022-06-09']),
]

print("Processing all flight sessions...")
processed = 0
errors    = 0
skipped   = 0

for base_path, dates in all_sources:
    for date in dates:
        fplan_folders = sorted(glob.glob(os.path.join(base_path, date, '*FPLAN')))
        print(f"\n  {date}: {len(fplan_folders)} FPLAN folders")

        for fplan_folder in fplan_folders:
            # Stop if all classes full
            if all(totals[cls] >= MAX_PER_CLASS for cls in ['healthy', 'moderate', 'poor']):
                print("\nAll classes full — stopping.")
                break

            folder_name = os.path.basename(fplan_folder)
            jpg_files   = sorted(glob.glob(os.path.join(fplan_folder, '*.JPG')))

            for jpg_path in jpg_files:
                if all(totals[cls] >= MAX_PER_CLASS for cls in ['healthy', 'moderate', 'poor']):
                    break

                base_name = os.path.splitext(os.path.basename(jpg_path))[0]
                prefix    = base_name[:-1]
                red_path  = os.path.join(fplan_folder, prefix + '3.TIF')
                nir_path  = os.path.join(fplan_folder, prefix + '5.TIF')

                if not os.path.exists(red_path) or not os.path.exists(nir_path):
                    skipped += 1
                    continue

                try:
                    ndvi_mean = save_ndvi_image.__wrapped__ if hasattr(save_ndvi_image, '__wrapped__') else None

                    # Calculate NDVI to determine class
                    red = np.array(Image.open(red_path)).astype(np.float32)
                    nir = np.array(Image.open(nir_path)).astype(np.float32)
                    if red.ndim == 3: red = red[:, :, 0]
                    if nir.ndim == 3: nir = nir[:, :, 0]
                    ndvi      = (nir - red) / (nir + red + 1e-8)
                    ndvi_mean = float(np.mean(ndvi))

                    # Classify
                    if ndvi_mean > NDVI_HEALTHY:
                        label = 'healthy'
                    elif ndvi_mean > NDVI_MODERATE:
                        label = 'moderate'
                    else:
                        label = 'poor'

                    # Skip if class is full
                    if totals[label] >= MAX_PER_CLASS:
                        continue

                    # Save NDVI image
                    out_name = f"{date}_{folder_name}_{base_name}.png"
                    out_path = os.path.join(OUTPUT_DIR, label, out_name)

                    ndvi_norm    = np.clip((ndvi + 1) / 2 * 255, 0, 255).astype(np.uint8)
                    ndvi_resized = cv2.resize(ndvi_norm, (64, 64))
                    ndvi_3ch     = cv2.merge([ndvi_resized, ndvi_resized, ndvi_resized])
                    cv2.imwrite(out_path, ndvi_3ch)

                    totals[label] += 1
                    processed += 1
                    print(f"    [{totals[label]}/{MAX_PER_CLASS}] {base_name} → {label} (NDVI: {ndvi_mean:.4f})")

                except Exception as e:
                    print(f"    ERROR {base_name}: {e}")
                    errors += 1

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────

total = sum(totals.values())

print()
print("=" * 65)
print("DATASET PREPARATION COMPLETE")
print("=" * 65)
print(f"  Healthy:  {totals['healthy']} images  (NDVI > {NDVI_HEALTHY})")
print(f"  Moderate: {totals['moderate']} images  (NDVI {NDVI_MODERATE} to {NDVI_HEALTHY})")
print(f"  Poor:     {totals['poor']} images  (NDVI < {NDVI_MODERATE})")
print(f"  Skipped:  {skipped}")
print(f"  Errors:   {errors}")
print(f"  TOTAL:    {total} images")
print()

if any(v == 0 for v in totals.values()):
    print("WARNING: One or more classes have 0 images!")
elif any(v < MAX_PER_CLASS for v in totals.values()):
    print("WARNING: Some classes have less than 500 images!")
    print("Consider lowering MAX_PER_CLASS to match the smallest class.")
else:
    print("Ready to train!")
    print(f"Dataset saved to: {OUTPUT_DIR}")
    print("Next step: python train_ndvi_cnn.py")