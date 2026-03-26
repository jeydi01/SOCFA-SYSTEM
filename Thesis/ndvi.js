// NDVI Dashboard JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    initDashboard();
    setupEventListeners();
    updateTime();
    
    // Update time every second
    setInterval(updateTime, 1000);
    
    // Update last update time
    updateLastUpdateTime();
});

function initDashboard() {
    console.log('Initializing NDVI Dashboard...');
    
    // Initialize all values to default
    updateValue('connection-status-value', 'Offline');
    updateValue('signal-value', '0%');
    updateValue('battery-value', '0%');
    updateValue('flight-time', '00:00');
    updateValue('area-covered', '0.0 ha');
    updateValue('avg-ndvi', '0.00');
    updateValue('health-score', '0%');
    updateValue('mission-status', 'Idle');
    updateValue('mission-progress-text', '0%');
    updateValue('drone-altitude', '0m');
    updateValue('zoom-level', '1:500');
    
    // Set initial status colors
    updateStatus('connection-status', 'Offline');
    updateStatus('signal-status', 'Poor');
    updateStatus('battery-status', 'Critical');
    updateStatus('mission-status', 'Ready');
    
    // Initialize progress bars
    updateProgressBar('connection-bar', 0);
    updateProgressBar('signal-bar', 0);
    updateProgressBar('battery-bar', 0);
    updateProgressBar('flight-bar', 0);
    updateProgressBar('area-bar', 0);
    updateProgressBar('ndvi-bar', 0);
    updateProgressBar('health-bar', 0);
    updateProgressBar('mission-bar', 0);
    updateProgressBar('mission-progress-bar', 0);
    
    // Update system status
    updateSystemStatus('ready');
    
    // Initialize map coordinates
    updateMapCoordinates(14.599512, 120.984222);
    
    // Initialize sidebar status displays
    updateStatusDisplays();
    
    // Add initial notification
    showNotification('NDVI Dashboard initialized', 'success');
}

function setupEventListeners() {
    console.log('Setting up event listeners...');
    
    // Connect drone button
    document.getElementById('connect-drone-btn').addEventListener('click', function() {
        console.log('Connect drone button clicked');
        openDroneConnectionModal();
    });
    
    // Modal close button
    document.querySelector('.close-modal').addEventListener('click', function() {
        console.log('Close modal button clicked');
        closeModal();
    });
    
    // Test connection button
    document.getElementById('test-connection-btn').addEventListener('click', testConnection);
    
    // Connect drone confirm button
    document.getElementById('connect-drone-confirm-btn').addEventListener('click', connectDrone);
    
    // Mission control buttons
    document.getElementById('start-mission-btn').addEventListener('click', startMission);
    document.getElementById('pause-mission-btn').addEventListener('click', pauseMission);
    document.getElementById('emergency-stop-btn').addEventListener('click', emergencyStop);
    
    // Map control buttons
    document.getElementById('zoom-in-btn').addEventListener('click', zoomIn);
    document.getElementById('zoom-out-btn').addEventListener('click', zoomOut);
    document.getElementById('reset-view-btn').addEventListener('click', resetView);
    document.getElementById('capture-map-btn').addEventListener('click', captureMap);
    
    // REMOVED: Refresh data button event listener
    
    // Field select change
    document.getElementById('field-select').addEventListener('change', function() {
        console.log('Field changed to:', this.value);
        changeField(this.value);
    });
    
    // Flight mode select change
    document.getElementById('flight-mode-select').addEventListener('change', function() {
        console.log('Flight mode changed to:', this.value);
        changeFlightMode(this.value);
    });
    
    // REMOVED: Node click events
    
    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        const modal = document.getElementById('drone-modal');
        if (event.target === modal) {
            closeModal();
        }
    });
    
    // Handle window resize for responsive design
    window.addEventListener('resize', handleResize);
    
    console.log('Event listeners setup complete');
}

// ============================================
// STATUS DISPLAY FUNCTIONS (Non-clickable)
// ============================================

