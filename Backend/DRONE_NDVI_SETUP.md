# SOCFA System - Firebase Realtime Database Setup & Drone NDVI Integration

✅ **Firebase credentials are configured!**

Your backend is now set up with:
- Firebase Realtime Database (Real-time sensor data)
- Drone NDVI Analysis endpoints
- Plant Health Status tracking

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd Backend
npm install
```

### 2. Start the Server
```bash
npm start
```

Expected output:
```
Firebase Initialized Successfully
Server running on port 3000
```

---

## 📊 API Endpoints

### **Sensor Data (ESP32)**

#### Get all soil data
```
GET /soil-data
```
Returns all sensor readings sorted by newest first.

#### Get soil data for a specific node
```
GET /soil-data/:node_id?range=realtime|day|lastWeek|lastMonth
```
Example:
```
GET /soil-data/1?range=day
```

#### Add new soil reading
```
POST /soil-data
Content-Type: application/json

{
  "node_id": "1",
  "temperature": 28.5,
  "humidity": 65.3,
  "ec": 1.2,
  "ph": 6.8
}
```

---

### **Node Management**

#### Get all nodes
```
GET /nodes
```

#### Add a new node
```
POST /nodes
Content-Type: application/json

{
  "node_id": "1",
  "name": "Field A - North"
}
```

#### Delete a node
```
DELETE /nodes/:node_id
```

---

### **🚁 Drone NDVI Analysis** (NEW!)

#### Submit NDVI analysis from drone
```
POST /drone-analysis
Content-Type: application/json

{
  "node_id": "1",
  "ndvi": 0.65,
  "image_url": "https://storage.example.com/image.jpg",
  "latitude": 14.5234,
  "longitude": 121.0234,
  "altitude": 50
}
```

Response:
```json
{
  "message": "NDVI analysis saved",
  "id": "analysis_id_123",
  "node_id": "1",
  "ndvi": 0.65,
  "health_status": "Good",
  "color": "#84cc16",
  "timestamp": 1682913456000
}
```

#### Get all NDVI analyses
```
GET /drone-analysis
```
Returns all analyses sorted by newest first.

#### Get NDVI for specific node
```
GET /drone-analysis/:node_id
```
Example:
```
GET /drone-analysis/1
```

#### Get health status summary
```
GET /health-status/summary
```
Returns the latest health status for each node (perfect for dashboard).

---

## 📈 NDVI Health Status Scale

| NDVI Range | Status | Color | Meaning |
|-----------|--------|-------|---------|
| 0.7 - 1.0 | **Excellent** | 🟢 Green | Very healthy vegetation |
| 0.5 - 0.7 | **Good** | 🟡 Lime | Healthy vegetation |
| 0.3 - 0.5 | **Fair** | 🟠 Yellow | Moderate vegetation stress |
| 0.1 - 0.3 | **Poor** | 🟠 Orange | Low vegetation/stressed |
| < 0.1 | **Dead/Barren** | 🔴 Red | No vegetation or water |

---

## 🎯 Example: Complete Drone Workflow

### 1. Drone captures image over field
- Extracts Red band and Near-Infrared (NIR) band from multispectral camera
- Calculates NDVI for the area

### 2. Send to backend
```bash
curl -X POST http://localhost:3000/drone-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "1",
    "ndvi": 0.72,
    "image_url": "https://storage.example.com/field-a-20260427.jpg",
    "latitude": 14.5234,
    "longitude": 121.0234,
    "altitude": 50
  }'
