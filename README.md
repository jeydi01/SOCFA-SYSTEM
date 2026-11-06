# SoCFA System

Drone NDVI (Raspberry Pi 5 + RGB and NoIR cameras) + ESP32 soil sensor nodes → one field condition (Healthy / Moderate / Poor) per zone. Colegio de Muntinlupa.

| Part | Folder | Runs on | Port |
|---|---|---|---|
| Website + soil API (Firebase) | `Backend/server.js` | laptop | 3000 |
| NDVI, CNN, Random Forest, Field Assessment, drone import | `Thesis/app.py` | laptop | 5000 |
| Camera capture + photo server | `Thesis/pi/` | Raspberry Pi | 8000 |

## Set up a laptop (Windows), once

1. Install **Git**, **Node.js 24** (nodejs.org) and **Python 3.10** (python.org; tick "Add Python to PATH").
2. Get the code:
   ```
   git clone https://github.com/jeydi01/SOCFA-SYSTEM.git
   cd SOCFA-SYSTEM
   ```
3. Website packages:
   ```
   cd Backend
   npm install
   cd ..
   ```
4. Python packages (takes a while, TensorFlow is big):
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r Thesis/requirements.txt
   ```
5. **Keys (not on GitHub).** Ask the team leader for the two key files, sent privately, and put them here:
   - `Backend/firebase-key.json`
   - `Thesis/serviceAccountKey.json`

   Never upload these files anywhere or commit them.

## Run it (every time)

Open two terminals in the `SOCFA-SYSTEM` folder:

```
cd Backend
node server.js
```

```
.venv\Scripts\activate
cd Thesis
python app.py
```

Then open **http://localhost:3000/ndvi.html** (also `soil.html`, `field.html`).

## In the field

- Connect the laptop to the team's phone hotspot **"no"**. The Pi only joins that hotspot; `app.py` finds it by itself.
- Only one laptop should press **Take Photos** at a time (the Pi takes one capture at a time).
- Before flying: follow `Thesis/data_collection/field_checklist.html`.

## Get the latest version

```
git pull
```

Photos (`Thesis/captures/`) and training images are **not** on GitHub. Back them up to the team's Google Drive.
