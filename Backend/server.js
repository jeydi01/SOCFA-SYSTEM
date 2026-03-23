const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

// Serve dashboard folder
app.use(express.static(path.join(__dirname, '../Thesis')));

// Connect to MySQL
const db = mysql.createConnection({
    host: 'localhost',
    user: 'root',
    password: 'socfa', // add your MySQL password if any
    database: 'socfa_db'
});

db.connect(err => {
    if (err) {
        console.log("Database error:", err);
    } else {
        console.log("MySQL Connected to socfa_db");
    }
});

// Route to test backend
app.get('/api', (req, res) => {
    res.send("Backend running");
});

// Fetch all soil data
app.get('/soil-data', (req, res) => {
    const query = 'SELECT * FROM soil_data ORDER BY timestamp DESC';
    db.query(query, (err, results) => {
        if (err) return res.status(500).json({ error: 'Database query failed' });
        res.json(results);
    });
});

// Fetch soil data by node
app.get('/soil-data/:node_id', (req, res) => {
    const nodeId = req.params.node_id;
    const range = req.query.range || 'realtime'; // default to realtime

    let query = 'SELECT * FROM soil_data WHERE node_id = ?';
    const params = [nodeId];

    const now = new Date();

    if (range === 'day') {
        query += ' AND timestamp >= ?';
        params.push(new Date(now - 24*60*60*1000)); // last 24 hours
    } else if (range === 'lastWeek') {
        query += ' AND timestamp >= ?';
        params.push(new Date(now - 7*24*60*60*1000)); // last 7 days
    } else if (range === 'lastMonth') {
        const lastMonth = new Date();
        lastMonth.setMonth(now.getMonth() - 1);
        query += ' AND timestamp >= ?';
        params.push(lastMonth); // last month
    }

    query += ' ORDER BY timestamp DESC LIMIT 1';

    db.query(query, params, (err, results) => {
        if (err) return res.status(500).json({ error: 'Database query failed' });
        res.json(results);
    });
});

// Endpoint for ESP32 soil sensor data
app.post('/soil-data', (req, res) => {
    const { node_id, temperature, humidity, ec, ph } = req.body;

    if (!node_id || temperature === undefined || humidity === undefined || ec === undefined || ph === undefined) {
        return res.status(400).send("Missing sensor data");
    }

    const sql = `
        INSERT INTO soil_data (node_id, temperature, humidity, ec, ph)
        VALUES (?, ?, ?, ?, ?)
    `;
    db.query(sql, [node_id, temperature, humidity, ec, ph], (err, result) => {
        if (err) {
            console.error("Database error:", err);
            return res.status(500).send("Database error");
        }
        res.send("Soil data inserted successfully");
    });
});

// Open dashboard in browser automatically
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});


