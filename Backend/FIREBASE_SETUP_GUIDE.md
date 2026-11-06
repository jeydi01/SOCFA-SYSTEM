# Firebase Realtime Database Setup Guide

Your project has been successfully migrated to **Firebase Realtime Database** with drone NDVI analysis! 

## Key Features

✅ Real-time sensor data from ESP32  
✅ Drone NDVI analysis & plant health tracking  
✅ Geolocation support (latitude, longitude, altitude)  
✅ Image storage integration ready  
✅ Historical data with timestamps  

---

## Step 1: Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Click "Add project" and follow the setup wizard
3. Choose a project name (e.g., "SOCFA System")
4. Accept the Firebase terms and create the project

## Step 2: Enable Realtime Database

1. In Firebase Console, go to **Build** > **Realtime Database**
2. Click **Create Database**
3. Choose **Asia-Southeast1** region (or your preferred location)
4. Choose **Start in test mode** for development
5. Click **Create**

**Note**: Your URL will look like:
```
https://socfa-361f7-default-rtdb.asia-southeast1.firebasedatabase.app
```

## Step 3: Generate Service Account Key

1. In Firebase Console, go to **Project Settings** (gear icon)
2. Click **Service Accounts** tab
3. Click **Generate New Private Key**
4. A JSON file will download automatically
5. **IMPORTANT**: Rename it to `firebase-key.json` and place in Backend folder

```
Backend/
├── firebase-key.json  ← Place your downloaded key here
├── package.json
├── server.js
└── ...
```

## Step 4: Install Dependencies

In your Backend folder, run:

```bash
npm install
```

This installs `firebase-admin` and other dependencies.

## Step 5: Start the Server

```bash
npm start
```

Expected output:
```
Firebase Initialized Successfully
Server running on port 3000
```

## Database Structure

Your Realtime Database is organized as:

```
├── nodes/                 ← Sensor node definitions
├── soil_data/            ← Sensor readings (ESP32)
└── drone_analysis/       ← NDVI analysis results from drone
```

---

## API Endpoints

### Soil Data (ESP32)
- `GET /soil-data` - Get all readings
- `GET /soil-data/:node_id?range=realtime|day|lastWeek|lastMonth` - Get by node
- `POST /soil-data` - Add new reading

### Node Management
- `GET /nodes` - List all nodes
- `POST /nodes` - Add new node
- `DELETE /nodes/:node_id` - Delete node

### Drone NDVI Analysis (NEW!)
- `POST /drone-analysis` - Submit NDVI analysis
- `GET /drone-analysis` - Get all analyses
- `GET /drone-analysis/:node_id` - Get analyses for node
- `GET /health-status/summary` - Latest health for all nodes

See [DRONE_NDVI_SETUP.md](./DRONE_NDVI_SETUP.md) for detailed drone integration guide.

---

## Firebase Security Rules

1. In Firebase Console, go to **Realtime Database** > **Rules**
2. Replace the rules with appropriate settings

**For Development (Test Mode):**
```javascript
{
  "rules": {
    ".read": true,
    ".write": true
  }
}
```

**For Production:**
```javascript
{
  "rules": {
    "nodes": {
      ".read": true,
      ".write": "auth != null"
    },
    "soil_data": {
      ".read": true,
      ".write": "auth != null"
    },
    "drone_analysis": {
      ".read": true,
      ".write": "auth != null"
    }
  }
}
```

Click **Publish** to save.

---

## Testing

Test with cURL:

```bash
# Get all nodes
curl http://localhost:3000/nodes

# Add sensor data
curl -X POST http://localhost:3000/soil-data \
  -H "Content-Type: application/json" \
  -d '{"node_id":"1","temperature":28.5,"humidity":65.3,"ec":1.2,"ph":6.8}'

# Submit NDVI analysis
curl -X POST http://localhost:3000/drone-analysis \
  -H "Content-Type: application/json" \
  -d '{"node_id":"1","ndvi":0.65,"latitude":14.5234,"longitude":121.0234}'

# Get health summary
curl http://localhost:3000/health-status/summary
```

---

## Troubleshooting

### "Cannot find module 'firebase-admin'"
```bash
npm install firebase-admin
```

### "firebase-key.json not found"
- Download from Firebase Console > Project Settings > Service Accounts
- Place in Backend folder
- Name it exactly: `firebase-key.json`

### "Permission denied" errors
- Go to **Realtime Database** > **Rules**
- Update security rules (see above)
- Click **Publish**

### Connection issues
- Verify internet connection
- Check Firebase project is active
- Confirm service account key is valid

---

## Key Differences: Realtime DB vs Firestore

| Feature | Realtime DB | Firestore |
|---------|----------|-----------|
| **Real-time** | Native listeners | Yes |
| **Querying** | Limited | Advanced |
| **IoT Data** | ⭐ Better | Good |
| **Structure** | JSON tree | Documents/Collections |
| **Offline** | Basic | Better |
| **Cost** | Lower | Higher |

Realtime Database is perfect for your IoT sensors and drone data!

---

## Next Steps

1. ✅ Set up Firebase Realtime Database
2. ✅ Download service account key → `firebase-key.json`
3. ✅ Run `npm install`
4. ✅ Run `npm start`
5. ✅ Test API endpoints
6. 📖 Read [DRONE_NDVI_SETUP.md](./DRONE_NDVI_SETUP.md) for drone integration
7. 🎨 Update frontend (ndvi.js, soil.js) to use new endpoints

Your SOCFA System is ready! 🚀

