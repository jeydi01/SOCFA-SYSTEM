let currentNode = 1;

document.addEventListener('DOMContentLoaded', () => {
    updateTime(); // Update clock
    setInterval(updateTime, 1000);

    updateLastUpdateTime(); // Show last update time
    initEventListeners(); // Attach buttons and dropdowns
    startLiveUpdates(); // Start auto-refresh

    // Initial data fetch
    fetchSensorStatus(); // Fetch sensor node statuses
    const initialRange = document.getElementById('time-range')?.value || 'realtime';
    updateParametersForNode(currentNode, mapRangeToBackend(initialRange));
    
    // Set up periodic sensor status updates
    setInterval(fetchSensorStatus, 5000);
});

function updateTime() {
    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const date = now.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
    document.getElementById('current-time').textContent = `${time} | ${date}`;
}

function updateLastUpdateTime() {
    const now = new Date();
    document.getElementById('last-update-time').textContent =
        now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
}

function initEventListeners() {
    const timeRange = document.getElementById('time-range');
    if (timeRange) timeRange.addEventListener('change', handleTimeRangeChange);

    document.querySelectorAll('.node-item').forEach((item, index) => {
        item.addEventListener('click', () => selectNode(index));
    });

    document.querySelectorAll('.close-modal').forEach(btn =>
        btn.addEventListener('click', closeModal)
    );
}

// Fetch sensor node statuses
async function fetchSensorStatus() {
    try {
        const response = await fetch('http://localhost:3000/soil-data');
        const data = await response.json();
        
        const nodes = [
            { id: 1, indicatorId: 'sensor-1-indicator', statusId: 'sensor-1-status' },
            { id: 2, indicatorId: 'sensor-2-indicator', statusId: 'sensor-2-status' },
            { id: 3, indicatorId: 'sensor-3-indicator', statusId: 'sensor-3-status' }
        ];

        const now = new Date();
        let latestTimestamp = null;

        nodes.forEach(node => {
            const nodeData = data
                .filter(d => Number(d.node_id) === node.id)
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0];

            const indicator = document.getElementById(node.indicatorId);
            const statusText = document.getElementById(node.statusId);

            if (indicator && statusText && nodeData) {
                const lastTime = new Date(nodeData.timestamp);
                const diffSeconds = (now - lastTime) / 1000;
                
                if (!latestTimestamp || lastTime > latestTimestamp) {
                    latestTimestamp = lastTime;
                }

                if (diffSeconds < 60) { // Online if less than 5 minutes old
                    indicator.style.backgroundColor = '#10b981';
                    indicator.style.boxShadow = '0 0 8px rgba(16, 185, 129, 0.5)';
                    statusText.textContent = 'Online';
                    statusText.style.color = '#10b981';
                } else {
                    indicator.style.backgroundColor = '#ef4444';
                    indicator.style.boxShadow = 'none';
                    statusText.textContent = 'Offline';
                    statusText.style.color = '#ef4444';
                }
            } else if (indicator && statusText) {
                indicator.style.backgroundColor = '#ef4444';
                indicator.style.boxShadow = 'none';
                statusText.textContent = 'Offline';
                statusText.style.color = '#ef4444';
            }
        });

        // Update last reading time
        if (latestTimestamp) {
            const diffSeconds = Math.floor((now - latestTimestamp) / 1000);
            let timeText = "Just now";
            if (diffSeconds > 60) {
                const mins = Math.floor(diffSeconds / 60);
                timeText = mins + " minute(s) ago";
            }
            document.getElementById('last-sensor-reading').textContent = timeText;
        } else {
            document.getElementById('last-sensor-reading').textContent = 'No data';
        }

    } catch (error) {
        console.error("Error fetching sensor status:", error);
        ['sensor-1', 'sensor-2', 'sensor-3'].forEach(id => {
            const indicator = document.getElementById(`${id}-indicator`);
            const statusText = document.getElementById(`${id}-status`);
            if (indicator) {
                indicator.style.backgroundColor = '#ef4444';
                indicator.style.boxShadow = 'none';
            }
            if (statusText) {
                statusText.textContent = 'Offline';
                statusText.style.color = '#ef4444';
            }
        });
        document.getElementById('last-sensor-reading').textContent = 'Server error';
    }
}

function selectNode(index) {
    document.querySelectorAll('.node-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.node-status').forEach(s => s.classList.remove('active'));

    const node = document.querySelectorAll('.node-item')[index];
    node.classList.add('active');
    node.querySelector('.node-status').classList.add('active');

    currentNode = index + 1;
    updateParametersForNode(currentNode, mapRangeToBackend(document.getElementById('time-range').value));

    showNotification(`Viewing data from Node ${currentNode}`);
}

function mapRangeToBackend(range) {
    if (range === 'day') return 'day';
    if (range === 'week') return 'lastWeek';
    if (range === 'month') return 'lastMonth';
    return 'realtime';
}

