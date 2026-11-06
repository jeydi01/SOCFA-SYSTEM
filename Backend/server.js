const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const path = require('path');

const app = express();

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb' }));

// Serve dashboard folder
app.use(express.static(path.join(__dirname, '../Thesis')));

// Initialize Firebase
try {
    const serviceAccount = require('./firebase-key.json');
    
    admin.initializeApp({
        credential: admin.credential.cert(serviceAccount),
        databaseURL: "https://socfa-361f7-default-rtdb.asia-southeast1.firebasedatabase.app"
    });
    
    console.log("Firebase Initialized Successfully");
} catch (error) {
    console.error("Firebase initialization error:", error.message);
    console.error("Please add your firebase-key.json file to the Backend directory");
}

const db = admin.database();

// ===============================
// TEST ROUTE
// ===============================
app.get('/api', (req, res) => {
    res.send("Backend running");
});

// ===============================
// SOIL DATA ROUTES
// ===============================
app.get('/soil-data', async (req, res) => {
    try {
        const snapshot = await db.ref('soil_data').orderByChild('timestamp').limitToLast(100).once('value');
        const data = snapshot.val();
        
        if (!data) {
            return res.json([]);
        }
        
        // Convert to array and sort by timestamp descending
        const results = Object.keys(data).map(key => ({
            id: key,
            ...data[key]
        })).sort((a, b) => b.timestamp - a.timestamp);
        
        res.json(results);
    } catch (err) {
        console.error("Database error:", err);
        return res.status(500).json({ error: 'Database query failed' });
    }
});

// Fetch soil data by node + range
app.get('/soil-data/:node_id', async (req, res) => {
    try {
        const nodeId = req.params.node_id;
        const range = req.query.range || 'realtime';
        
        const snapshot = await db.ref(`soil_data`).orderByChild('node_id').equalTo(String(nodeId)).once('value');
        const data = snapshot.val();
        
        if (!data) {
            return res.json([]);
        }
        
        const now = new Date().getTime();
        let filteredData = Object.keys(data).map(key => ({
            id: key,
            ...data[key]
        }));

        // Filter by range
        if (range === 'day') {
            filteredData = filteredData.filter(d => (now - d.timestamp) <= 24 * 60 * 60 * 1000);
        } else if (range === 'lastWeek') {
            filteredData = filteredData.filter(d => (now - d.timestamp) <= 7 * 24 * 60 * 60 * 1000);
        } else if (range === 'lastMonth') {
            filteredData = filteredData.filter(d => (now - d.timestamp) <= 30 * 24 * 60 * 60 * 1000);
        } else if (range === 'realtime') {
            filteredData = filteredData.slice(-1); // Only last reading
        }

        // Sort by timestamp descending
        filteredData.sort((a, b) => b.timestamp - a.timestamp);
        
        res.json(filteredData);
    } catch (err) {
        console.error("Database error:", err);
        return res.status(500).json({ error: 'Database query failed' });
    }
});

// ===============================
// SENSOR DATA INSERT (ESP32)
// ===============================
app.post('/soil-data', async (req, res) => {
    try {
        const { node_id, temperature, humidity, ec, ph } = req.body;

        if (!node_id || temperature === undefined || humidity === undefined || ec === undefined || ph === undefined) {
            return res.status(400).send("Missing sensor data");
        }

        const timestamp = new Date().getTime();
        const newRef = db.ref('soil_data').push();

        await newRef.set({
            node_id: String(node_id),
            temperature: parseFloat(temperature),
            humidity: parseFloat(humidity),
            ec: parseFloat(ec),
            ph: parseFloat(ph),
            timestamp: timestamp
        });

        res.send("Soil data inserted successfully");
    } catch (err) {
        console.error("Database error:", err);
        return res.status(500).send("Database error");
    }
});

// ===============================
// NODES ROUTES
// ===============================

// GET ALL NODES
app.get('/nodes', async (req, res) => {
    try {
        const snapshot = await db.ref('nodes').once('value');
        const data = snapshot.val();
        
        if (!data) {
            return res.json([]);
        }
        
        const results = Object.keys(data).map(key => ({
            node_id: key,
            ...data[key]
        }));
        
        res.json(results);
    } catch (err) {
        console.error(err);
        return res.status(500).json({ error: 'Failed to fetch nodes' });
    }
});

// ADD NEW NODE
app.post('/nodes', async (req, res) => {
    try {
        const { node_id, name } = req.body;

        console.log("Incoming node:", req.body);

        if (!node_id || !name) {
            return res.status(400).json({ error: 'Missing node_id or name' });
        }

        await db.ref(`nodes/${node_id}`).set({
            node_id: node_id,
            name: name,
            createdAt: new Date().getTime()
        });

        res.json({ message: 'Node added successfully' });
    } catch (err) {
        console.error("DB ERROR:", err);
        return res.status(500).json({ error: 'Failed to add node' });
    }
});