function updateStatusDisplays() {
    const isConnected = isDroneConnected();
    const battery = parseInt(document.getElementById('battery-value').textContent) || 0;
    const signal = parseInt(document.getElementById('signal-value').textContent) || 0;
    
    // Update drone connection display
    updateStatusDisplay('drone-connection-dot', 'drone-connection-status', 
                       isConnected ? 'connected' : 'disconnected',
                       isConnected ? 'Connected' : 'Disconnected');
    
    // Update battery display
    let batteryStatus = 'critical';
    if (battery > 50) batteryStatus = 'good';
    else if (battery > 20) batteryStatus = 'warning';
    
    updateStatusDisplay('battery-status-dot', 'sidebar-battery-value',
                       batteryStatus, battery + '%');
    
    // Update signal display
    let signalStatus = 'critical';
    if (signal > 70) signalStatus = 'good';
    else if (signal > 40) signalStatus = 'warning';
    
    updateStatusDisplay('signal-status-dot', 'sidebar-signal-value',
                       signalStatus, signal + '%');
}

function updateStatusDisplay(dotId, valueId, status, text) {
    const dot = document.getElementById(dotId);
    const valueElement = document.getElementById(valueId);
    
    if (dot) {
        dot.className = 'status-indicator-dot';
        
        switch(status) {
            case 'connected':
            case 'good':
                dot.classList.add('active');
                break;
            case 'warning':
                dot.classList.add('warning');
                break;
            case 'disconnected':
            case 'critical':
                dot.classList.add('critical');
                break;
        }
    }
    
    if (valueElement) {
        valueElement.textContent = text;
        valueElement.className = 'status-value';
        
        switch(status) {
            case 'connected':
            case 'good':
                valueElement.classList.add('good');
                break;
            case 'warning':
                valueElement.classList.add('warning');
                break;
            case 'disconnected':
            case 'critical':
                valueElement.classList.add('critical');
                break;
        }
    }
}

// ============================================
// EXISTING FUNCTIONS (Updated)
// ============================================

// Time Functions
function updateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    const dateString = now.toLocaleDateString('en-US', {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
    
    document.getElementById('current-time').textContent = timeString + ' | ' + dateString;
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit'
    });
    document.getElementById('last-update-time').textContent = timeString;
}

// Drone Connection Functions
function openDroneConnectionModal() {
    console.log('Opening drone connection modal');
    document.getElementById('drone-modal').style.display = 'flex';
}

function closeModal() {
    console.log('Closing modal');
    document.getElementById('drone-modal').style.display = 'none';
}

function testConnection() {
    const ip = document.getElementById('drone-ip').value;
    const type = document.getElementById('connection-type').value;
    
    console.log('Testing connection to', ip, 'via', type);
    showNotification(`Testing connection to ${ip} via ${type}...`, 'info');
    
    // Simulate connection test
    setTimeout(() => {
        showNotification('✓ Connection test successful!', 'success');
    }, 1500);
}

function connectDrone() {
    const ip = document.getElementById('drone-ip').value;
    const type = document.getElementById('connection-type').value;
    
    console.log('Connecting to drone at', ip, 'via', type);
    showNotification(`Connecting to drone at ${ip} via ${type}...`, 'info');
    
    // Update connection status
    updateStatus('connection-status', 'Connecting');
    updateValue('connection-status-value', 'Connecting');
    updateProgressBar('connection-bar', 50);
    
    // Simulate connection process
    setTimeout(() => {
        // Update UI for connected state
        updateStatus('connection-status', 'Connected');
        updateValue('connection-status-value', 'Connected');
        updateProgressBar('connection-bar', 100);
        
        // Hide connection prompt and show map
        document.getElementById('drone-connection-prompt').style.display = 'none';
        showNDVIMap();
        
        // Start simulating data
        startDataSimulation();
        
        // Close modal
        closeModal();
        
        showNotification('✓ Drone connected successfully!', 'success');
        updateSystemStatus('connected');
        
        // Update drone status text
        document.getElementById('drone-status').textContent = 'Connected';
        
        // Update status displays
        updateStatusDisplays();
        
    }, 2000);
}

// Mission Control Functions
function startMission() {
    if (!isDroneConnected()) {
        showNotification('Please connect drone first', 'warning');
        return;
    }
    
    console.log('Starting mission...');
    
    updateValue('mission-status', 'Active');
    updateStatus('mission-status', 'Active');
    updateProgressBar('mission-bar', 50);
    
    // Enable pause button
    document.getElementById('pause-mission-btn').disabled = false;
    
    // Start mission simulation
    simulateMission();
    
    showNotification('Mission started successfully', 'success');
    updateSystemStatus('mission');
}