// Update parameters for a node with optional range
function updateParametersForNode(node, range = 'realtime') {
    fetch(`http://localhost:3000/soil-data/${node}?range=${range}`)
        .then(res => res.json())
        .then(dataArray => {
            if (!dataArray || dataArray.length === 0) {
                clearParameterCards();
                showNotification('No data available for this range', 'info');
                return;
            }

            // Use latest for real-time/day, average for week/month
            let data;

            if (range === 'realtime' || range === 'day') {
                // latest value only
                data = {
                    ph: Number(dataArray[0].ph),
                    temperature: Number(dataArray[0].temperature),
                    ec: Number(dataArray[0].ec),
                    humidity: Number(dataArray[0].humidity)
                };
            } else {
                // average values
                data = {
                    ph: Number(
                        dataArray.reduce((sum, d) => sum + Number(d.ph), 0) / dataArray.length
                    ).toFixed(2),
                    temperature: Number(
                        dataArray.reduce((sum, d) => sum + Number(d.temperature), 0) / dataArray.length
                    ).toFixed(1),
                    ec: Number(
                        dataArray.reduce((sum, d) => sum + Number(d.ec), 0) / dataArray.length
                    ).toFixed(2),
                    humidity: Number(
                        dataArray.reduce((sum, d) => sum + Number(d.humidity), 0) / dataArray.length
                    ).toFixed(1),
                };
            }
            
            // Update values
            animateValueUpdate('.param-value', {
                'pH Level': data.ph,
                'Temperature': `${data.temperature}°C`,
                'Electrical Conductivity': `${data.ec} dS/m`,
                'Humidity': `${data.humidity}%`
            });

            updateProgressBars(data);
            updateStatuses(data);
            updateRecommendation(data);
        })
        .catch(err => console.error('Error fetching soil data:', err));
}

// Clear cards when no data
function clearParameterCards() {
    document.querySelectorAll('.parameter-card').forEach(card => {
        const valueEl = card.querySelector('.param-value');
        if (valueEl) valueEl.textContent = '--';

        const statusEl = card.querySelector('.param-status');
        if (statusEl) {
            statusEl.textContent = '--';
            statusEl.classList.remove('good', 'moderate', 'bad');
        }

        const fill = card.querySelector('.range-fill');
        if (fill) fill.style.width = '0%';
    });

    // Clear recommendations
    const recSection = document.getElementById('recommendation-section');
    if (recSection) {
        recSection.innerHTML = ''; // Clear content but keep the section
    }
}

// Handle dropdown range change
function handleTimeRangeChange() {
    const range = mapRangeToBackend(document.getElementById('time-range').value);
    updateParametersForNode(currentNode, range);
}

// Animate value changes
function animateValueUpdate(selector, values) {
    document.querySelectorAll(selector).forEach(el => {
        const title = el.closest('.parameter-card').querySelector('h3').textContent;
        if (values[title]) {
            el.classList.add('updating');
            setTimeout(() => {
                el.textContent = values[title];
                el.classList.remove('updating');
            }, 300);
        }
    });
}

// Update progress bars
function updateProgressBars(data) {
    document.querySelectorAll('.range-fill').forEach(fill => {
        const title = fill.closest('.parameter-card').querySelector('h3').textContent;
        if (title === 'pH Level') fill.style.width = `${data.ph * 10}%`;
        if (title === 'Temperature') fill.style.width = `${(data.temperature / 40) * 100}%`;
        if (title === 'Electrical Conductivity') fill.style.width = `${data.ec * 20}%`;
        if (title === 'Humidity') fill.style.width = `${data.humidity}%`;
    });
}

// Update parameter statuses
function updateStatuses(data) {
    document.querySelectorAll('.parameter-card').forEach(card => {
        const title = card.querySelector('h3').textContent;
        const statusEl = card.querySelector('.param-status');
        if (!statusEl) return;

        statusEl.classList.remove('good', 'moderate', 'bad');
        let statusText = '--';

        if (title === 'pH Level') {
            if (data.ph >= 6 && data.ph <= 7) { statusText = 'Good'; statusEl.classList.add('good'); }
            else if (data.ph >= 5 && data.ph < 6 || data.ph > 7 && data.ph <= 8) { statusText = 'Moderate'; statusEl.classList.add('moderate'); }
            else { statusText = 'Bad'; statusEl.classList.add('bad'); }
        }

        if (title === 'Temperature') {
            if (data.temperature >= 25 && data.temperature <= 35) { statusText = 'Good'; statusEl.classList.add('good'); }
            else if (data.temperature >= 20 && data.temperature < 25 || data.temperature > 35 && data.temperature <= 40) { statusText = 'Moderate'; statusEl.classList.add('moderate'); }
            else { statusText = 'Bad'; statusEl.classList.add('bad'); }
        }

        if (title === 'Electrical Conductivity') {
            if (data.ec <= 2) { statusText = 'Good'; statusEl.classList.add('good'); }
            else if (data.ec <= 3) { statusText = 'Moderate'; statusEl.classList.add('moderate'); }
            else { statusText = 'Bad'; statusEl.classList.add('bad'); }
        }

        if (title === 'Humidity') {
            if (data.humidity >= 40 && data.humidity <= 70) { statusText = 'Good'; statusEl.classList.add('good'); }
            else if (data.humidity >= 30 && data.humidity < 40 || data.humidity > 70 && data.humidity <= 80) { statusText = 'Moderate'; statusEl.classList.add('moderate'); }
            else { statusText = 'Bad'; statusEl.classList.add('bad'); }
        }

        statusEl.textContent = statusText;
    });
}

