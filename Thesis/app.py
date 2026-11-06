from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import tensorflow as tf
import numpy as np
from PIL import Image
import io, os, json, base64, cv2, time, threading, socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import urllib.request, urllib.error, urllib.parse
from firebase_config import save_analysis_result, get_field_history
from fusion import predict_soil_zone, combine, HEALTHY_MIN, MODERATE_MIN
from soil_rules import probe_not_in_soil
from ndvi_core import (ndvi_from_noir, ndvi_red, class_shares, NDVI_POOR_MAX, NDVI_MODERATE_MAX,
                       NDVI_SOURCE)
from pair_align import align_pair

app = Flask(__name__)
CORS(app)  # Allow your HTML dashboard to call this API

# Load model once on startup
# Trained in Colab on dataset_rgb (download SOCFA_NDVI/model_rgb/ndvi_cnn_best.h5)
MODEL_PATH = 'model/ndvi_cnn_rgb.h5'
GRID_ROWS  = 4     # same tiling as prepare_rgb_dataset.py
TILE_SIZE  = 64
print("Loading CNN model...")
# Build the network from the training script and load only the weights: a full
# .h5 saved by Colab's newer Keras stores settings this Keras cannot read.
from train_ndvi_cnn import create_model
model = create_model()
model.load_weights(MODEL_PATH)
CLASSES = ['healthy', 'moderate', 'poor']
print("✅ Model loaded!")


def decode_image(image_data):
    """Base64 (optionally a data URL) → RGB uint8 array."""
    if ',' in image_data:
        image_data = image_data.split(',')[1]
    img = Image.open(io.BytesIO(base64.b64decode(image_data))).convert('RGB')
    return np.array(img)


def make_tiles(rgb):
    """Cut the photo into square tiles exactly like the training dataset:
    GRID_ROWS tiles along the short side, grid centred, each resized to 64x64."""
    h, w = rgb.shape[:2]
    side = min(h, w) // GRID_ROWS
    if side < TILE_SIZE // 2:                        # tiny image: use it whole
        tiles = [cv2.resize(rgb, (TILE_SIZE, TILE_SIZE), interpolation=cv2.INTER_AREA)]
    else:
        rows, cols = h // side, w // side
        y0, x0 = (h - rows * side) // 2, (w - cols * side) // 2
        tiles = [cv2.resize(rgb[y0 + r * side:y0 + (r + 1) * side, x0 + c * side:x0 + (c + 1) * side],
                            (TILE_SIZE, TILE_SIZE), interpolation=cv2.INTER_AREA)
                 for r in range(rows) for c in range(cols)]
    return np.stack(tiles).astype(np.float32) / 255.0


_model_lock = threading.Lock()   # /analyze and the drone watcher share the model


def predict_field(rgb):
    """Classify every tile; the field result is the mean of the tile probabilities."""
    with _model_lock:
        tile_probs = model.predict(make_tiles(rgb), verbose=0)
    predictions = tile_probs.mean(axis=0)
    tile_counts = {cls: int(n) for cls, n in
                   zip(CLASSES, np.bincount(tile_probs.argmax(axis=1), minlength=len(CLASSES)))}
    return predictions, tile_counts

# ── Drone (Raspberry Pi) ─────────────────────────────────────────────────────
# pi_server.py on the Pi. The hotspot can give the Pi a new address any day, so
# the last address that worked is remembered (pi_url.txt) and, when it stops
# answering, the Wi-Fi network is searched for the Pi automatically (find_pi).
# SOCFA_PI_URL is only the first guess when nothing has been remembered yet.
PI_PORT     = 8000
PI_URL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pi_url.txt')
CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures')


def _initial_pi_url():
    try:
        with open(PI_URL_FILE, encoding='utf-8') as f:
            saved = f.read().strip()
        if saved:
            return saved.rstrip('/')
    except OSError:
        pass
    return os.environ.get('SOCFA_PI_URL', f'http://raspberrypi.local:{PI_PORT}').rstrip('/')


PI_URL = _initial_pi_url()

def compute_ndvi(noir_rgb, settings=None):
    """NoIR camera with blue filter: NDVI = (NIR - Blue) / (NIR + Blue) (see ndvi_core.py).
    settings = the NoIR camera's recorded colour gains (None for uploads / old flights)."""
    ndvi = ndvi_from_noir(noir_rgb, settings)
    mean = float(np.nanmean(ndvi)) if np.isfinite(ndvi).any() else 0.0
    return mean, class_shares(ndvi), ndvi_map_image(ndvi)


