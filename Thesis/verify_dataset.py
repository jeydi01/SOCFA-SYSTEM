#!/usr/bin/env python3
"""
NDVI Field Category Verification Script
Uses flight_session_02 / 2022-06-09 / 100FPLAN images.
Calculates real NDVI from TIF bands, classifies them,
then runs through the CNN model and generates a paper table.
50 images total.
"""

import os
import numpy as np
import cv2
import csv
import tensorflow as tf
from PIL import Image
import glob

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

FPLAN_PATH = r"C:\Users\facun\Downloads\Component 1 - part 1-2\Component 1 - part 1-2\flight_session_02\filght_session_02\2022-06-09\100FPLAN"

MODEL_PATH = 'model/ndvi_cnn_best.h5'
CLASSES    = ['healthy', 'moderate', 'poor']
IMAGE_SIZE = (64, 64)
OUTPUT_CSV = 'field_categories_table.csv'

# NDVI thresholds for June 2022 (range: 0.05 to 0.177)
NDVI_HEALTHY  = 0.15   # NDVI > 0.15        → healthy
NDVI_MODERATE = 0.10   # NDVI 0.10 to 0.15  → moderate
                        # NDVI < 0.10        → poor

# Total images to test — will try to balance across 3 classes
TOTAL_SAMPLES = 50

# ─────────────────────────────────────────────
# LOAD MODEL
# ─────────────────────────────────────────────

print("=" * 70)
print("NDVI Field Category Verification — June 9, 2022 | 100FPLAN")
print("=" * 70)
print()
print("Loading CNN model...")
model = tf.keras.models.load_model(MODEL_PATH)
print("Model loaded!")
print()

# ─────────────────────────────────────────────
# STEP 1 — CALCULATE NDVI FROM TIF BANDS
# ─────────────────────────────────────────────

print("Step 1: Calculating NDVI from TIF bands...")
print()

jpg_files = sorted(glob.glob(os.path.join(FPLAN_PATH, '*.JPG')))
classified = {'healthy': [], 'moderate': [], 'poor': []}

for jpg_path in jpg_files:
    base_name = os.path.splitext(os.path.basename(jpg_path))[0]
    prefix    = base_name[:-1]

    red_path = os.path.join(FPLAN_PATH, prefix + '3.TIF')
    nir_path = os.path.join(FPLAN_PATH, prefix + '5.TIF')

    if not os.path.exists(red_path) or not os.path.exists(nir_path):
        continue

    try:
        red  = np.array(Image.open(red_path)).astype(np.float32)
        nir  = np.array(Image.open(nir_path)).astype(np.float32)
        ndvi = (nir - red) / (nir + red + 1e-8)
        ndvi_mean = float(np.mean(ndvi))

        if ndvi_mean > NDVI_HEALTHY:
            label = 'healthy'
        elif ndvi_mean > NDVI_MODERATE:
            label = 'moderate'
        else:
            label = 'poor'

        classified[label].append((jpg_path, ndvi_mean))

    except Exception as e:
        print(f"  Error processing {base_name}: {e}")

print("Images found per class:")
for cls in CLASSES:
    print(f"  {cls:<12}: {len(classified[cls])} images")
print()

# ─────────────────────────────────────────────
# STEP 2 — PICK 50 SAMPLES (balanced)
# ─────────────────────────────────────────────

# Try to get equal samples per class
per_class = TOTAL_SAMPLES // len(CLASSES)  # ~17 each

test_images = []
for cls in CLASSES:
    samples = classified[cls][:per_class]
    for jpg_path, ndvi_mean in samples:
        test_images.append((jpg_path, cls, ndvi_mean))

# Fill remaining slots if one class has fewer images
remaining = TOTAL_SAMPLES - len(test_images)
if remaining > 0:
    for cls in CLASSES:
        extra = classified[cls][per_class:per_class + remaining]
        for jpg_path, ndvi_mean in extra:
            test_images.append((jpg_path, cls, ndvi_mean))
        if len(test_images) >= TOTAL_SAMPLES:
            break

print(f"Step 2: Selected {len(test_images)} images for testing")
print()

# ─────────────────────────────────────────────
# STEP 3 — CNN PREDICTION
# ─────────────────────────────────────────────

results = []
correct = 0
total   = 0

print(f"{'No.':<5} {'Image':<22} {'NDVI':>8} {'True Label':<12} {'Predicted':<12} {'Confidence':>10}  {'Result'}")
print("-" * 80)

