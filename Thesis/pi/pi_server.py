"""
SoCFA — capture server (runs on the Raspberry Pi after landing)

Shares the flights recorded by pi_capture.py over Wi-Fi, so app.py on the
laptop can import them. It never changes or deletes captures; the only action
is POST /capture, which starts pi_capture.py to take photos right away.

Start:      python3 pi_server.py          (port 8000)
Requires:   pip install flask   (or: sudo apt install python3-flask)

  GET /flights                     -> list of flights
  GET /flights/<flight>            -> that flight's pairs.json
  GET /files/<flight>/<filename>   -> one image
  POST /capture  {"count": 10}     -> take photo pairs now (dashboard "Take Photos" button)
  GET /capture                     -> is a capture running?
"""
import json
import os
import re
import subprocess
import sys

from flask import Flask, abort, jsonify, request, send_from_directory

CAPTURE_DIR    = os.path.expanduser('~/socfa_captures')
CAPTURE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pi_capture.py')
CAPTURE_LOG    = os.path.join(CAPTURE_DIR, 'manual_capture.log')
app = Flask(__name__)


def capture_running():
    """True while any pi_capture.py runs (button or the boot capture): the
    cameras can only be used by one program at a time."""
    return subprocess.run(['pgrep', '-f', 'pi_capture.py'], stdout=subprocess.DEVNULL).returncode == 0


def flight_dir(flight):
    path = os.path.realpath(os.path.join(CAPTURE_DIR, flight))
    if not path.startswith(os.path.realpath(CAPTURE_DIR) + os.sep) or not os.path.isdir(path):
        abort(404)
    return path


@app.get('/flights')
def flights():
    out = []
    for name in sorted(os.listdir(CAPTURE_DIR), reverse=True) if os.path.isdir(CAPTURE_DIR) else []:
        meta_path = os.path.join(CAPTURE_DIR, name, 'pairs.json')
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            out.append({'flight': name, 'pairs': len(meta['pairs']),
                        'started': meta['pairs'][0]['time'] if meta['pairs'] else None,
                        'target': meta.get('target'),        # pairs planned for this flight
                        # finished capturing → app.py may analyze it automatically
                        'complete': bool(meta.get('complete', False)),
                        'spot': meta.get('spot')})
    return jsonify(out)


@app.get('/flights/<flight>')
def flight(flight):
    with open(os.path.join(flight_dir(flight), 'pairs.json')) as f:
        return jsonify(json.load(f))


@app.get('/files/<flight>/<filename>')
def files(flight, filename):
    return send_from_directory(flight_dir(flight), filename)


@app.get('/capture')
def capture_status():
    return jsonify({'running': capture_running()})


@app.post('/capture')
def capture_now():
    """Take photo pairs right away (no boot delay)."""
    if capture_running():
        return jsonify({'error': 'The drone is already taking photos. Wait until it finishes.'}), 409
    body = request.get_json(silent=True) or {}
    count = max(1, min(int(body.get('count', 10)), 30))
    spot = re.sub(r'[^A-Za-z0-9_-]', '', str(body.get('spot') or ''))[:20]    # e.g. A-03
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    with open(CAPTURE_LOG, 'a') as log:
        subprocess.Popen([sys.executable, CAPTURE_SCRIPT, '--manual', '--delay', '0', '--count', str(count),
                          '--spot', spot],
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return jsonify({'success': True, 'count': count, 'spot': spot or None})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