function pauseMission() {
    if (!isDroneConnected()) return;
    
    console.log('Pausing mission...');
    
    updateValue('mission-status', 'Paused');
    updateStatus('mission-status', 'Paused');
    
    // Pause mission timer
    if (window.missionTimer) {
        clearInterval(window.missionTimer);
    }
    
    showNotification('Mission paused', 'warning');
}

function emergencyStop() {
    if (!isDroneConnected()) return;
    
    if (confirm('Are you sure you want to emergency stop the drone?\n\nThis will immediately halt all operations.')) {
        console.log('Emergency stop activated');
        
        updateValue('mission-status', 'Stopped');
        updateStatus('mission-status', 'Critical');
        updateProgressBar('mission-bar', 0);
        
        // Disable pause button
        document.getElementById('pause-mission-btn').disabled = true;
        
        // Reset mission progress
        if (window.missionTimer) {
            clearInterval(window.missionTimer);
        }
        document.getElementById('mission-progress-text').textContent = '0%';
        document.getElementById('mission-progress-bar').style.width = '0%';
        
        // Reset other values
        updateValue('area-covered', '0.0 ha');
        updateProgressBar('area-bar', 0);
        
        showNotification('⚠️ Emergency stop activated!', 'error');
        updateSystemStatus('connected');
    }
}

function simulateMission() {
    let progress = 0;
    
    // Clear any existing interval
    if (window.missionTimer) {
        clearInterval(window.missionTimer);
    }
    
    console.log('Simulating mission progress...');
    
    window.missionTimer = setInterval(() => {
        progress += Math.random() * 3; // Random progress increment
        
        if (progress > 100) {
            progress = 100;
            clearInterval(window.missionTimer);
            updateValue('mission-status', 'Complete');
            updateStatus('mission-status', 'Complete');
            updateProgressBar('mission-bar', 100);
            document.getElementById('pause-mission-btn').disabled = true;
            showNotification('✓ Mission completed successfully!', 'success');
            updateSystemStatus('connected');
        }
        
        // Update progress display
        const progressPercent = Math.min(100, Math.round(progress));
        document.getElementById('mission-progress-text').textContent = progressPercent + '%';
        document.getElementById('mission-progress-bar').style.width = progressPercent + '%';
        
        // Update other values during mission
        if (progressPercent % 10 === 0) {
            simulateDataUpdate(progressPercent);
        }
        
    }, 1000);
}

// Map Control Functions
function zoomIn() {
    if (!isDroneConnected()) {
        showNotification('Connect drone first', 'warning');
        return;
    }
    
    const zoomElement = document.getElementById('zoom-level');
    const currentZoom = zoomElement.textContent;
    const zoomMatch = currentZoom.match(/1:(\d+)/);
    
    if (zoomMatch) {
        const zoomValue = parseInt(zoomMatch[1]);
        if (zoomValue > 100) {
            const newZoom = zoomValue - 100;
            zoomElement.textContent = `1:${newZoom}`;
            showNotification(`Zoomed in to 1:${newZoom}`, 'info');
            
            // Simulate map update
            simulateMapUpdate();
        } else {
            showNotification('Maximum zoom level reached', 'warning');
        }
    }
}

function zoomOut() {
    if (!isDroneConnected()) {
        showNotification('Connect drone first', 'warning');
        return;
    }
    
    const zoomElement = document.getElementById('zoom-level');
    const currentZoom = zoomElement.textContent;
    const zoomMatch = currentZoom.match(/1:(\d+)/);
    
    if (zoomMatch) {
        const zoomValue = parseInt(zoomMatch[1]);
        const newZoom = zoomValue + 100;
        zoomElement.textContent = `1:${newZoom}`;
        showNotification(`Zoomed out to 1:${newZoom}`, 'info');
        
        // Simulate map update
        simulateMapUpdate();
    }
}

function resetView() {
    if (!isDroneConnected()) {
        showNotification('Connect drone first', 'warning');
        return;
    }
    
    document.getElementById('zoom-level').textContent = '1:500';
    showNotification('View reset to default', 'info');
    simulateMapUpdate();
}

function captureMap() {
    if (!isDroneConnected()) {
        showNotification('Connect drone first', 'warning');
        return;
    }
    
    // Create a simulated map capture
    showNotification('📸 Map screenshot saved to gallery', 'success');
    
    // Simulate file download
    setTimeout(() => {
        console.log('Map capture saved');
    }, 500);
}