for idx, (jpg_path, true_label, ndvi_mean) in enumerate(test_images, 1):
    filename = os.path.basename(jpg_path)

    try:
        # Load JPG for CNN input
        img = cv2.imread(jpg_path)
        img = cv2.resize(img, IMAGE_SIZE)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_input = np.expand_dims(img.astype(np.float32) / 255.0, axis=0)

        # Predict
        predictions     = model.predict(img_input, verbose=0)[0]
        predicted_idx   = np.argmax(predictions)
        predicted_label = CLASSES[predicted_idx]
        confidence      = float(np.max(predictions))

        is_correct = predicted_label == true_label
        if is_correct:
            correct += 1
            status = 'CORRECT'
        else:
            status = 'WRONG'

        total += 1

        results.append({
            'No':                idx,
            'Image File':        filename,
            'NDVI Value':        f"{ndvi_mean:.4f}",
            'True Label':        true_label,
            'Predicted Label':   predicted_label,
            'Confidence (%)':    f"{confidence * 100:.1f}%",
            'Healthy Prob (%)':  f"{predictions[0] * 100:.1f}%",
            'Moderate Prob (%)': f"{predictions[1] * 100:.1f}%",
            'Poor Prob (%)':     f"{predictions[2] * 100:.1f}%",
            'Correct':           'Yes' if is_correct else 'No'
        })

        short = filename[:20] + '..' if len(filename) > 20 else filename
        print(f"{idx:<5} {short:<22} {ndvi_mean:>8.4f} {true_label:<12} {predicted_label:<12} {confidence*100:>9.1f}%  {status}")

    except Exception as e:
        print(f"{idx:<5} ERROR: {e}")

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────

accuracy = (correct / total * 100) if total > 0 else 0

print("-" * 80)
print()
print("=" * 70)
print("FIELD CATEGORY SUMMARY")
print("=" * 70)
print(f"  Flight Session:  02  |  Date: June 9, 2022  |  Folder: 100FPLAN")
print(f"  NDVI Thresholds: Healthy > {NDVI_HEALTHY} | Moderate {NDVI_MODERATE}–{NDVI_HEALTHY} | Poor < {NDVI_MODERATE}")
print(f"  Total Tested:    {total} images")
print(f"  Correct:         {correct} images")
print(f"  Overall Accuracy:{accuracy:.1f}%")
print()
print("Per-class results:")
print(f"  {'Class':<12} {'Tested':>8} {'Correct':>8} {'Accuracy':>10} {'Avg NDVI':>10}")
print(f"  {'-'*52}")
for cls in CLASSES:
    cls_results = [r for r in results if r['True Label'] == cls]
    cls_correct = sum(1 for r in cls_results if r['Correct'] == 'Yes')
    cls_total   = len(cls_results)
    cls_acc     = (cls_correct / cls_total * 100) if cls_total > 0 else 0
    ndvi_vals   = [float(r['NDVI Value']) for r in cls_results]
    avg_ndvi    = sum(ndvi_vals) / len(ndvi_vals) if ndvi_vals else 0
    print(f"  {cls:<12} {cls_total:>8} {cls_correct:>8} {cls_acc:>9.1f}% {avg_ndvi:>10.4f}")

# ─────────────────────────────────────────────
# SAVE CSV
# ─────────────────────────────────────────────

with open(OUTPUT_CSV, 'w', newline='') as f:
    fieldnames = [
        'No', 'Image File', 'NDVI Value', 'True Label', 'Predicted Label',
        'Confidence (%)', 'Healthy Prob (%)', 'Moderate Prob (%)',
        'Poor Prob (%)', 'Correct'
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

    # Summary rows
    writer.writerow({})
    writer.writerow({
        'No': '', 'Image File': 'SUMMARY',
        'NDVI Value': '', 'True Label': '',
        'Predicted Label': '', 'Confidence (%)': '',
        'Healthy Prob (%)': '', 'Moderate Prob (%)': '',
        'Poor Prob (%)': '', 'Correct': ''
    })
    writer.writerow({
        'No': '', 'Image File': f'Total Tested: {total}',
        'NDVI Value': '', 'True Label': '',
        'Predicted Label': f'Correct: {correct}',
        'Confidence (%)': f'Accuracy: {accuracy:.1f}%',
        'Healthy Prob (%)': f'Healthy > {NDVI_HEALTHY}',
        'Moderate Prob (%)': f'Moderate {NDVI_MODERATE}-{NDVI_HEALTHY}',
        'Poor Prob (%)': f'Poor < {NDVI_MODERATE}',
        'Correct': ''
    })

print()
print(f"Table saved to: {OUTPUT_CSV}")
print("Open in Excel and copy into your paper!")