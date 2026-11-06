"""
SoCFA — align the NoIR photo to the RGB photo of a drone pair
=============================================================
The two cameras sit side by side, so their photos are slightly shifted,
rotated and scaled against each other. NDVI compares the same spot in both
(red NDVI uses NIR from the NoIR photo and red from the RGB photo), and the
dashboard should show both photos covering the same ground.

  1. Find matching details in both photos (SIFT features on contrast-enhanced
     greyscale), fit a shift + rotation + scale (RANSAC), and check it is
     reliable (enough matching points, plausible rotation and scale).
  2. Reliable → use it and remember it (alignment.json): the cameras are fixed
     on one plate, so the alignment barely changes between flights.
     Not reliable (dark photo, plain water surface) → use the last good one.
  3. Warp the NoIR photo onto the RGB photo and crop both to the area both
     cameras see.
"""
import json
import os
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ALIGN_FILE = os.path.join(HERE, 'alignment.json')    # last reliable alignment

MATCH_WIDTH   = 1000     # photos are matched at this width (fast, enough detail)
MIN_INLIERS   = 40       # fewer matching points than this → not reliable
SCALE_RANGE   = (0.85, 1.15)
MAX_ROTATION  = 45.0     # degrees


def _grey(img):
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(g)


def estimate(rgb, noir):
    """Alignment NoIR → RGB in full-resolution pixels, or None. RGB arrays (RGB order)."""
    s = MATCH_WIDTH / rgb.shape[1]
    a = cv2.resize(rgb, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    b = cv2.resize(noir, None, fx=MATCH_WIDTH / noir.shape[1], fy=MATCH_WIDTH / noir.shape[1], interpolation=cv2.INTER_AREA)
    sift = cv2.SIFT_create(4000)
    ka, da = sift.detectAndCompute(_grey(a), None)
    kb, db = sift.detectAndCompute(_grey(b), None)
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return None
    matches = cv2.BFMatcher().knnMatch(db, da, k=2)
    good = [m for m, n in (p for p in matches if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return None
    src = np.float32([kb[g.queryIdx].pt for g in good])
    dst = np.float32([ka[g.trainIdx].pt for g in good])
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0)
    if M is None:
        return None
    # back to full resolution: rotation/scale unchanged, shift scales with the image
    sb = MATCH_WIDTH / noir.shape[1]
    M_full = M.copy()
    M_full[:, :2] = M[:, :2] * (sb / s)
    M_full[:, 2] = M[:, 2] / s
    return {'matrix': M_full.tolist(), 'inliers': int(inl.sum()),
            'rotation_deg': float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))),
            'scale': float(np.hypot(M_full[0, 0], M_full[1, 0])),
            'rgb_size': [int(rgb.shape[1]), int(rgb.shape[0])],
            'noir_size': [int(noir.shape[1]), int(noir.shape[0])]}


def reliable(est):
    return (est is not None and est['inliers'] >= MIN_INLIERS
            and SCALE_RANGE[0] <= est['scale'] <= SCALE_RANGE[1]
            and abs(est['rotation_deg']) <= MAX_ROTATION)


def load_saved():
    try:
        with open(ALIGN_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save(est):
    data = dict(est, saved_at=int(time.time() * 1000))
    with open(ALIGN_FILE + '.part', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(ALIGN_FILE + '.part', ALIGN_FILE)


def _valid_rect(mask):
    """Largest axis-aligned rectangle (approx.) fully inside the area both cameras see."""
    small = mask[::8, ::8]
    y0, x0, y1, x1 = 0, 0, small.shape[0], small.shape[1]
    while y1 - y0 > 4 and x1 - x0 > 4:
        sub = small[y0:y1, x0:x1]
        if sub.all():
            break
        bad = {'t': (~sub[0]).sum(), 'b': (~sub[-1]).sum(), 'l': (~sub[:, 0]).sum(), 'r': (~sub[:, -1]).sum()}
        side = max(bad, key=bad.get)
        if side == 't': y0 += 1
        elif side == 'b': y1 -= 1
        elif side == 'l': x0 += 1
        else: x1 -= 1
    # back to full size, one step inside to stay clear of the warped border
    return (min(y0 * 8 + 8, mask.shape[0]), min(x0 * 8 + 8, mask.shape[1]),
            max(y1 * 8 - 8, 0), max(x1 * 8 - 8, 0))


def align_pair(rgb, noir):
    """Align the NoIR photo to the RGB photo and crop both to the shared area.
    Returns (rgb_crop, noir_crop, info). info['method']: 'auto', 'saved' or 'none'."""
    est = estimate(rgb, noir)
    if reliable(est):
        method = 'auto'
        save(est)
    else:
        saved = load_saved()
        if saved and saved.get('rgb_size') == [rgb.shape[1], rgb.shape[0]] \
                and saved.get('noir_size') == [noir.shape[1], noir.shape[0]]:
            method, est = 'saved', saved
        else:
            info = {'method': 'none', 'inliers': est['inliers'] if est else 0,
                    'kept_pct': 100.0, 'note': 'Photos could not be aligned; shown unaligned.'}
            return rgb, noir, info
    M = np.array(est['matrix'], dtype=np.float64)
    h, w = rgb.shape[:2]
    warped = cv2.warpAffine(noir, M, (w, h), flags=cv2.INTER_LINEAR)
    mask = cv2.warpAffine(np.full(noir.shape[:2], 255, np.uint8), M, (w, h), flags=cv2.INTER_NEAREST) > 0
    y0, x0, y1, x1 = _valid_rect(mask)
    if y1 - y0 < h * 0.2 or x1 - x0 < w * 0.2:          # almost no overlap: don't crop to a sliver
        return rgb, noir, {'method': 'none', 'inliers': est.get('inliers', 0), 'kept_pct': 100.0,
                           'note': 'Too little overlap between the two photos.'}
    kept = (y1 - y0) * (x1 - x0) / (w * h) * 100
    info = {'method': method, 'inliers': est.get('inliers', 0),
            'rotation_deg': round(est['rotation_deg'], 2), 'scale': round(est['scale'], 4),
            'shift_px': [round(est['matrix'][0][2]), round(est['matrix'][1][2])],
            'kept_pct': round(kept, 1), 'crop': [int(x0), int(y0), int(x1), int(y1)]}
    return rgb[y0:y1, x0:x1], warped[y0:y1, x0:x1], info