// Data Simulation
function startDataSimulation() {
    console.log('Starting data simulation...');
    
    // Simulate signal strength updates
    window.signalInterval = setInterval(() => {
        if (isDroneConnected()) {
            const signal = Math.floor(Math.random() * 30) + 70; // 70-100%
            updateValue('signal-value', signal + '%');
            updateProgressBar('signal-bar', signal);
            
            // Update signal status
            if (signal > 85) {
                updateStatus('signal-status', 'Excellent');
            } else if (signal > 70) {
                updateStatus('signal-status', 'Good');
            } else {
                updateStatus('signal-status', 'Moderate');
            }
            
            // Update sidebar displays
            updateStatusDisplays();
        }
    }, 3000);
    
    // Simulate battery drain
    window.batteryInterval = setInterval(() => {
        if (isDroneConnected()) {
            const currentBattery = parseInt(document.getElementById('battery-value').textContent) || 85;
            const newBattery = Math.max(15, currentBattery - 0.3);
            updateValue('battery-value', Math.round(newBattery) + '%');
            updateProgressBar('battery-bar', newBattery);
            
            // Update battery status
            if (newBattery > 60) {
                updateStatus('battery-status', 'Good');
            } else if (newBattery > 30) {
                updateStatus('battery-status', 'Moderate');
            } else {
                updateStatus('battery-status', 'Low');
            }
            
            // Update sidebar displays
            updateStatusDisplays();
        }
    }, 5000);
    
    // Simulate other data updates
    window.dataInterval = setInterval(() => {
        if (isDroneConnected()) {
            simulateDataUpdate();
            // Update sidebar displays
            updateStatusDisplays();
        }
    }, 2000);
    
    // Simulate altitude changes
    window.altitudeInterval = setInterval(() => {
        if (isDroneConnected()) {
            const currentAlt = parseInt(document.getElementById('drone-altitude').textContent) || 120;
            const newAlt = Math.max(50, Math.min(200, currentAlt + (Math.random() - 0.5) * 10));
            updateValue('drone-altitude', Math.round(newAlt) + 'm');
        }
    }, 3000);
}

function simulateDataUpdate(missionProgress = 0) {
    if (!isDroneConnected()) return;
    
    // Update flight time
    const flightTimeElement = document.getElementById('flight-time');
    const timeMatch = flightTimeElement.textContent.match(/(\d+):(\d+)/);
    if (timeMatch) {
        let minutes = parseInt(timeMatch[1]);
        let seconds = parseInt(timeMatch[2]);
        
        seconds += 1;
        if (seconds >= 60) {
            seconds = 0;
            minutes += 1;
        }
        
        const newTime = minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
        updateValue('flight-time', newTime);
        updateProgressBar('flight-bar', (minutes * 60 + seconds) / 3600 * 100);
    }
    
    // Update area covered (only if mission is active)
    if (missionProgress > 0) {
        const areaElement = document.getElementById('area-covered');
        const areaMatch = areaElement.textContent.match(/(\d+\.?\d*)/);
        if (areaMatch) {
            const currentArea = parseFloat(areaMatch[1]);
            const newArea = Math.min(25.3, currentArea + (missionProgress / 1000));
            updateValue('area-covered', newArea.toFixed(1) + ' ha');
            updateProgressBar('area-bar', (newArea / 25.3) * 100);
        }
    }
    
    // Update NDVI value (simulate variations)
    const baseNDVI = 0.65 + (Math.sin(Date.now() / 10000) * 0.15);
    const ndvi = Math.max(0, Math.min(1, baseNDVI + (Math.random() - 0.5) * 0.1));
    updateValue('avg-ndvi', ndvi.toFixed(2));
    updateProgressBar('ndvi-bar', ndvi * 100);
    
    // Update health score based on NDVI
    const health = (ndvi * 100) - 20 + (Math.random() * 20);
    const healthPercent = Math.max(0, Math.min(100, Math.round(health)));
    updateValue('health-score', healthPercent + '%');
    updateProgressBar('health-bar', healthPercent);
    
    // Update map coordinates (simulate drone movement)
    const lat = 14.599512 + (Math.random() - 0.5) * 0.0005;
    const lng = 120.984222 + (Math.random() - 0.5) * 0.0005;
    updateMapCoordinates(lat, lng);
    
    // Update last update time
    updateLastUpdateTime();
}

