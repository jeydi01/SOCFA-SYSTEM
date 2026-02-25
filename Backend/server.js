const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

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
    const query = 'SELECT * FROM soil_data WHERE node_id = ? ORDER BY timestamp DESC';
    db.query(query, [nodeId], (err, results) => {
        if (err) return res.status(500).json({ error: 'Database query failed' });
        res.json(results);
    });
});

// Open dashboard in browser automatically
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});


// Serve dashboard folder
app.use(express.static(path.join(__dirname, '../Thesis')));