def ndvi_map_image(ndvi, max_side=1000):
    """Colour the NDVI: brown (bare) -> yellow (sparse) -> greens (dense)."""
    stops  = [-0.2, 0.0, NDVI_POOR_MAX, (NDVI_POOR_MAX + NDVI_MODERATE_MAX) / 2, NDVI_MODERATE_MAX, 0.8]
    colors = np.array([[110, 60, 20], [139, 69, 19], [210, 105, 30],
                       [255, 215, 0], [50, 205, 50], [0, 100, 0]], np.float32)
    bad = np.isnan(ndvi)
    filled = np.where(bad, 0.0, ndvi)
    rgb = np.stack([np.interp(filled, stops, colors[:, k]) for k in range(3)], axis=-1).astype(np.uint8)
    rgb[bad] = (150, 150, 150)                    # not measurable (overexposed / too dark)
    h, w = rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1:
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def capture_path(flight, filename):
    path = os.path.realpath(os.path.join(CAPTURE_DIR, flight, filename))
    if not path.startswith(os.path.realpath(CAPTURE_DIR) + os.sep):
        abort(404)
    return path


def flight_meta(flight):
    """The flight's pairs.json ({} if missing)."""
    try:
        with open(capture_path(flight, 'pairs.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def flight_cameras(flight):
    """Exposure / gain / colour gains of both cameras for this flight (None if not recorded)."""
    return flight_meta(flight).get('cameras')


def save_aligned(flight, pair_id, rgb_crop, noir_crop, max_width=1640):
    """Aligned + cropped photos for the dashboard (same ground in both)."""
    names = {}
    for kind, img in (('rgb', rgb_crop), ('noir', noir_crop)):
        im = Image.fromarray(img)
        if im.width > max_width:
            im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
        name = f'{int(pair_id):04d}_{kind}_aligned.jpg'
        im.save(capture_path(flight, name), quality=90)
        names[kind] = name
    return names


def load_capture_pair(flight, pair_id):
    with open(capture_path(flight, 'pairs.json'), encoding='utf-8') as f:
        pair = next(p for p in json.load(f)['pairs'] if p['id'] == int(pair_id))
    read = lambda name: np.array(Image.open(capture_path(flight, name)).convert('RGB'))
    return read(pair['rgb']), read(pair['noir'])


def pi_get(path, timeout=5):
    with urllib.request.urlopen(f'{PI_URL}{path}', timeout=timeout) as r:
        return r.read()


# ── Finding the Pi on the Wi-Fi ──────────────────────────────────────────────
FIND_PI_EVERY = 20            # seconds between searches while the Pi is missing
_find_lock = threading.Lock()
_last_find = 0.0


def _local_prefixes():
    """'a.b.c.' of every IPv4 network this laptop is on (Wi-Fi hotspot first)."""
    ips = []
    try:                                              # interface used to reach other networks
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))              # no packet is sent
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        ips += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    own, prefixes = set(), []
    for ip in ips:
        if ip.startswith(('127.', '169.254.')) or ip in own:
            continue
        own.add(ip)
        prefix = ip.rsplit('.', 1)[0] + '.'
        if prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes, own


def _port_open(ip):
    try:
        with socket.create_connection((ip, PI_PORT), timeout=0.5):
            return ip
    except OSError:
        return None


def _is_socfa_pi(ip):
    """True when ip runs pi_server.py (answers /flights with a list)."""
    try:
        with urllib.request.urlopen(f'http://{ip}:{PI_PORT}/flights', timeout=2) as r:
            return isinstance(json.loads(r.read()), list)
    except (OSError, ValueError):
        return False


def find_pi(force=False):
    """Search the laptop's Wi-Fi network(s) for the Pi. On success, switch to its
    address and remember it. At most once every FIND_PI_EVERY seconds."""
    global PI_URL, _last_find
    with _find_lock:
        if not force and time.time() - _last_find < FIND_PI_EVERY:
            return False
        _last_find = time.time()
        prefixes, own = _local_prefixes()
        old_host = urllib.parse.urlparse(PI_URL).hostname or ''
        for prefix in prefixes:
            hosts = [f'{prefix}{n}' for n in range(1, 255) if f'{prefix}{n}' not in own]
            with ThreadPoolExecutor(max_workers=128) as pool:
                open_ips = [ip for ip in pool.map(_port_open, hosts) if ip]
            open_ips.sort(key=lambda ip: ip != old_host)  # the old address first, if it is back
            for ip in open_ips:
                if _is_socfa_pi(ip):
                    new_url = f'http://{ip}:{PI_PORT}'
                    if new_url != PI_URL:
                        print(f"Found the drone at {new_url} (was {PI_URL})")
                    PI_URL = new_url
                    try:
                        with open(PI_URL_FILE, 'w', encoding='utf-8') as f:
                            f.write(new_url)
                    except OSError:
                        pass
                    return True
        return False