// Map Display Functions
function showNDVIMap() {
    console.log('Showing NDVI map');
    
    const mapCanvas = document.getElementById('ndvi-map-canvas');
    if (!mapCanvas) return;
    
    mapCanvas.style.display = 'block';
    mapCanvas.innerHTML = '';
    
    // Create simulated NDVI map
    createSimulatedNDVIMap();
}

function createSimulatedNDVIMap() {
    const mapCanvas = document.getElementById('ndvi-map-canvas');
    if (!mapCanvas) return;
    
    // Set dimensions
    mapCanvas.style.width = '100%';
    mapCanvas.style.height = '100%';
    mapCanvas.style.position = 'relative';
    mapCanvas.style.background = 'linear-gradient(135deg, #1a9641 0%, #d7191c 100%)';
    mapCanvas.style.borderRadius = '8px';
    
    // Create grid pattern
    const gridSize = 40;
    const width = mapCanvas.offsetWidth;
    const height = mapCanvas.offsetHeight;
    const cols = Math.ceil(width / gridSize);
    const rows = Math.ceil(height / gridSize);
    
    // Create grid cells
    for (let i = 0; i < cols * rows; i++) {
        const cell = document.createElement('div');
        cell.style.position = 'absolute';
        cell.style.width = gridSize + 'px';
        cell.style.height = gridSize + 'px';
        cell.style.left = (i % cols) * gridSize + 'px';
        cell.style.top = Math.floor(i / cols) * gridSize + 'px';
        cell.style.backgroundColor = getNDVIColor(Math.random());
        cell.style.opacity = '0.8';
        cell.style.border = '1px solid rgba(255,255,255,0.1)';
        mapCanvas.appendChild(cell);
    }
    
    // Add drone position indicator
    const droneIndicator = document.createElement('div');
    droneIndicator.id = 'drone-indicator';
    droneIndicator.style.position = 'absolute';
    droneIndicator.style.left = '50%';
    droneIndicator.style.top = '50%';
    droneIndicator.style.width = '20px';
    droneIndicator.style.height = '20px';
    droneIndicator.style.backgroundColor = '#2d3748';
    droneIndicator.style.borderRadius = '50%';
    droneIndicator.style.border = '3px solid #ffffff';
    droneIndicator.style.boxShadow = '0 0 10px rgba(0,0,0,0.5)';
    droneIndicator.style.transform = 'translate(-50%, -50%)';
    droneIndicator.style.zIndex = '10';
    droneIndicator.innerHTML = '<i class="fas fa-drone" style="color: white; font-size: 10px; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);"></i>';
    mapCanvas.appendChild(droneIndicator);
    
    // Animate drone movement
    animateDrone();
}

function animateDrone() {
    const drone = document.getElementById('drone-indicator');
    if (!drone) return;
    
    let x = 50;
    let y = 50;
    let dx = 0.5;
    let dy = 0.3;
    
    function moveDrone() {
        if (!drone || !isDroneConnected()) return;
        
        x += dx;
        y += dy;
        
        // Bounce off edges
        if (x <= 5 || x >= 95) dx = -dx;
        if (y <= 5 || y >= 95) dy = -dy;
        
        drone.style.left = x + '%';
        drone.style.top = y + '%';
        
        // Update coordinates
        const lat = 14.599512 + (x - 50) * 0.0001;
        const lng = 120.984222 + (y - 50) * 0.0001;
        updateMapCoordinates(lat, lng);
        
        requestAnimationFrame(moveDrone);
    }
    
    moveDrone();
}

function getNDVIColor(value) {
    if (value < 0.2) return '#d7191c'; // Stress / Very Poor
    if (value < 0.4) return '#fdae61'; // Poor Vegetation
    if (value < 0.6) return '#ffffbf'; // Moderate Health
    if (value < 0.8) return '#a6d96a'; // Good Health
    return '#1a9641'; // Excellent Health
}

function simulateMapUpdate() {
    const mapCanvas = document.getElementById('ndvi-map-canvas');
    if (mapCanvas && mapCanvas.style.display !== 'none') {
        // Simulate map refresh
        mapCanvas.style.opacity = '0.8';
        setTimeout(() => {
            mapCanvas.style.opacity = '1';
        }, 200);
    }
}

function updateMapCoordinates(lat, lng) {
    document.getElementById('map-coordinates').textContent = 
        `Lat: ${lat.toFixed(6)}°, Lng: ${lng.toFixed(6)}°`;
}

