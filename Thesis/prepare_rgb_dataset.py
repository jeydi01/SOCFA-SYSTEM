"""
RGB Dataset Preparation — tile based, labelled by green cover

Every source photo is cut into square tiles. Each tile is labelled by its
green cover (share of pixels with ExGR > 0, the Excess Green minus Excess Red
index of Meyer & Neto 2008), using the same thresholds for every source, so
each class mixes several datasets:

  healthy:  cover >= 0.85
  moderate: cover 0.30 - 0.75, spread evenly (not dense crop next to a bare path);
            WeedyRice is excluded here (its mid-cover tiles are ponds, trees, gravel)
  poor:     cover <  0.15        (bare soil, roads, dry/senescent crop)
  tiles in the gaps are ambiguous and skipped

ExGR is used instead of plain Excess Green because it rejects yellow straw
and the greenish colour cast of the flight-session camera on bare ground.
Sky, white calibration panels, very dark and blank tiles are dropped automatically.

Output:
  dataset_rgb/<class>/NNNN_<source>_<photo>_r<row>c<col>.jpg
  dataset_rgb/manifest.csv          — every tile with its source and cover
  dataset_rgb/review/<class>_NN.jpg — numbered contact sheets

Colour alone cannot tell crop from trees, roads or buildings, so check the
review sheets once and delete non-crop tiles by their number (NNNN).
"""
import os, csv, shutil, glob, random
import cv2
import numpy as np

DOWNLOADS = r"C:\Users\facun\Downloads"
SOURCES = {
    # name        : list of glob patterns
    'weedyrice'   : [rf"{DOWNLOADS}\WeedyRice-RGBMS-DB\WeedyRice-RGBMS-DB\RGB\*.JPG"],
    'wheat0727'   : [rf"{DOWNLOADS}\new dataset\Wheat-dataset\Wheat-dataset\wheat_27072019\RGB\*.png"],
    'wheat0813'   : [rf"{DOWNLOADS}\new dataset\Wheat-dataset\Wheat-dataset\wheat_13082019\RGB\*.png"],
    'wheat0830'   : [rf"{DOWNLOADS}\new dataset\Wheat-dataset\Wheat-dataset\wheat_30082019\RGB\*.png"],
    'session01'   : [rf"{DOWNLOADS}\Component 1 - part 1-2\Component 1 - part 1-2\flight_session_01\flight_session_01\*\*FPLAN\*.JPG"],
    'session02'   : [rf"{DOWNLOADS}\Component 1 - part 1-2\Component 1 - part 1-2\flight_session_02\filght_session_02\*\*FPLAN\*.JPG"],
}

SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR        = os.path.join(SCRIPT_DIR, 'dataset_rgb')
CLASSES           = ['healthy', 'moderate', 'poor']
MAX_PER_CLASS     = 500
PHOTOS_PER_SOURCE = 700      # random photos read per source (keeps runtime reasonable)
GRID_ROWS         = 4        # tiles along the short side of a photo
IMAGE_SIZE        = 64       # output tile size (matches train_ndvi_cnn.py)
SEED              = 42

HEALTHY_MIN         = 0.85
MODERATE_RANGE      = (0.30, 0.75)
POOR_MAX            = 0.15
# A moderate tile is 'crop + path' (skipped) when, on an 8x8 block grid, at least 20% of
# blocks are fully green, at least 20% fully bare, and together they make up >= 65%.
MIXED_MIN_SIDE      = 0.20
MIXED_MIN_EXTREME   = 0.65
MODERATE_EXCLUDE    = {'weedyrice'}

random.seed(SEED)


def list_files(patterns):
    # set(): Windows glob is case-insensitive, so *.jpg and *.JPG return the same files
    return sorted({f for p in patterns for f in glob.glob(p)})


def green_mask(img):
    f = img.astype(np.float32)
    b, g, r = cv2.split(f)
    total = b + g + r + 1e-6
    r, g, b = r / total, g / total, b / total
    exgr = (2 * g - r - b) - (1.4 * r - g)          # ExG - ExR (Meyer & Neto 2008)
    return exgr > 0