def pi_get_or_find(path, timeout=5):
    """pi_get, but if the Pi does not answer, search the Wi-Fi for it and retry."""
    try:
        return pi_get(path, timeout)
    except (urllib.error.URLError, OSError):
        if find_pi():
            return pi_get(path, timeout)
        raise


def _pi_host():
    return urllib.parse.urlparse(PI_URL).hostname


def pi_post(path, data, timeout=5):
    req = urllib.request.Request(f'{PI_URL}{path}', data=json.dumps(data).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ── Field assessment (drone zone + soil nodes → one result) ─────────────────
# The drone captures one zone and all soil nodes sit inside it, so the latest
# drone analysis and the latest reading of every node give ONE final result.
SOIL_API_URL     = os.environ.get('SOCFA_SOIL_URL', 'http://localhost:3000').rstrip('/')
LATEST_NDVI_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'latest_ndvi.json')   # any analysis
LATEST_DRONE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'latest_drone.json')  # drone captures only
# Soil readings must be taken within this many hours of the drone capture to be combined
SOIL_MAX_GAP_HOURS = float(os.environ.get('SOCFA_SOIL_MAX_GAP_HOURS', '24'))


def _write_json(path, data):
    with open(path + '.part', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(path + '.part', path)


def _read_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_latest_ndvi(result):
    _write_json(LATEST_NDVI_PATH, result)
    if result.get('source') == 'drone':
        _write_json(LATEST_DRONE_PATH, result)


def load_latest_ndvi():
    """Prefer the latest real drone capture; fall back to the latest upload (flagged)."""
    return _read_json(LATEST_DRONE_PATH) or _read_json(LATEST_NDVI_PATH)


def capture_time_ms(flight, pair_id):
    """When the drone took the pair (from pairs.json), in ms like the soil timestamps."""
    with open(capture_path(flight, 'pairs.json'), encoding='utf-8') as f:
        pair = next(p for p in json.load(f)['pairs'] if p['id'] == int(pair_id))
    return int(datetime.fromisoformat(pair['time']).timestamp() * 1000)


def _fmt_ms(ms):
    return datetime.fromtimestamp(ms / 1000).strftime('%b %d, %Y %H:%M')


def latest_soil_readings():
    """Newest reading of every node from the Node backend (EC in µS/cm)."""
    with urllib.request.urlopen(f'{SOIL_API_URL}/soil-data', timeout=5) as r:
        rows = json.loads(r.read())
    latest = {}
    for row in rows:
        node = str(row.get('node_id'))
        if node not in latest or row.get('timestamp', 0) > latest[node].get('timestamp', 0):
            latest[node] = row
    return [{'node_id':    node,
             'ph':          float(r['ph']),
             'temperature': float(r['temperature']),
             'ec':          float(r['ec']),
             'humidity':    float(r['humidity']),
             'timestamp':   r.get('timestamp')}
            for node, r in sorted(latest.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else kv[0])]


def preprocess_image(image_data):
    """Convert uploaded RGB image for CNN — matches training format."""
    if ',' in image_data:
        image_data = image_data.split(',')[1]

    img_bytes = base64.b64decode(image_data)
    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    img = img.resize((64, 64))
    arr = np.array(img).astype(np.float32) / 255.0

    return np.expand_dims(arr, axis=0)

def calculate_ndvi_from_colors(image_array):
    """Calculate more accurate NDVI estimation from RGB image using vegetation indices"""
    # Convert to float and normalize
    img = image_array[0].astype(np.float32) / 255.0

    # Extract RGB channels
    r = img[:, :, 0]
    g = img[:, :, 1]
    b = img[:, :, 2]

    # Calculate multiple vegetation indices for better accuracy

    # 1. Green-Red Vegetation Index (GRVI)
    grvi = (g - r) / (g + r + 1e-8)

    # 2. Visible Atmospherically Resistant Index (VARI)
    vari = (g - r) / (g + r - b + 1e-8)

    # 3. Excess Green Index (ExG)
    exg = 2 * g - r - b

    # 4. Normalized Green-Red Difference Index (NGRDI)
    ngrdi = (g - r) / (g + r + 1e-8)

    # Combine indices with weights for NDVI estimation
    # Healthy vegetation: high green, low red
    # Stressed vegetation: lower green, higher red/yellow
    combined_index = 0.4 * grvi + 0.3 * vari + 0.2 * exg + 0.1 * ngrdi

    # Normalize to 0-1 range (typical NDVI range is -1 to 1, but we use 0-1 for classification)
    ndvi = np.clip((combined_index + 2) / 4, 0, 1)

    return float(np.mean(ndvi))

def generate_greenness_map(image_array):
    """Generate a pixel-level greenness/NDVI map for visualization"""
    img = image_array[0].astype(np.float32) / 255.0

    r = img[:, :, 0]
    g = img[:, :, 1]
    b = img[:, :, 2]

    # Calculate greenness index (simplified NDVI approximation)
    greenness = (g - r) / (g + r + 1e-8)
    # Normalize to 0-255 range for visualization
    greenness_normalized = ((greenness + 1) / 2 * 255).astype(np.uint8)

    # Convert to base64 image
    greenness_img = Image.fromarray(greenness_normalized, mode='L')
    buffer = io.BytesIO()
    greenness_img.save(buffer, format='PNG')
    greenness_b64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{greenness_b64}"

@app.route('/analyze', methods=['POST'])
def analyze_ndvi():
    """Main endpoint: classifies the zone by NDVI (NoIR photo) + CNN (RGB photo)."""
    try:
        data = request.get_json()
        result = run_analysis(image_data=data.get('image'),          # base64 image (manual upload)
                              capture=data.get('capture'),           # {'flight', 'pair'} (drone pair)
                              noir_data=data.get('noir'),
                              field_name=data.get('field', 'North Field'),
                              coordinates=data.get('coordinates', {}))
        if result is None:
            return jsonify({'error': 'No image provided'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_analysis(image_data=None, capture=None, noir_data=None, field_name='North Field', coordinates=None):
    """NDVI (NoIR) + CNN (RGB) analysis of one photo or drone pair. Saves the result
    (Firebase + the zone's latest drone result) and returns the response dict."""
    coordinates = coordinates or {}
    noir_rgb = None
    rgb_aligned = alignment = aligned_files = cameras = spot = None
    if capture:
        rgb, noir_rgb = load_capture_pair(capture['flight'], capture['pair'])
        # Line the NoIR photo up with the RGB photo and keep only the shared area,
        # so the CNN, both NDVIs and the dashboard all describe the same ground
        rgb, noir_rgb, alignment = align_pair(rgb, noir_rgb)
        if alignment['method'] != 'none':
            rgb_aligned = rgb
            try:
                aligned_files = save_aligned(capture['flight'], capture['pair'], rgb, noir_rgb)
            except OSError as e:
                print(f"⚠️ Could not save aligned photos: {e}")
        cameras = flight_cameras(capture['flight'])
        spot = flight_meta(capture['flight']).get('spot')
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, format='JPEG', quality=92)
        image_data = base64.b64encode(buf.getvalue()).decode()
    elif noir_data:
        noir_rgb = decode_image(noir_data)
    if not image_data:
        return None

    # Preprocess & predict (tile the photo like the training data)
    img_array = preprocess_image(image_data)
    predictions, tile_counts = predict_field(decode_image(image_data))

    # Real NDVI only when the NoIR photo is available
    ndvi_true, ndvi_shares, ndvi_map = (compute_ndvi(noir_rgb, (cameras or {}).get('noir'))
                                        if noir_rgb is not None else (None, None, None))
    blue_shares = ndvi_shares

    # Red NDVI (NIR from NoIR + red from RGB) needs the two photos aligned
    red_value = red_shares = red_map = None
    red_calibrated = False
    if rgb_aligned is not None:
        red, red_calibrated = ndvi_red(rgb_aligned, noir_rgb, cameras)
        if np.isfinite(red).any():
            red_value = float(np.nanmean(red))
            red_shares = class_shares(red)
            red_map = ndvi_map_image(red)
    ndvi_source = 'red' if (NDVI_SOURCE == 'red' and red_shares is not None) else 'blue'
    if ndvi_source == 'red':
        ndvi_shares = red_shares                    # red NDVI decides the class

    # The aerial result integrates NDVI and the CNN (objective 3): the average of
    # the CNN probabilities (RGB photo) and the share of NoIR pixels in each NDVI
    # class (Table 7). Without a NoIR photo, the CNN alone is used.
    cnn_probs = {cls: float(pred) for cls, pred in zip(CLASSES, predictions)}
    if ndvi_shares is not None:
        method      = 'ndvi_cnn'
        class_probs = {cls: (cnn_probs[cls] + ndvi_shares[cls]) / 2 for cls in CLASSES}
    else:
        method      = 'cnn'
        class_probs = cnn_probs
    predicted_class = max(class_probs, key=class_probs.get)
    confidence      = class_probs[predicted_class]
    # Calculate proper NDVI approximation from RGB
    # Calculate proper NDVI approximation from RGB
    img_pil    = Image.open(io.BytesIO(base64.b64decode(
                 image_data.split(',')[1] if ',' in image_data else image_data
                 ))).convert('RGB').resize((64, 64))
    arr_rgb    = np.array(img_pil).astype(np.float32)
    r          = arr_rgb[:, :, 0] / 255.0
    g          = arr_rgb[:, :, 1] / 255.0
    grvi_value = float(np.mean((g - r) / (g + r + 1e-8)))   # greenness from RGB

    # Generate greenness visualization
    greenness_map = generate_greenness_map(img_array)

    # Save to Firebase (with error handling for demo)
    try:
        result = save_analysis_result(
            field_name=field_name,
            ndvi_value=ndvi_true,
            grvi_value=grvi_value,
            health_class=predicted_class,
            confidence=confidence,
            coordinates=coordinates
        )
        firebase_saved = True
    except Exception as e:
        print(f"⚠️ Firebase save failed (continuing without DB): {e}")
        firebase_saved = False

    # Keep the zone's latest drone result for the field assessment
    try:
        save_latest_ndvi({
            'health_class':        predicted_class,
            'confidence':          confidence,
            'class_probabilities': class_probs,
            'method':              method,
            'ndvi_shares':         ndvi_shares,
            'ndvi_source':         ndvi_source,
            'ndvi_red_value':      red_value,
            'ndvi_red_shares':     red_shares,
            'ndvi_red_calibrated': red_calibrated,
            'alignment':           alignment,
            'cnn_probabilities':   cnn_probs,
            'grvi_value':          grvi_value,
            'ndvi_value':          ndvi_true,
            'tile_counts':         tile_counts,
            'source':              'drone' if capture else 'upload',
            'capture':             capture,
            'field':               field_name,
            # drone: when the photo was taken; upload: when it was analyzed
            'timestamp':           (capture_time_ms(capture['flight'], capture['pair']) if capture
                                    else int(time.time() * 1000)),
        })
    except OSError as e:
        print(f"⚠️ Could not save latest NDVI result: {e}")

    return {
        'success': True,
        'health_class': predicted_class,
        'confidence': confidence,
        'ndvi_value': ndvi_true,          # blue NDVI average; None without a NoIR photo
        'grvi_value': grvi_value,
        'ndvi_shares': ndvi_shares,       # shares of the NDVI that decides the class
        'ndvi_blue_shares': blue_shares,
        'ndvi_map': ndvi_map,
        'ndvi_source': ndvi_source,       # 'blue' or 'red' (ndvi_core.NDVI_SOURCE)
        'ndvi_red_value': red_value,      # None when the photos could not be aligned
        'ndvi_red_shares': red_shares,
        'ndvi_red_map': red_map,
        'ndvi_red_calibrated': red_calibrated,
        'alignment': alignment,           # how the NoIR photo was lined up with the RGB photo
        'spot': spot,                     # spot / zone label typed when the photos were taken
        'aligned_files': aligned_files,   # aligned + cropped photos in captures/<flight>/
        'source': 'drone' if capture else 'upload',
        'greenness_map': greenness_map,
        'class_probabilities': class_probs,     # average of CNN and NDVI shares, or CNN only
        'method': method,                        # 'ndvi_cnn' or 'cnn'
        'ndvi_thresholds': {'poor_max': NDVI_POOR_MAX, 'moderate_max': NDVI_MODERATE_MAX},
        'cnn_probabilities': cnn_probs,
        'tile_counts': tile_counts,
        'field': field_name,
        'firebase_saved': firebase_saved,
        'message': get_recommendation(predicted_class, ndvi_true if ndvi_true is not None else grvi_value)
    }

@app.route('/drone/flights', methods=['GET'])
def drone_flights():
    """Flights on the Pi (needs the Pi on the same Wi-Fi) + which are already imported."""
    try:
        flights = json.loads(pi_get_or_find('/flights'))
    except (urllib.error.URLError, OSError) as e:
        return jsonify({'error': 'Drone not found on this Wi-Fi (searched the whole network). '
                                 'Is the Pi powered on and connected to the same hotspot as this laptop?'}), 503
    for f in flights:
        f['imported'] = os.path.isfile(os.path.join(CAPTURE_DIR, f['flight'], 'pairs.json'))
    return jsonify(flights)


@app.route('/drone/capture', methods=['POST'])
def drone_capture():
    """Dashboard "Take Photos" button: the Pi takes photo pairs right away.
    The finished flight is then picked up and analyzed by the watcher as usual."""
    body = request.get_json(silent=True) or {}
    count, spot = body.get('count', 10), body.get('spot', '')
    try:
        pi_get_or_find('/capture')                       # finds the Pi if its address changed
        return jsonify(json.loads(pi_post('/capture', {'count': count, 'spot': spot})))
    except urllib.error.HTTPError as e:                  # e.g. 409: already taking photos
        try:
            return jsonify(json.loads(e.read())), e.code
        except ValueError:
            return jsonify({'error': f'The drone answered with error {e.code}. '
                                     'Is pi_server.py on the Pi up to date?'}), 502
    except (urllib.error.URLError, OSError):
        return jsonify({'error': 'Drone not found on this Wi-Fi. Is the Pi powered on and '
                                 'connected to the same hotspot as this laptop?'}), 503


@app.route('/drone/capture-status', methods=['GET'])
def drone_capture_status():
    """Live state for the NDVI page indicator: waiting / capturing / analyzing."""
    status = {'connected': False, 'state': 'idle', 'flight': None, 'pairs': 0, 'target': None}
    if _auto_status.get('state') == 'processing':
        status.update(connected=True, state='analyzing')
        return jsonify(status)
    try:
        flights = json.loads(pi_get('/flights', timeout=3))
    except (urllib.error.URLError, OSError, ValueError):
        return jsonify(status)                            # Pi not on the Wi-Fi
    status['connected'] = True
    try:
        running = bool(json.loads(pi_get('/capture', timeout=3)).get('running'))
    except (urllib.error.URLError, OSError, ValueError):
        running = None                                    # older pi_server.py without /capture
    current = next((f for f in flights if not f.get('complete')), None)   # newest first
    if current and running is not False:
        status.update(state='capturing', flight=current['flight'], spot=current.get('spot'),
                      pairs=current.get('pairs', 0), target=current.get('target'))
    elif running:
        status['state'] = 'preparing'                     # waiting for the delay before photos
    else:
        done = next((f for f in flights if f.get('complete') and f.get('pairs', 0) > 0
                     and not os.path.isfile(os.path.join(CAPTURE_DIR, f['flight'], AUTO_RESULT_FILE))), None)
        if done:
            status.update(state='analyzing', flight=done['flight'])   # finished, about to be analyzed
    return jsonify(status)


@app.route('/drone/import', methods=['POST'])
def drone_import():
    """Copy a flight's photo pairs from the Pi to captures/<flight>/ (skips files already copied)."""
    flight = request.get_json().get('flight', '')
    try:
        meta, copied = import_flight(flight)
        return jsonify({'success': True, 'flight': flight, 'pairs': len(meta['pairs']), 'files_copied': copied})
    except (urllib.error.URLError, OSError) as e:
        return jsonify({'error': f'Import failed: {e}'}), 503


def import_flight(flight):
    meta = json.loads(pi_get(f'/flights/{flight}'))
    folder = os.path.dirname(capture_path(flight, 'pairs.json'))
    os.makedirs(folder, exist_ok=True)
    copied = 0
    for p in meta['pairs']:
        for name in (p['rgb'], p['noir']):
            dest = os.path.join(folder, name)
            if not os.path.isfile(dest):
                data = pi_get(f'/files/{flight}/{name}', timeout=30)
                with open(dest + '.part', 'wb') as f:
                    f.write(data)
                os.replace(dest + '.part', dest)
                copied += 1
    with open(os.path.join(folder, 'pairs.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    return meta, copied


# ── Automatic drone results ──────────────────────────────────────────────────
# After landing, the Pi shares its flights over Wi-Fi. This watcher checks the
# Pi every AUTO_POLL_SECONDS; each new COMPLETE flight is imported, its sharpest
# pair analyzed (NDVI + CNN), and the dashboard picks the result up by itself.
AUTO_POLL_SECONDS = float(os.environ.get('SOCFA_AUTO_POLL_SECONDS', '10'))
AUTO_FIELD_NAME   = os.environ.get('SOCFA_FIELD_NAME', 'Field Analysis')
AUTO_RESULT_FILE  = 'auto_result.json'          # in captures/<flight>/, marks it as done
_auto_status = {'state': 'off', 'message': 'Automatic drone results are off (start app.py directly).',
                'last_check': None}


def sharpest_pair(flight, meta):
    """Pair whose RGB photo is the sharpest (variance of the Laplacian):
    avoids photos blurred by wind or drone movement during the hover."""
    best, best_score = None, -1.0
    for p in meta['pairs']:
        img = cv2.imread(capture_path(flight, p['rgb']), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        small = cv2.resize(img, (max(1, img.shape[1] // 4), max(1, img.shape[0] // 4)),
                           interpolation=cv2.INTER_AREA)
        score = float(cv2.Laplacian(small, cv2.CV_64F).var())
        if score > best_score:
            best, best_score = p, score
    return best, best_score


def auto_process_flight(flight):
    meta, _ = import_flight(flight)
    out_path = capture_path(flight, AUTO_RESULT_FILE)
    pair, sharpness = sharpest_pair(flight, meta)
    if pair is None:
        _write_json(out_path, {'success': False, 'flight': flight, 'error': 'No usable photos in this flight.',
                               'processed_at': int(time.time() * 1000)})
        return None
    result = run_analysis(capture={'flight': flight, 'pair': pair['id']}, field_name=AUTO_FIELD_NAME)
    result.update({'auto': True, 'flight': flight, 'spot': meta.get('spot'), 'pair': pair['id'], 'rgb': pair['rgb'],
                   'pairs_in_flight': len(meta['pairs']), 'sharpness': round(sharpness, 1),
                   'processed_at': int(time.time() * 1000)})
    _write_json(out_path, result)
    print(f"Auto-analyzed {flight} pair {pair['id']}: {result['health_class']} ({result['method']})")
    return result


def auto_check_once():
    """One check of the Pi: analyze every new complete flight (oldest first,
    so the newest one ends up as the latest drone result)."""
    try:
        flights = json.loads(pi_get_or_find('/flights'))
    except (urllib.error.URLError, OSError, ValueError):
        _auto_status.update(state='waiting', message='Waiting for the drone — searching the Wi-Fi for the Pi...')
        return
    new = sorted(f['flight'] for f in flights
                 if f.get('complete') and f.get('pairs', 0) > 0
                 and not os.path.isfile(os.path.join(CAPTURE_DIR, f['flight'], AUTO_RESULT_FILE)))
    _auto_status.update(state='connected', message=f'Drone connected ({_pi_host()}) — no new flight.')
    for flight in new:
        _auto_status.update(state='processing', message=f'New flight {flight} — analyzing...')
        auto_process_flight(flight)
        _auto_status.update(state='connected', message=f'Analyzed {flight}.')


def auto_watch():
    while True:
        try:
            auto_check_once()
        except Exception as e:                            # keep watching whatever happens
            _auto_status.update(state='error', message=f'Automatic analysis failed: {e}')
            print(f"Automatic analysis failed: {e}")
        _auto_status['last_check'] = int(time.time() * 1000)
        time.sleep(AUTO_POLL_SECONDS)


def start_auto_watch():
    _auto_status.update(state='starting', message='Checking for the drone...')
    threading.Thread(target=auto_watch, daemon=True, name='drone-watcher').start()
    print(f"Watching for the drone every {AUTO_POLL_SECONDS:g} s (last known at {PI_URL}; "
          "searches the Wi-Fi automatically if the address changed)")


@app.route('/drone/latest', methods=['GET'])
def drone_latest():
    """Newest automatically analyzed flight (full result for the NDVI page) + watcher status."""
    latest = None
    if os.path.isdir(CAPTURE_DIR):
        for name in os.listdir(CAPTURE_DIR):
            data = _read_json(os.path.join(CAPTURE_DIR, name, AUTO_RESULT_FILE))
            if data and (latest is None or data.get('processed_at', 0) > latest.get('processed_at', 0)):
                latest = data
    return jsonify({'status': dict(_auto_status), 'result': latest})


@app.route('/drone/captures', methods=['GET'])
def drone_captures():
    """Flights already imported to this laptop (works without the Pi)."""
    out = []
    if os.path.isdir(CAPTURE_DIR):
        for name in sorted(os.listdir(CAPTURE_DIR), reverse=True):
            meta_path = os.path.join(CAPTURE_DIR, name, 'pairs.json')
            if os.path.isfile(meta_path):
                with open(meta_path, encoding='utf-8') as f:
                    meta = json.load(f)
                auto = _read_json(os.path.join(CAPTURE_DIR, name, AUTO_RESULT_FILE)) or {}
                meta['auto_pair'] = auto.get('pair')      # pair chosen by the automatic analysis
                out.append(meta)
    return jsonify(out)


@app.route('/captures/<flight>/<filename>', methods=['GET'])
def capture_file(flight, filename):
    path = capture_path(flight, filename)
    return send_from_directory(os.path.dirname(path), os.path.basename(path))


@app.route('/history/<field_name>', methods=['GET'])
def get_history(field_name):
    """Get analysis history for a field from Firebase."""
    try:
        history = get_field_history(field_name)
        return jsonify({'success': True, 'data': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/field-assessment', methods=['GET'])
def field_assessment():
    """Latest drone analysis of the zone + latest reading of every soil node → one result."""
    ndvi = load_latest_ndvi()
    if ndvi is None:
        return jsonify({'error': 'No drone analysis yet. Analyze an image on the NDVI page first.'}), 404
    try:
        readings = latest_soil_readings()
    except (urllib.error.URLError, OSError, ValueError) as e:
        return jsonify({'error': f'Cannot reach the soil backend at {SOIL_API_URL} '
                                 f'({e.__class__.__name__}). Is server.js running?'}), 503
    if not readings:
        return jsonify({'error': 'No soil readings yet from the sensor nodes.'}), 404

    warnings = []
    if ndvi.get('source') != 'drone':
        warnings.append('Aerial result is from an uploaded image, not a drone capture.')
    if ndvi.get('method', 'cnn') != 'ndvi_cnn':
        warnings.append('No NoIR photo: the aerial result comes from the CNN only, without NDVI.')

    # Only combine soil readings taken close to the drone capture
    allow_stale = request.args.get('allow_stale') == '1'
    gap_ms = SOIL_MAX_GAP_HOURS * 3600 * 1000
    recent = [r for r in readings
              if r.get('timestamp') is not None and abs(r['timestamp'] - ndvi['timestamp']) <= gap_ms]
    if not recent:
        newest = max((r['timestamp'] for r in readings if r.get('timestamp') is not None), default=None)
        msg = (f'No soil reading within {SOIL_MAX_GAP_HOURS:g} h of the drone capture '
               f'({_fmt_ms(ndvi["timestamp"])}). Newest soil reading: '
               f'{_fmt_ms(newest) if newest else "unknown"}.')
        if not allow_stale:
            return jsonify({'error': msg, 'stale': True}), 409
        warnings.append(msg + ' Showing it anyway — not a valid combined result.')
        recent = readings
    elif len(recent) < len(readings):
        skipped = sorted({r['node_id'] for r in readings} - {r['node_id'] for r in recent})
        warnings.append(f'Left out node(s) {", ".join(skipped)}: no reading within '
                        f'{SOIL_MAX_GAP_HOURS:g} h of the drone capture.')

    # 0 % moisture or 0 EC = probe not in the soil, not a soil condition
    probe_out = [r for r in recent if probe_not_in_soil(r['humidity'], r['ec'])]
    recent    = [r for r in recent if not probe_not_in_soil(r['humidity'], r['ec'])]
    if probe_out:
        warnings.append(f'Left out node(s) {", ".join(r["node_id"] for r in probe_out)}: '
                        'probe not reading soil (0% moisture or 0 EC). Check the probe.')
    if not recent:
        return jsonify({'error': 'No usable soil reading: every node reads 0% moisture or 0 EC. '
                                 'Check that the probes are in the soil.',
                        'probe_out': probe_out}), 409

    soil  = predict_soil_zone(recent)
    final = combine(soil['probabilities'], ndvi['class_probabilities'])
    return jsonify({
        'success':    True,
        'final':      final,
        'ndvi':       ndvi,
        'soil':       soil,
        'probe_out':  probe_out,
        'warnings':   warnings,
        'thresholds': {'healthy_min': HEALTHY_MIN, 'moderate_min': MODERATE_MIN},
    })


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'model': 'ndvi_cnn_rgb_tiles',
                    'ndvi_thresholds': {'poor_max': NDVI_POOR_MAX, 'moderate_max': NDVI_MODERATE_MAX}})

def get_recommendation(health_class, ndvi):
    """Returns actionable recommendation based on CNN output."""
    recs = {
        'healthy':  f'NDVI {ndvi:.2f} — Crops are healthy. Continue current irrigation schedule.',
        'moderate': f'NDVI {ndvi:.2f} — Moderate stress detected. Check soil moisture and nutrients.',
        'poor':     f'NDVI {ndvi:.2f} — Severe stress. Immediate intervention required. Check for disease or drought.'
    }
    return recs.get(health_class, 'Analysis complete.')

if __name__ == '__main__':
    # debug=True starts this file twice (auto-reloader); watch only in the serving process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_auto_watch()
    app.run(debug=True, port=5000)