// Update recommendations - Now populates the grid below parameters
function updateRecommendation(data) {
    let overall = "Soil conditions are optimal.";
    let phRec = "pH level is within ideal range.";
    let tempRec = "Temperature is suitable.";
    let humRec = "Humidity level is acceptable.";
    let ecRec = "Salinity level is safe.";

    if (data.ph < 6) { phRec = "Soil is acidic. Apply lime."; overall = "Soil needs attention."; }
    else if (data.ph > 7) { phRec = "Soil is alkaline. Reduce pH."; overall = "Soil needs attention."; }

    if (data.temperature < 20) { tempRec = "Temperature is low."; overall = "Soil needs monitoring."; }
    else if (data.temperature > 35) { tempRec = "Temperature is high."; overall = "Soil needs monitoring."; }

    if (data.humidity < 40) { humRec = "Soil is dry. Irrigation recommended."; overall = "Soil needs attention."; }
    else if (data.humidity > 70) { humRec = "Soil too wet. Improve drainage."; overall = "Soil needs attention."; }

    if (data.ec > 2) { ecRec = "High salinity detected."; overall = "Soil needs attention."; }

    // Update the recommendation grid below parameters
    const recGrid = document.getElementById('recommendation-section');
    if (recGrid) {
        recGrid.innerHTML = `
            <div class="rec-card" style="background: #f0fdf4; border-left: 4px solid #0f766e;">
                <h3 style="color: #065f46;">Overall</h3>
                <p style="color: #166534;">${overall}</p>
            </div>
            <div class="rec-card" style="background: #f8fafc;">
                <h3 style="color: #475569;">pH Level</h3>
                <p style="color: #334155;">${phRec}</p>
            </div>
            <div class="rec-card" style="background: #f8fafc;">
                <h3 style="color: #475569;">Temperature</h3>
                <p style="color: #334155;">${tempRec}</p>
            </div>
            <div class="rec-card" style="background: #f8fafc;">
                <h3 style="color: #475569;">Humidity</h3>
                <p style="color: #334155;">${humRec}</p>
            </div>
            <div class="rec-card" style="background: #f8fafc;">
                <h3 style="color: #475569;">EC</h3>
                <p style="color: #334155;">${ecRec}</p>
            </div>
        `;
    }
}

// Live updates every 5s for real-time/day only
function startLiveUpdates() {
    setInterval(() => {
        const range = document.getElementById('time-range').value;
        if (range === 'realtime' || range === 'day') {
            updateParametersForNode(currentNode, range);
        }
    }, 5000);
}

// Notification popup
function showNotification(message, type = 'info') {
    const old = document.querySelector('.notification');
    if (old) old.remove();

    const note = document.createElement('div');
    note.className = 'notification';
    
    note.style.cssText = `
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
    
    switch(type) {
        case 'success': note.style.backgroundColor = '#10b981'; break;
        case 'error': note.style.backgroundColor = '#ef4444'; break;
        case 'warning': note.style.backgroundColor = '#f59e0b'; break;
        case 'info': note.style.backgroundColor = '#0f766e'; break;
    }
    
    note.textContent = message;
    document.body.appendChild(note);
    
    setTimeout(() => {
        if (note.parentNode) {
            note.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => note.remove(), 300);
        }
    }, 3000);
}

// Close modal
function closeModal() {
    document.getElementById('node-modal').style.display = 'none';
}

// CSS for notifications and recommendations
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
    
    /* Recommendation Grid Styling */
    .recommendation-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 16px;
        margin-top: 24px;
        margin-bottom: 16px;
    }
    
    .rec-card {
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease;
    }
    
    .rec-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
    }
    
    .rec-card h3 {
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    
    .rec-card p {
        font-size: 0.85rem;
        line-height: 1.4;
        margin: 0;
    }
    
    /* Responsive design */
    @media (max-width: 1200px) {
        .recommendation-grid {
            grid-template-columns: repeat(3, 1fr);
        }
    }
    
    @media (max-width: 768px) {
        .recommendation-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    
    @media (max-width: 480px) {
        .recommendation-grid {
            grid-template-columns: 1fr;
        }
    }
`;
document.head.appendChild(style);