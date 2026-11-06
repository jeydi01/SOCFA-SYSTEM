#!/usr/bin/env python3
"""
SoCFA — calibrate red NDVI (do once, and again if a camera or filter changes)
=============================================================================
Red NDVI compares near-infrared from the NoIR camera with red from the RGB
camera. The two cameras have different sensitivities, so they are balanced
once on a WHITE TARGET, which reflects red and near-infrared about equally
(plain white printer paper or a white foam board, no glossy plastic).

1. Outdoors in sunlight, lay the white target flat so it FILLS THE CENTRE of
   the cameras' view (hold or fly the cameras about 1 m above it).
2. Take a capture: "Take Photos" on the NDVI page (wait for the result).
3. Run:   python calibrate_red_ndvi.py                (uses the newest flight)
     or   python calibrate_red_ndvi.py flight_20261102_101530 3   (flight, pair)

It writes red_ndvi_calibration.json; from then on red NDVI is "calibrated".
Flights must be taken with the updated pi_capture.py (it records the camera
settings the calibration relies on).
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

from ndvi_core import red_bands, RED_CAL_FILE
from pair_align import align_pair

HERE = os.path.dirname(os.path.abspath(__file__))
CAPTURES = os.path.join(HERE, 'captures')
CENTRE = 0.35          # middle 35% of the aligned photo must show the white target


def newest_flight():
    flights = sorted(f for f in os.listdir(CAPTURES) if os.path.isfile(os.path.join(CAPTURES, f, 'pairs.json')))
    if not flights:
        sys.exit('No flights in captures/. Take a capture of the white target first.')
    return flights[-1]


def main():
    flight = sys.argv[1] if len(sys.argv) > 1 else newest_flight()
    meta = json.load(open(os.path.join(CAPTURES, flight, 'pairs.json'), encoding='utf-8'))
    if len(sys.argv) > 2:
        pair_id = int(sys.argv[2])
    else:                                  # the pair the automatic analysis used, else the middle one
        auto = os.path.join(CAPTURES, flight, 'auto_result.json')
        pair_id = json.load(open(auto, encoding='utf-8'))['pair'] if os.path.isfile(auto) \
            else meta['pairs'][len(meta['pairs']) // 2]['id']
    pair = next(p for p in meta['pairs'] if p['id'] == pair_id)
    cameras = meta.get('cameras')
    print(f'Flight {flight}, pair {pair_id}')
    if not cameras:
        sys.exit('This flight has no recorded camera settings. Update pi_capture.py on the Pi, '
                 'take a new capture of the white target, and run this again.')

    read = lambda name: np.array(Image.open(os.path.join(CAPTURES, flight, name)).convert('RGB'))
    rgb, noir, info = align_pair(read(pair['rgb']), read(pair['noir']))
    print(f"Alignment: {info['method']} ({info.get('inliers', 0)} matching points, {info.get('kept_pct')}% kept)")
    if info['method'] == 'none':
        sys.exit('The two photos could not be aligned. Make sure both show the same scene, then retry.')

    nir, red, ok = red_bands(rgb, noir, cameras)
    h, w = red.shape
    y0, y1 = int(h * (0.5 - CENTRE / 2)), int(h * (0.5 + CENTRE / 2))
    x0, x1 = int(w * (0.5 - CENTRE / 2)), int(w * (0.5 + CENTRE / 2))
    sel = ok[y0:y1, x0:x1]
    r, n = red[y0:y1, x0:x1][sel], nir[y0:y1, x0:x1][sel]
    if r.size < 0.5 * sel.size:
        sys.exit('Too much of the centre is overexposed or too dark. Retake in steady sunlight.')

    rgb_c = rgb[y0:y1, x0:x1].reshape(-1, 3).astype(float).mean(0)
    spread = float(np.std(r) / (np.mean(r) + 1e-12))
    print(f'Centre of the RGB photo: mean colour R {rgb_c[0]:.0f} G {rgb_c[1]:.0f} B {rgb_c[2]:.0f} '
          f'(white target should look bright and neutral)')
    if spread > 0.25 or min(rgb_c) < 120:
        print('⚠ The centre does not look like an even, bright white target '
              f'(brightness varies {spread * 100:.0f}%). Check the photo; the result may be wrong.')

    scale = float(np.median(r / np.maximum(n, 1e-12)))
    data = {'nir_scale': scale, 'flight': flight, 'pair': pair_id,
            'measured_at': time.strftime('%Y-%m-%d %H:%M'), 'cameras': cameras,
            'target_brightness_spread': round(spread, 3)}
    with open(RED_CAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f'NIR scale factor: {scale:.4f}  → saved to {os.path.basename(RED_CAL_FILE)}')
    print('Red NDVI on the white target is now ~0 (as it should be). Used from the next analysis on.')


if __name__ == '__main__':
    main()
