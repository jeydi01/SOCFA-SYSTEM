"""
SoCFA — drone capture (runs on the Raspberry Pi, both cameras on the 2 CSI ports)

HOVER MODE (default, used in deployment)
  Waits DELAY seconds (time to take off and reach the hover position over the
  zone), then takes COUNT RGB + NoIR photo pairs, INTERVAL seconds apart, and
  marks the flight complete. After landing, app.py on the laptop picks it up
  automatically, analyzes the sharpest pair and updates the dashboard.

      python3 pi_capture.py                       (delay 60 s, 5 pairs)
      python3 pi_capture.py --delay 90 --count 5

  Started automatically at boot by socfa-capture.service. To boot the Pi
  without capturing (e.g. on the desk):   touch ~/socfa_no_capture
  and remove that file again before flying.

DASHBOARD BUTTON  "Take Photos" on the NDVI page: pi_server.py runs
                  python3 pi_capture.py --manual --delay 0 --count 10
CONTINUOUS MODE   python3 pi_capture.py --continuous     (Ctrl+C to stop)
TEST              python3 pi_capture.py --test           (which port has which camera)

Photos are stored per flight:

  ~/socfa_captures/flight_YYYYMMDD_HHMMSS/
      0001_rgb.jpg   0001_noir.jpg
      0002_rgb.jpg   0002_noir.jpg
      pairs.json     (time of each pair, camera settings, "complete")

Requires: picamera2 (preinstalled on Raspberry Pi OS Bookworm).
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from picamera2 import Picamera2

RGB_CAM    = 0          # CSI port of the Camera Module V2 (RGB)  — swap if --test shows otherwise
NOIR_CAM   = 1          # CSI port of the NoIR Camera V2
INTERVAL   = 3.0        # seconds between pairs
RESOLUTION = (3280, 2464)
# NoIR colour gains (red, blue) fixed for every flight, so NDVI values are comparable
# between days (auto white balance would pick different gains each time).
# Changing them invalidates the red-NDVI calibration: run calibrate_red_ndvi.py again.
NOIR_COLOUR_GAINS = (1.0, 1.0)
OUT_DIR    = os.path.expanduser('~/socfa_captures')
SKIP_FILE  = os.path.expanduser('~/socfa_no_capture')   # exists → don't capture at boot


def open_camera(num, tuning=None, colour_gains=None):
    tuning_data = Picamera2.load_tuning_file(tuning) if tuning else None
    cam = Picamera2(num, tuning=tuning_data)
    cam.configure(cam.create_still_configuration(main={'size': RESOLUTION}))
    cam.start()
    if colour_gains:                   # fixed white balance (NoIR camera)
        cam.set_controls({'AwbEnable': False, 'ColourGains': tuple(colour_gains)})
    time.sleep(2)                      # let exposure (and white balance) settle
    return cam


def lock_camera(cam):
    """Freeze exposure, gain and white balance at what auto chose, and return them.
    Blue NDVI compares two channels of the NoIR photo; red NDVI compares the NoIR
    photo with the RGB photo, so both cameras must keep fixed, known settings."""
    md = cam.capture_metadata()
    cam.set_controls({'AeEnable': False, 'ExposureTime': md['ExposureTime'],
                      'AnalogueGain': md['AnalogueGain'],
                      'AwbEnable': False, 'ColourGains': md['ColourGains']})
    time.sleep(0.5)
    return {'exposure_us': int(md['ExposureTime']), 'analogue_gain': float(md['AnalogueGain']),
            'digital_gain': float(md.get('DigitalGain', 1.0)), 'colour_gains': [float(g) for g in md['ColourGains']]}


def save_meta(folder, meta):
    path = os.path.join(folder, 'pairs.json')
    with open(path + '.part', 'w') as f:
        json.dump(meta, f, indent=2)
    os.replace(path + '.part', path)   # written every pair: safe if power is cut


def main():
    ap = argparse.ArgumentParser(description='SoCFA drone capture')
    ap.add_argument('--test', action='store_true', help='save one test pair and exit')
    ap.add_argument('--continuous', action='store_true', help='capture until Ctrl+C')
    ap.add_argument('--delay', type=float, default=60, help='hover mode: seconds before capturing (default 60)')
    ap.add_argument('--count', type=int, default=5, help='hover mode: number of pairs (default 5)')
    ap.add_argument('--manual', action='store_true', help='started by the dashboard button (ignores the no-capture file)')
    ap.add_argument('--spot', default='', help='spot / zone label typed on the dashboard (e.g. A-03)')
    args = ap.parse_args()

    if not args.test and not args.manual and os.path.exists(SKIP_FILE):
        print(f'{SKIP_FILE} exists — not capturing. Delete it before flying.')
        return

    print('Opening cameras...')
    rgb = open_camera(RGB_CAM)
    noir = open_camera(NOIR_CAM, 'imx219_noir.json', NOIR_COLOUR_GAINS)

    if args.test:
        lock_camera(rgb); lock_camera(noir)
        os.makedirs(OUT_DIR, exist_ok=True)
        rgb.capture_file(os.path.join(OUT_DIR, 'test_rgb.jpg'))
        noir.capture_file(os.path.join(OUT_DIR, 'test_noir.jpg'))
        print(f'Saved test_rgb.jpg and test_noir.jpg in {OUT_DIR}.')
        print('test_noir.jpg should look pink/purple. If it is test_rgb.jpg instead, swap RGB_CAM and NOIR_CAM.')
        return

    if not args.continuous and args.delay > 0:
        print(f'Hover mode: capturing in {args.delay:.0f} s — take off and hover over the zone.')
        time.sleep(args.delay)          # cameras keep adjusting to the light meanwhile

    # Lock both cameras now, over the field (not on the ground at boot)
    rgb_settings, noir_settings = lock_camera(rgb), lock_camera(noir)

    flight = datetime.now().strftime('flight_%Y%m%d_%H%M%S')
    folder = os.path.join(OUT_DIR, flight)
    os.makedirs(folder)
    meta = {'flight': flight, 'mode': 'manual' if args.manual else 'continuous' if args.continuous else 'hover',
            'spot': args.spot.strip()[:20] or None,                   # matches the field rating in the log
            'resolution': RESOLUTION, 'noir_colour_gains': noir_settings['colour_gains'],
            'cameras': {'rgb': rgb_settings, 'noir': noir_settings},   # for red NDVI
            'target': None if args.continuous else args.count,   # pairs planned (dashboard progress)
            'complete': False, 'pairs': []}
    save_meta(folder, meta)
    total = meta['target']
    print(f'Recording {flight} — one pair every {INTERVAL:.0f}s'
          + (' until Ctrl+C.' if total is None else f', {total} pairs.'))

    n = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        try:
            while total is None or n < total:
                started = time.time()
                n += 1
                rgb_name, noir_name = f'{n:04d}_rgb.jpg', f'{n:04d}_noir.jpg'
                # trigger both cameras together so the pair shows the same ground
                jobs = [pool.submit(rgb.capture_file, os.path.join(folder, rgb_name)),
                        pool.submit(noir.capture_file, os.path.join(folder, noir_name))]
                for job in jobs:
                    job.result()
                meta['pairs'].append({'id': n, 'time': datetime.now().isoformat(timespec='seconds'),
                                      'rgb': rgb_name, 'noir': noir_name})
                save_meta(folder, meta)
                print(f'  pair {n:04d} saved')
                if total is None or n < total:
                    time.sleep(max(0.0, INTERVAL - (time.time() - started)))
        except KeyboardInterrupt:
            pass
    rgb.stop(); noir.stop()

    # "complete" tells app.py the flight is finished and can be analyzed
    meta['complete'] = True
    save_meta(folder, meta)
    print(f'Done. {len(meta["pairs"])} pairs in {folder} — land; the dashboard updates after landing.')


if __name__ == '__main__':
    main()