def is_artifact(tile):
    """Sky, white calibration panels / QR boards, near-black and blank tiles,
    and camera glitches (saturated yellow edge bars, red/cyan corruption)."""
    f = tile.astype(np.float32)
    B, G, R = f[..., 0], f[..., 1], f[..., 2]
    b, g, r = B.mean(), G.mean(), R.mean()
    white = (tile.min(axis=2) > 200).mean()
    blank = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY).std() < 2.5   # overexposed / featureless
    glitch = ((R > 190) & (G > 170) & (B < 60)).mean() > 0.02         or ((R > 150) & (G < 70)).mean() > 0.02         or ((G > 140) & (B > 140) & (R < 70)).mean() > 0.02
    return (b > g + 15 and b > r + 15) or white > 0.05 or (r + g + b) / 3 < 35 or blank or glitch


def is_mixed(mask):
    """Dense crop and bare ground side by side (e.g. a plot next to a path),
    as opposed to crop that is evenly sparse or patchy across the tile."""
    h, w = mask.shape
    blocks = np.array([mask[i * h // 8:(i + 1) * h // 8, j * w // 8:(j + 1) * w // 8].mean()
                       for i in range(8) for j in range(8)])
    full, bare = (blocks > 0.85).mean(), (blocks < 0.15).mean()
    if full >= MIXED_MIN_SIDE and bare >= MIXED_MIN_SIDE and full + bare >= MIXED_MIN_EXTREME:
        return True
    # a straight bare strip (path) and a straight dense strip (plot) in the same tile
    rows = [mask[i * h // 8:(i + 1) * h // 8].mean() for i in range(8)]
    cols = [mask[:, j * w // 8:(j + 1) * w // 8].mean() for j in range(8)]
    return any(min(v) < 0.15 and max(v) > 0.85 for v in (rows, cols))


def label_for(cover, mixed):
    if cover >= HEALTHY_MIN:
        return 'healthy'
    if MODERATE_RANGE[0] <= cover <= MODERATE_RANGE[1]:
        return None if mixed else 'moderate'
    if cover < POOR_MAX:
        return 'poor'
    return None                                      # ambiguous band, skipped


def tiles_from_photo(path):
    img = cv2.imread(path)
    if img is None:
        return
    h, w = img.shape[:2]
    side = min(h, w) // GRID_ROWS
    rows, cols = h // side, w // side
    y0, x0 = (h - rows * side) // 2, (w - cols * side) // 2   # centre the grid
    mask = green_mask(img)
    for r in range(rows):
        for c in range(cols):
            ys, xs = y0 + r * side, x0 + c * side
            tile_mask = mask[ys:ys + side, xs:xs + side]
            tile = cv2.resize(img[ys:ys + side, xs:xs + side], (IMAGE_SIZE, IMAGE_SIZE),
                              interpolation=cv2.INTER_AREA)
            # mixed check on the 64 px tile (what the model sees); full-res noise hides bare strips
            yield r, c, float(tile_mask.mean()), is_mixed(green_mask(tile)), tile


def write_review_sheets(rows_by_class):
    review_dir = os.path.join(OUTPUT_DIR, 'review')
    os.makedirs(review_dir)
    cell, per_row, per_sheet = 128, 10, 100
    for cls, rows in rows_by_class.items():
        for s in range(0, len(rows), per_sheet):
            chunk = rows[s:s + per_sheet]
            sheet = np.full((cell * ((len(chunk) + per_row - 1) // per_row), cell * per_row, 3), 255, np.uint8)
            for i, row in enumerate(chunk):
                tile = cv2.imread(os.path.join(OUTPUT_DIR, cls, row['file']))
                tile = cv2.resize(tile, (cell - 4, cell - 4), interpolation=cv2.INTER_NEAREST)
                y, x = (i // per_row) * cell, (i % per_row) * cell
                sheet[y + 2:y + cell - 2, x + 2:x + cell - 2] = tile
                num = row['file'][:4]
                cv2.rectangle(sheet, (x + 2, y + 2), (x + 46, y + 20), (0, 0, 0), -1)
                cv2.putText(sheet, num, (x + 5, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imwrite(os.path.join(review_dir, f'{cls}_{s // per_sheet + 1:02d}.jpg'), sheet)


# ── Collect candidate tiles from every source ────────────────────────────────
for name, patterns in SOURCES.items():
    assert list_files(patterns), f"No images found for '{name}': {patterns[0]}"

if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
for cls in CLASSES:
    os.makedirs(os.path.join(OUTPUT_DIR, cls))

# candidates[cls][source] -> list of (photo_path, row, col, cover, tile)
candidates = {cls: {src: [] for src in SOURCES} for cls in CLASSES}
skipped_ambiguous = skipped_artifacts = 0

for name, patterns in SOURCES.items():
    files = list_files(patterns)
    photos = random.sample(files, min(PHOTOS_PER_SOURCE, len(files)))
    print(f"Tiling {name:10s} {len(photos):4d} of {len(files):4d} photos...")
    for path in photos:
        for r, c, cover, mixed, tile in tiles_from_photo(path):
            if is_artifact(tile):
                skipped_artifacts += 1
                continue
            cls = label_for(cover, mixed)
            if cls == 'moderate' and name in MODERATE_EXCLUDE:
                cls = None
            if cls is None:
                skipped_ambiguous += 1
                continue
            candidates[cls][name].append((path, r, c, cover, tile))

# ── Pick tiles round-robin across sources so every class mixes datasets ─────
selected = {cls: [] for cls in CLASSES}
for cls in CLASSES:
    pools = {src: random.sample(t, len(t)) for src, t in candidates[cls].items() if t}
    while len(selected[cls]) < MAX_PER_CLASS and pools:
        for src in list(pools):
            if len(selected[cls]) >= MAX_PER_CLASS:
                break
            selected[cls].append((src, *pools[src].pop()))
            if not pools[src]:
                del pools[src]

# ── Write tiles, manifest and review sheets ─────────────────────────────────
manifest, rows_by_class, n = [], {cls: [] for cls in CLASSES}, 0
for cls in CLASSES:
    for src, path, r, c, cover, tile in selected[cls]:
        n += 1
        base = os.path.splitext(os.path.basename(path))[0][:40]
        fname = f"{n:04d}_{src}_{base}_r{r}c{c}.jpg"
        cv2.imwrite(os.path.join(OUTPUT_DIR, cls, fname), tile)
        row = {'file': fname, 'class': cls, 'source': src, 'cover': f"{cover:.3f}",
               'tile_row': r, 'tile_col': c, 'original': path}
        manifest.append(row)
        rows_by_class[cls].append(row)

with open(os.path.join(OUTPUT_DIR, 'manifest.csv'), 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=list(manifest[0]))
    writer.writeheader()
    writer.writerows(manifest)

write_review_sheets(rows_by_class)

# ── Summary ─────────────────────────────────────────────────────────────────
print(f"\nDone! (skipped {skipped_ambiguous} ambiguous/mixed and {skipped_artifacts} sky/panel/dark tiles)\n")
print(f"{'class':9s} {'total':>5s}  " + "  ".join(f"{s:>9s}" for s in SOURCES) + "   cover mean")
for cls in CLASSES:
    counts = {s: sum(1 for x in selected[cls] if x[0] == s) for s in SOURCES}
    covers = [x[4] for x in selected[cls]]
    print(f"{cls:9s} {len(selected[cls]):5d}  " + "  ".join(f"{counts[s]:9d}" for s in SOURCES)
          + f"   {np.mean(covers) if covers else float('nan'):.2f}")
print(f"\nReview sheets: {os.path.join(OUTPUT_DIR, 'review')}")
print("Delete non-crop tiles (trees, roads, buildings) by their number, then train.")