```

### 3. Backend stores analysis and determines health
- Calculates health status: "Excellent" ✅
- Stores image URL and GPS coordinates
- Records timestamp automatically

### 4. Frontend retrieves summary
```
GET /health-status/summary
```
Response shows latest health for all fields:
```json
[
  {
    "id": "abc123",
    "node_id": "1",
    "ndvi": 0.72,
    "health_status": "Excellent",
    "color": "#22c55e",
    "altitude": 50,
    "timestamp": 1682913456000
  }
]
```

---

## 💾 Firebase Database Structure

```
socfa-361f7 (Realtime Database)
├── nodes/
│   ├── 1/
│   │   ├── node_id: "1"
│   │   ├── name: "Field A - North"
│   │   └── createdAt: 1682913456000
│   └── 2/
│       ├── node_id: "2"
│       ├── name: "Field B - South"
│       └── createdAt: 1682913456000
│
├── soil_data/
│   ├── push_id_1/
│   │   ├── node_id: "1"
│   │   ├── temperature: 28.5
│   │   ├── humidity: 65.3
│   │   ├── ec: 1.2
│   │   ├── ph: 6.8
│   │   └── timestamp: 1682913456000
│   └── push_id_2/
│       └── ...
│
└── drone_analysis/
    ├── analysis_1/
    │   ├── node_id: "1"
    │   ├── ndvi: 0.72
    │   ├── health_status: "Excellent"
    │   ├── color: "#22c55e"
    │   ├── image_url: "https://..."
    │   ├── latitude: 14.5234
    │   ├── longitude: 121.0234
    │   ├── altitude: 50
    │   └── timestamp: 1682913456000
    └── analysis_2/
        └── ...
```

---

## 🔧 Testing Endpoints

### Using cURL (Command line)

**Test soil data insert:**
```bash
curl -X POST http://localhost:3000/soil-data \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "1",
    "temperature": 28.5,
    "humidity": 65.3,
    "ec": 1.2,
    "ph": 6.8
  }'
```

**Test getting nodes:**
```bash
curl http://localhost:3000/nodes
```

**Test drone analysis:**
```bash
curl -X POST http://localhost:3000/drone-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "1",
    "ndvi": 0.65,
    "latitude": 14.5234,
    "longitude": 121.0234
  }'
```

### Using Postman / Thunder Client

1. Open Postman
2. Create new request
3. Select method (GET/POST)
4. Enter URL: `http://localhost:3000/soil-data`
5. If POST, go to Body tab → raw → JSON
6. Send request

---

## 🔐 Firebase Security Rules

For production, update your Firebase security rules to protect your data:

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

For development (less secure), allow reads/writes from your app:
```javascript
{
  "rules": {
    ".read": true,
    ".write": true
  }
}
```

---

## 📝 Frontend Integration

Your frontend (ndvi.js, soil.js) needs to be updated to use the new drone endpoints.

Example fetch for health summary:
```javascript
async function getHealthSummary() {
  const response = await fetch('http://localhost:3000/health-status/summary');
  const data = await response.json();
  
  // Display health status for each field
  data.forEach(field => {
    console.log(`${field.node_id}: ${field.health_status} (NDVI: ${field.ndvi})`);
  });
}
```

---

## ⚠️ Important Notes

1. **firebase-key.json** - Never commit this to GitHub!
   - Added to .gitignore automatically

2. **Timestamps** - All timestamps are in milliseconds (UNIX time)
   - JavaScript: `new Date(timestamp)`

3. **NDVI Calculation** - Formula:
   ```
   NDVI = (NIR - RED) / (NIR + RED)
   ```
   - Where NIR = Near-Infrared band, RED = Red band

4. **Real-time Updates** - Firebase Realtime Database supports listeners:
   ```javascript
   db.ref('drone_analysis').on('child_added', (snapshot) => {
     console.log('New analysis:', snapshot.val());
   });
   ```

---

## 🐛 Troubleshooting

### "Firebase initialization error"
- Make sure `firebase-key.json` exists in Backend folder
- Verify the file path is correct

### "Cannot POST to /drone-analysis"
- Make sure server is running: `npm start`
- Check URL is correct: `http://localhost:3000`

### NDVI values not calculating properly
- Ensure Red and NIR bands are normalized (0-1 range)
- Check for division by zero

### Database connection issues
- Verify internet connection
- Check Firebase project is active
- Ensure service account has permissions

---

## 🎉 You're All Set!

Your SOCFA System is now ready to:
✅ Collect real-time soil sensor data  
✅ Analyze drone NDVI images  
✅ Track plant health status  
✅ Store and retrieve historical data  

Start the server and begin collecting data!

```bash
npm start
```