// DELETE NODE
app.delete('/nodes/:node_id', async (req, res) => {
    try {
        const node_id = req.params.node_id;
        
        const snapshot = await db.ref(`nodes/${node_id}`).once('value');
        
        if (!snapshot.exists()) {
            return res.status(404).json({ error: 'Node not found' });
        }

        await db.ref(`nodes/${node_id}`).remove();
        res.json({ message: 'Node deleted successfully' });
    } catch (err) {
        console.error('DB ERROR:', err);
        return res.status(500).json({ error: 'Failed to delete node' });
    }
});

// ===============================
// DRONE NDVI ANALYSIS ROUTES
// ===============================

// Calculate NDVI from image (requires Red and Near-Infrared bands)
function calculateNDVI(redBand, nirBand) {
    if (nirBand + redBand === 0) return 0;
    return (nirBand - redBand) / (nirBand + redBand);
}

// Determine plant health status based on NDVI
function getHealthStatus(ndvi) {
    if (ndvi >= 0.7) return { status: 'Excellent', color: '#22c55e' }; // Green
    if (ndvi >= 0.5) return { status: 'Good', color: '#84cc16' }; // Lime
    if (ndvi >= 0.3) return { status: 'Fair', color: '#eab308' }; // Yellow
    if (ndvi >= 0.1) return { status: 'Poor', color: '#f97316' }; // Orange
    return { status: 'Dead/Barren', color: '#ef4444' }; // Red
}

// POST - Submit drone NDVI analysis
app.post('/drone-analysis', async (req, res) => {
    try {
        const { node_id, ndvi, image_url, latitude, longitude, altitude } = req.body;

        if (!node_id || ndvi === undefined) {
            return res.status(400).json({ error: 'Missing node_id or ndvi value' });
        }

        const timestamp = new Date().getTime();
        const healthInfo = getHealthStatus(ndvi);

        const analysisData = {
            node_id: String(node_id),
            ndvi: parseFloat(ndvi),
            health_status: healthInfo.status,
            color: healthInfo.color,
            image_url: image_url || null,
            latitude: latitude || null,
            longitude: longitude || null,
            altitude: altitude || null,
            timestamp: timestamp
        };

        const newRef = db.ref('drone_analysis').push();
        await newRef.set(analysisData);

        res.json({ 
            message: 'NDVI analysis saved',
            id: newRef.key,
            ...analysisData
        });
    } catch (err) {
        console.error("Database error:", err);
        return res.status(500).json({ error: 'Failed to save NDVI analysis' });
    }
});

// GET - Get all drone analyses
app.get('/drone-analysis', async (req, res) => {
    try {
        const snapshot = await db.ref('drone_analysis').orderByChild('timestamp').limitToLast(100).once('value');
        const data = snapshot.val();
        
        if (!data) {
            return res.json([]);
        }
        
        const results = Object.keys(data).map(key => ({
            id: key,
            ...data[key]
        })).sort((a, b) => b.timestamp - a.timestamp);
        
        res.json(results);
    } catch (err) {
        console.error("Database error:", err);
        return res.status(500).json({ error: 'Failed to fetch drone analyses' });
    }
});

// GET - Get drone analyses for specific node
app.get('/drone-analysis/:node_id', async (req, res) => {
    try {
        const nodeId = req.params.node_id;
        const snapshot = await db.ref('drone_analysis').orderByChild('node_id').equalTo(String(nodeId)).once('value');
        const data = snapshot.val();
        
        if (!data) {
            return res.json([]);
        }
        
        const results = Object.keys(data).map(key => ({
            id: key,
            ...data[key]
        })).sort((a, b) => b.timestamp - a.timestamp);
        
        res.json(results);
    } catch (err) {
        console.error("Database error:", err);
        return res.status(500).json({ error: 'Failed to fetch drone analyses for node' });
    }
});

// GET - Get latest NDVI for each node (dashboard summary)
app.get('/health-status/summary', async (req, res) => {
    try {
        const snapshot = await db.ref('drone_analysis').once('value');
        const data = snapshot.val();
        
        if (!data) {
            return res.json([]);
        }

        const allAnalyses = Object.keys(data).map(key => ({
            id: key,
            ...data[key]
        }));

        // Get latest analysis per node
        const latestByNode = {};
        allAnalyses.forEach(analysis => {
            const nodeId = analysis.node_id;
            if (!latestByNode[nodeId] || analysis.timestamp > latestByNode[nodeId].timestamp) {
                latestByNode[nodeId] = analysis;
            }
        });

        const summary = Object.values(latestByNode).sort((a, b) => b.timestamp - a.timestamp);
        res.json(summary);
    } catch (err) {
        console.error("Database error:", err);
        return res.status(500).json({ error: 'Failed to fetch health summary' });
    }
});

// ===============================
// START SERVER
// ===============================
const PORT = 3000;

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});