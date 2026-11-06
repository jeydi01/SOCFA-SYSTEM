#!/usr/bin/env python3
"""
SoCFA — check the NDVI thresholds against your own NoIR camera
==============================================================
Blue NDVI from the NoIR camera usually reads lower than standard NDVI, so this
checks whether the Table 7 thresholds in ndvi_core.py fit your camera.

1. With the drone (or by hand, same height and light as a real flight), take
   NoIR photos of clearly known surfaces and sort them into folders:

       ndvi_reference/
           healthy_palay/   photos of clearly healthy, dense palay
           bare_soil/       photos of bare soil (dry or wet)
           water/           photos of open water (optional)

   Crop the photos so each shows mostly that one surface. A few photos per
   folder is enough; more is better.

2. Run:   python check_ndvi_thresholds.py            (or give another folder)

It prints the NDVI of each group, how the current thresholds classify it, and
suggested thresholds if they do not fit. Report the result in the paper.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

from ndvi_core import ndvi_from_noir, class_shares, NDVI_POOR_MAX, NDVI_MODERATE_MAX

HERE = os.path.dirname(os.path.abspath(__file__))
REF_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'ndvi_reference')
GROUPS = {   # folder → what it should be classified as
    'healthy_palay': 'healthy',
    'bare_soil':     'poor',
    'water':         'poor',
}
EXTS = ('*.jpg', '*.jpeg', '*.png')


def load_group(folder):
    files = sorted({f for e in EXTS for f in glob.glob(os.path.join(folder, e))} |
                   {f for e in EXTS for f in glob.glob(os.path.join(folder, e.upper()))})
    values, dark, clipped, total = [], 0, 0, 0
    for f in files:
        img = np.array(Image.open(f).convert('RGB'))
        r, b = img[..., 0].astype(np.int32), img[..., 2].astype(np.int32)
        dark    += int(((r + b) < 30).sum())                 # too dark to measure well
        clipped += int(((r >= 255) | (b >= 255)).sum())      # overexposed
        total   += r.size
        v = ndvi_from_noir(img).ravel()
        values.append(v[~np.isnan(v)])            # leave out overexposed / too-dark pixels
    return files, (np.concatenate(values) if values else None), dark, clipped, total


def main():
    if not os.path.isdir(REF_DIR):
        sys.exit(f'Folder not found: {REF_DIR}\nCreate it with sub-folders: {", ".join(GROUPS)}')

    print('=' * 64)
    print('SoCFA — NDVI threshold check (NoIR camera, blue NDVI)')
    print(f'Current thresholds (ndvi_core.py): Poor < {NDVI_POOR_MAX}, '
          f'Moderate {NDVI_POOR_MAX}–{NDVI_MODERATE_MAX}, Healthy ≥ {NDVI_MODERATE_MAX}')
    print('=' * 64)

    data = {}
    for group, expected in GROUPS.items():
        files, ndvi, dark, clipped, total = load_group(os.path.join(REF_DIR, group))
        if ndvi is None:
            print(f'\n{group}: no photos (skipped)')
            continue
        data[group] = ndvi
        p10, p25, p50, p75, p90 = np.percentile(ndvi, [10, 25, 50, 75, 90])
        s = class_shares(ndvi)
        print(f'\n{group}  ({len(files)} photo(s), should be {expected.upper()})')
        print(f'  NDVI  mean {ndvi.mean():.3f} | 10% {p10:.3f}  25% {p25:.3f}  median {p50:.3f}  '
              f'75% {p75:.3f}  90% {p90:.3f}')
        print(f'  Current thresholds classify it as: Healthy {s["healthy"]*100:.0f}%  '
              f'Moderate {s["moderate"]*100:.0f}%  Poor {s["poor"]*100:.0f}%  '
              f'→ {s[expected]*100:.0f}% as expected')
        if dark / total > 0.05 or clipped / total > 0.02:
            print(f'  ⚠ photo quality: {dark/total*100:.0f}% too dark, {clipped/total*100:.0f}% overexposed '
                  '— retake in better light or adjust exposure')

    if 'healthy_palay' not in data:
        sys.exit('\nNeed at least the healthy_palay folder to judge the thresholds.')

    healthy_ok = class_shares(data['healthy_palay'])['healthy']
    bare = [data[g] for g in ('bare_soil', 'water') if g in data]
    bare_ok = class_shares(np.concatenate(bare))['poor'] if bare else None

    print('\n' + '-' * 64)
    print(f'Healthy palay classified Healthy: {healthy_ok*100:.0f}%'
          + (f' | Bare soil/water classified Poor: {bare_ok*100:.0f}%' if bare_ok is not None else ''))

    fits = healthy_ok >= 0.70 and (bare_ok is None or bare_ok >= 0.70)
    if fits:
        print('→ The Table 7 thresholds fit this camera. Keep them, and report these numbers.')
        return

    # Suggested camera-specific thresholds: Healthy starts where most healthy-palay
    # pixels are (25th percentile); Poor ends above most soil/water pixels (90th).
    healthy_min = float(np.percentile(data['healthy_palay'], 25))
    poor_max = float(np.percentile(np.concatenate(bare), 90)) if bare else NDVI_POOR_MAX
    print('→ The Table 7 thresholds do NOT fit this camera well.')
    if poor_max < healthy_min:
        print(f'  Suggested for this camera:  NDVI_POOR_MAX = {poor_max:.2f}   NDVI_MODERATE_MAX = {healthy_min:.2f}')
        print('  (Healthy from the 25th percentile of healthy palay; Poor below the 90th percentile of soil/water.)')
        print('  To use them, change the two values in ndvi_core.py and restart app.py.')
    else:
        print('  Healthy palay and soil/water overlap too much to separate them — check the blue filter,')
        print('  the white balance lock, and that each photo shows mostly one surface, then try again.')


if __name__ == '__main__':
    main()