// Utility Functions
function isDroneConnected() {
    return document.getElementById('connection-status-value').textContent === 'Connected';
}

function updateValue(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    }
}

function updateStatus(elementId, status) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = status;
        element.className = 'param-status';
        
        switch(status.toLowerCase()) {
            case 'connected':
            case 'excellent':
            case 'good':
            case 'complete':
            case 'ready':
                element.classList.add('good');
                break;
            case 'connecting':
            case 'moderate':
            case 'active':
            case 'fair':
                element.classList.add('moderate');
                break;
            case 'offline':
            case 'poor':
            case 'critical':
            case 'stopped':
            case 'low':
                element.classList.add('poor');
                break;
        }
    }
}

function updateProgressBar(barId, percentage) {
    const bar = document.getElementById(barId);
    if (bar) {
        const percent = Math.min(100, Math.max(0, percentage));
        bar.style.width = percent + '%';
        
        // Update color based on percentage
        if (percent > 70) {
            bar.style.backgroundColor = '#10b981';
        } else if (percent > 40) {
            bar.style.backgroundColor = '#f59e0b';
        } else {
            bar.style.backgroundColor = '#ef4444';
        }
    }
}

function updateSystemStatus(status) {
    const dot = document.getElementById('system-status-dot');
    const text = document.getElementById('system-status-text');
    
    if (dot && text) {
        switch(status) {
            case 'ready':
                dot.className = 'status-dot';
                text.textContent = 'System Ready';
                break;
            case 'connected':
                dot.className = 'status-dot active';
                text.textContent = 'Drone Connected';
                break;
            case 'mission':
                dot.className = 'status-dot active';
                text.textContent = 'Mission Active';
                break;
            case 'error':
                dot.className = 'status-dot';
                dot.style.backgroundColor = '#ef4444';
                text.textContent = 'System Error';
                break;
        }
    }
}

// REMOVED: selectNode function

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        animation: slideIn 0.3s ease;
    `;
    
    // Set background color based on type
    switch(type) {
        case 'success':
            notification.style.backgroundColor = '#10b981';
            break;
        case 'error':
            notification.style.backgroundColor = '#ef4444';
            break;
        case 'warning':
            notification.style.backgroundColor = '#f59e0b';
            break;
        case 'info':
            notification.style.backgroundColor = '#0f766e';
            break;
    }
    
    notification.textContent = message;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }
    }, 3000);
}

// REMOVED: refreshData function (since refresh button is removed)

function changeField(field) {
    const fieldNames = {
        'north': 'North Field',
        'south': 'South Field', 
        'east': 'East Field',
        'west': 'West Field'
    };
    showNotification(`Switched to ${fieldNames[field] || field}`, 'info');
    
    // Reset area covered when changing fields
    updateValue('area-covered', '0.0 ha');
    updateProgressBar('area-bar', 0);
}

function changeFlightMode(mode) {
    const modeNames = {
        'manual': 'Manual Control',
        'auto': 'Auto Mission',
        'grid': 'Grid Scan Pattern',
        'follow': 'Follow Path'
    };
    showNotification(`Flight mode changed to ${modeNames[mode] || mode}`, 'info');
}

function handleResize() {
    // Handle window resize for responsive design
    console.log('Window resized to:', window.innerWidth, 'x', window.innerHeight);
    
    // Recreate map if needed
    if (isDroneConnected()) {
        simulateMapUpdate();
    }
}

// Clean up intervals when page is unloaded
window.addEventListener('beforeunload', function() {
    if (window.signalInterval) clearInterval(window.signalInterval);
    if (window.batteryInterval) clearInterval(window.batteryInterval);
    if (window.dataInterval) clearInterval(window.dataInterval);
    if (window.altitudeInterval) clearInterval(window.altitudeInterval);
    if (window.missionTimer) clearInterval(window.missionTimer);
});

document.getElementById("disconnect-drone-btn").addEventListener("click", () => {
    document.getElementById("drone-connection-status").textContent = "Disconnected";
    document.getElementById("drone-connection-dot").classList.remove("active");

    document.getElementById("connection-status-value").textContent = "Offline";
    document.getElementById("connection-status").textContent = "Offline";
    document.getElementById("connection-desc").textContent = "Drone disconnected";

    alert("Drone disconnected successfully.");
});

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        animation: slideIn 0.3s ease;
    }
`;
document.head.appendChild(style);

console.log('NDVI Dashboard JavaScript loaded successfully');