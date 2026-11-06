// ─── State ───────────────────────────────────────────────────────────────────
let currentNode = 1;
let nodeList = [
    { id: 1, name: 'Node 1' },
    { id: 2, name: 'Node 2' },
    { id: 3, name: 'Node 3' },
];

// ─── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    updateTime();
    setInterval(updateTime, 1000);
    updateLastUpdateTime();
    initTheme();

    // Always render default nodes first so sidebar is never empty
    renderAllNodes();

    // Attach all event listeners (safe, no async)
    initEventListeners();

    // Then try to sync from DB in background
    loadNodesFromDB();

    startLiveUpdates();
    fetchSensorStatus();
    setInterval(fetchSensorStatus, 5000);

    const initialRange = document.getElementById('time-range')?.value || 'realtime';
    updateParametersForNode(currentNode, mapRangeToBackend(initialRange));
});

// ─── Render nodes from nodeList into sidebar + status bar ────────────────────
function renderAllNodes() {
    const nodesList = document.getElementById('nodes-list');
    const statusBar = document.getElementById('sensor-nodes-horizontal');
    if (!nodesList || !statusBar) return;

    nodesList.innerHTML = '';
    statusBar.innerHTML = '';

    nodeList.forEach((node, index) => {
        // Sidebar item
        const nodeItem = document.createElement('div');
        nodeItem.className = 'node-item' + (index === 0 ? ' active' : '');
        nodeItem.setAttribute('data-node-index', index);
        nodeItem.innerHTML = `
            <div class="node-info">
                <span class="node-status${index === 0 ? ' active' : ''}"></span>
                <span class="node-name">${escapeHtml(node.name)}</span>
            </div>
            <button class="delete-node-btn" title="Delete ${escapeHtml(node.name)}">
                <i class="fas fa-trash-alt"></i>
            </button>
        `;
        nodeItem.querySelector('.delete-node-btn').addEventListener('click', e => {
            e.stopPropagation();
            openDeleteConfirm(node.id, node.name);
        });
        nodesList.appendChild(nodeItem);

        // Status bar pill
        const pill = document.createElement('div');
        pill.className = 'horizontal-node-item';
        pill.innerHTML = `
            <div class="node-indicator" id="sensor-${node.id}-indicator"></div>
            <span class="node-label">${escapeHtml(node.name)}</span>
            <span class="node-status-text" id="sensor-${node.id}-status" style="color:#ef4444;">Offline</span>
        `;
        statusBar.appendChild(pill);
    });
}

// ─── Load Nodes from Backend (background sync) ────────────────────────────────
async function loadNodesFromDB() {
    try {
        const res = await fetch('http://localhost:3000/nodes');
        if (!res.ok) throw new Error('Server error');
        const nodes = await res.json();
        if (!Array.isArray(nodes) || nodes.length === 0) return;

        // Convert DB nodes to the expected format
        const dbNodes = nodes.map(n => ({ id: Number(n.node_id), name: n.name }));

        // Merge with default nodes, ensuring defaults are always present
        const defaultNodes = [
            { id: 1, name: 'Node 1' },
            { id: 2, name: 'Node 2' },
            { id: 3, name: 'Node 3' },
        ];

        // Combine defaults with DB nodes, removing duplicates by ID
        const allNodes = [...defaultNodes];
        dbNodes.forEach(dbNode => {
            if (!allNodes.some(n => n.id === dbNode.id)) {
                allNodes.push(dbNode);
            }
        });

        // Update nodeList and sort by ID
        nodeList = allNodes.sort((a, b) => a.id - b.id);
        currentNode = nodeList[0].id;

        // Re-render with merged data
        renderAllNodes();

        // Fetch status for newly rendered nodes
        fetchSensorStatus();
        const range = mapRangeToBackend(document.getElementById('time-range')?.value || 'realtime');
        updateParametersForNode(currentNode, range);

    } catch (err) {
        console.warn('Could not load nodes from DB, using defaults:', err.message);
        // Silently keep the default hardcoded nodes — no error notification
    }
}

// ─── Clock ───────────────────────────────────────────────────────────────────
function updateTime() {
    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const date = now.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
    const el = document.getElementById('current-time');
    if (el) el.textContent = `${time} | ${date}`;
}

function updateLastUpdateTime() {
    const now = new Date();
    const el = document.getElementById('last-update-time');
    if (el) el.textContent = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
}

// ─── Theme ───────────────────────────────────────────────────────────────────
function initTheme() {
    applyTheme(localStorage.getItem('socfa-theme') || 'light');
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('theme-icon');
    if (icon) icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    localStorage.setItem('socfa-theme', theme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    applyTheme(current === 'dark' ? 'light' : 'dark');
}

// ─── Event Listeners ─────────────────────────────────────────────────────────
function initEventListeners() {
    // Time range
    const timeRange = document.getElementById('time-range');
    if (timeRange) timeRange.addEventListener('change', handleTimeRangeChange);

    // Theme toggle
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

    // Node selection (delegated)
    const nodesList = document.getElementById('nodes-list');
    if (nodesList) {
        nodesList.addEventListener('click', e => {
            const item = e.target.closest('.node-item');
            if (item) selectNode(parseInt(item.getAttribute('data-node-index')));
        });
    }

    // Add Node button → open modal
    const addBtn = document.getElementById('add-node-btn');
    if (addBtn) addBtn.addEventListener('click', openAddNodeModal);

    // Add Node modal — close buttons
    const closeAddBtn = document.getElementById('close-add-node-modal');
    if (closeAddBtn) closeAddBtn.addEventListener('click', closeAddNodeModal);

    const cancelBtn = document.getElementById('cancel-add-node');
    if (cancelBtn) cancelBtn.addEventListener('click', closeAddNodeModal);

    // Delete Node modal
    const closeDeleteBtn = document.getElementById('close-delete-node-modal');
    if (closeDeleteBtn) closeDeleteBtn.addEventListener('click', closeDeleteConfirm);
    const cancelDeleteBtn = document.getElementById('cancel-delete-node');
    if (cancelDeleteBtn) cancelDeleteBtn.addEventListener('click', closeDeleteConfirm);
    const confirmDeleteBtn = document.getElementById('confirm-delete-node');
    if (confirmDeleteBtn) confirmDeleteBtn.addEventListener('click', confirmDeleteNode);
    const deleteModal = document.getElementById('delete-node-modal');
    if (deleteModal) {
        deleteModal.addEventListener('click', e => {
            if (e.target === deleteModal) closeDeleteConfirm();
        });
    }

    const confirmBtn = document.getElementById('confirm-add-node');
    if (confirmBtn) confirmBtn.addEventListener('click', confirmAddNode);

    // Click backdrop to close
    const addModal = document.getElementById('add-node-modal');
    if (addModal) {
        addModal.addEventListener('click', e => {
            if (e.target === addModal) closeAddNodeModal();
        });
    }

    // Keyboard shortcuts inside modal
    document.addEventListener('keydown', e => {
        const modal = document.getElementById('add-node-modal');
        if (!modal || modal.style.display !== 'flex') return;
        if (e.key === 'Enter') confirmAddNode();
        if (e.key === 'Escape') closeAddNodeModal();
    });

    // Node detail modal close
    const nodeModalClose = document.querySelector('#node-modal .close-modal');
    if (nodeModalClose) nodeModalClose.addEventListener('click', closeModal);

    const nodeModal = document.getElementById('node-modal');
    if (nodeModal) {
        nodeModal.addEventListener('click', e => {
            if (e.target === nodeModal) closeModal();
        });
    }
}

// ─── Sensor Status ────────────────────────────────────────────────────────────
async function fetchSensorStatus() {
    try {
        const response = await fetch('http://localhost:3000/soil-data');
        const data = await response.json();
        const now = new Date();
        let latestTimestamp = null;

        nodeList.forEach(node => {
            const nodeData = data
                .filter(d => Number(d.node_id) === node.id)
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0];

            const indicator = document.getElementById(`sensor-${node.id}-indicator`);
            const statusText = document.getElementById(`sensor-${node.id}-status`);

            if (indicator && statusText && nodeData) {
                const lastTime = new Date(nodeData.timestamp);
                const diffSeconds = (now - lastTime) / 1000;
                if (!latestTimestamp || lastTime > latestTimestamp) latestTimestamp = lastTime;

                if (diffSeconds < 60) {
                    indicator.style.backgroundColor = '#10b981';
                    indicator.style.boxShadow = '0 0 8px rgba(16,185,129,0.5)';
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

        const lastReadingEl = document.getElementById('last-sensor-reading');
        if (lastReadingEl) {
            if (latestTimestamp) {
                const diffSeconds = Math.floor((now - latestTimestamp) / 1000);
                lastReadingEl.textContent = diffSeconds > 60 ? Math.floor(diffSeconds / 60) + ' minute(s) ago' : 'Just now';
            } else {
                lastReadingEl.textContent = 'No data';
            }
        }

    } catch (error) {
        console.error('Error fetching sensor status:', error);
        nodeList.forEach(node => {
            const indicator = document.getElementById(`sensor-${node.id}-indicator`);
            const statusText = document.getElementById(`sensor-${node.id}-status`);
            if (indicator) { indicator.style.backgroundColor = '#ef4444'; indicator.style.boxShadow = 'none'; }
            if (statusText) { statusText.textContent = 'Offline'; statusText.style.color = '#ef4444'; }
        });
        const el = document.getElementById('last-sensor-reading');
        if (el) el.textContent = 'Server error';
    }
}

// ─── Node Selection ───────────────────────────────────────────────────────────
function selectNode(index) {
    document.querySelectorAll('.node-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.node-item .node-status').forEach(s => s.classList.remove('active'));

    const nodeItems = document.querySelectorAll('.node-item');
    if (nodeItems[index]) {
        nodeItems[index].classList.add('active');
        const dot = nodeItems[index].querySelector('.node-status');
        if (dot) dot.classList.add('active');
    }

    if (!nodeList[index]) return;
    currentNode = nodeList[index].id;
    updateParametersForNode(currentNode, mapRangeToBackend(document.getElementById('time-range').value));
    showNotification(`Viewing data from ${nodeList[index].name}`);
}

// ─── Add Node Modal ───────────────────────────────────────────────────────────
// ─── Delete Node ─────────────────────────────────────────────────────────────
let nodeToDeleteId = null;

function openDeleteConfirm(nodeId, nodeName) {
    nodeToDeleteId = nodeId;
    const label = document.getElementById('delete-node-name-label');
    if (label) label.textContent = nodeName;
    const modal = document.getElementById('delete-node-modal');
    if (modal) modal.style.display = 'flex';
}

function closeDeleteConfirm() {
    nodeToDeleteId = null;
    const modal = document.getElementById('delete-node-modal');
    if (modal) modal.style.display = 'none';
}

async function confirmDeleteNode() {
    if (!nodeToDeleteId) return;

    const btn = document.getElementById('confirm-delete-node');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deleting...'; }

    try {
        const res = await fetch(`http://localhost:3000/nodes/${nodeToDeleteId}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || 'Server error');
        }

        const deletedName = nodeList.find(n => n.id === nodeToDeleteId)?.name || 'Node';

        // Remove from local state
        nodeList = nodeList.filter(n => n.id !== nodeToDeleteId);

        // If deleted node was selected, switch to first remaining
        if (currentNode === nodeToDeleteId && nodeList.length > 0) {
            currentNode = nodeList[0].id;
        }

        renderAllNodes();
        closeDeleteConfirm();
        showNotification(`${deletedName} deleted successfully`, 'success');

        if (nodeList.length > 0) {
            const range = mapRangeToBackend(document.getElementById('time-range')?.value || 'realtime');
            updateParametersForNode(currentNode, range);
            fetchSensorStatus();
        } else {
            clearParameterCards();
        }

    } catch (err) {
        console.error('Failed to delete node:', err);
        showNotification(`Failed to delete: ${err.message}`, 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-trash-alt"></i> Delete'; }
    }
}

function openAddNodeModal() {
    const nextId = nodeList.length > 0 ? Math.max(...nodeList.map(n => n.id)) + 1 : 1;
    const nameInput = document.getElementById('new-node-name');
    const idInput   = document.getElementById('new-node-id');
    if (nameInput) nameInput.value = `Node ${nextId}`;
    if (idInput)   idInput.value   = nextId;

    const modal = document.getElementById('add-node-modal');
    if (modal) modal.style.display = 'flex';
    setTimeout(() => { if (nameInput) nameInput.focus(); }, 100);
}

function closeAddNodeModal() {
    const modal = document.getElementById('add-node-modal');
    if (modal) modal.style.display = 'none';
    const nameInput = document.getElementById('new-node-name');
    const idInput   = document.getElementById('new-node-id');
    if (nameInput) nameInput.value = '';
    if (idInput)   idInput.value   = '';
    // Clear any error states
    document.querySelectorAll('.field-error').forEach(e => e.remove());
}

async function confirmAddNode() {
    const nameInput = document.getElementById('new-node-name');
    const idInput   = document.getElementById('new-node-id');
    const name = nameInput ? nameInput.value.trim() : '';
    const id   = idInput   ? parseInt(idInput.value) : NaN;

    if (!name)                   { highlightError('new-node-name', 'Node name is required'); return; }
    if (!id || isNaN(id) || id < 1) { highlightError('new-node-id', 'Please enter a valid Node ID (≥ 1)'); return; }
    if (nodeList.some(n => n.id === id))   { highlightError('new-node-id', `Node ID ${id} already exists`); return; }
    if (nodeList.some(n => n.name.toLowerCase() === name.toLowerCase())) {
        highlightError('new-node-name', `A node named "${name}" already exists`); return;
    }

    const confirmBtn = document.getElementById('confirm-add-node');
    if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...'; }

    try {
        const res = await fetch('http://localhost:3000/nodes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ node_id: id, name })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || 'Server error');
        }

        // Add to local state and re-render
        nodeList.push({ id, name });
        renderAllNodes();

        closeAddNodeModal();
        showNotification(`${name} saved successfully`, 'success');

    } catch (err) {
        console.error('Failed to save node:', err);
        showNotification(`Failed to save: ${err.message}`, 'error');
    } finally {
        if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.innerHTML = '<i class="fas fa-plus"></i> Add Node'; }
    }
}

function highlightError(inputId, message) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.style.borderColor = '#ef4444';
    input.style.boxShadow = '0 0 0 3px rgba(239,68,68,0.1)';
    input.focus();

    const existing = input.parentElement.querySelector('.field-error');
    if (existing) existing.remove();

    const errEl = document.createElement('span');
    errEl.className = 'field-error';
    errEl.style.cssText = 'color:#ef4444;font-size:0.75rem;margin-top:2px;display:block;';
    errEl.textContent = message;
    input.parentElement.appendChild(errEl);

    input.addEventListener('input', () => {
        input.style.borderColor = '';
        input.style.boxShadow = '';
        if (errEl.parentElement) errEl.remove();
    }, { once: true });
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─── Data Fetching ────────────────────────────────────────────────────────────
function mapRangeToBackend(range) {
    if (range === 'day')   return 'day';
    if (range === 'week')  return 'lastWeek';
    if (range === 'month') return 'lastMonth';
    return 'realtime';
}

function updateParametersForNode(node, range = 'realtime') {
    fetch(`http://localhost:3000/soil-data/${node}?range=${range}`)
        .then(res => res.json())
        .then(dataArray => {
            if (!dataArray || dataArray.length === 0) {
                clearParameterCards();
                return;
            }

            let data;
            if (range === 'realtime' || range === 'day') {
                data = {
                    ph:          Number(dataArray[0].ph),
                    temperature: Number(dataArray[0].temperature),
                    ec:          Number(dataArray[0].ec),
                    humidity:    Number(dataArray[0].humidity)
                };
                if (probeNotInSoil(data.humidity, data.ec)) {
                    showProbeWarning(data);
                    return;
                }
            } else {
                // Leave out readings taken while the probe was not in the soil
                const valid = dataArray.filter(d => !probeNotInSoil(Number(d.humidity), Number(d.ec)));
                if (valid.length === 0) {
                    showProbeWarning({
                        ph: Number(dataArray[0].ph), temperature: Number(dataArray[0].temperature),
                        ec: Number(dataArray[0].ec), humidity: Number(dataArray[0].humidity)
                    });
                    return;
                }
                dataArray = valid;
                const avg = key => dataArray.reduce((s,d) => s + Number(d[key]), 0) / dataArray.length;
                data = {
                     ph:          Number(avg('ph').toFixed(2)),
                     temperature: Number(avg('temperature').toFixed(1)),
                     ec:          Number(avg('ec').toFixed(2)),
                     humidity:    Number(avg('humidity').toFixed(1)),
         };
                    }
            

        const ec_dSm = (data.ec / 1000).toFixed(2);
        const tempF = (data.temperature * 9/5 + 32).toFixed(1);

        animateValueUpdate('.param-value', {
        'pH Level': data.ph.toFixed(1),
        'Temperature': `${data.temperature}°C (${tempF}°F)`,
        'Electrical Conductivity': `${ec_dSm} dS/m`,
        'Humidity': `${data.humidity}`
        });
            updateProgressBars(data);
            updateStatuses(data);
            updateRecommendation(data);
        })
        .catch(err => console.error('Error fetching soil data:', err));
}

// Exactly 0 % moisture or 0 EC: the probe is not in contact with the soil
// (real soil, even very dry, always reads above 0). Same check as soil_rules.py.
function probeNotInSoil(humidity, ec) {
    return humidity <= 0 || ec <= 0;
}

function showProbeWarning(data) {
    animateValueUpdate('.param-value', {
        'pH Level': data.ph.toFixed(1),
        'Temperature': `${data.temperature}°C`,
        'Electrical Conductivity': `${(data.ec / 1000).toFixed(2)} dS/m`,
        'Humidity': `${data.humidity}`
    });
    document.querySelectorAll('.parameter-card').forEach(card => {
        card.classList.remove('good','moderate','bad');
        const s = card.querySelector('.param-status');
        if (s) {
            s.classList.remove('good','moderate','bad');
            s.textContent = 'Check probe';
        }
        const f = card.querySelector('.range-fill');
        if (f) f.style.width = '0%';
    });
    const rec = document.getElementById('recommendation-section');
    if (rec) rec.innerHTML = `
        <div class="recommendation-header" style="grid-column: 1 / -1; margin-bottom: 16px;">
            <h2 class="section-title" style="font-size: 1.25rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 10px; margin: 0;">
                <i class="fas fa-lightbulb" style="color: var(--text-primary);"></i> Recommendations
            </h2>
        </div>
        <div class="rec-card overall-card">
            <h3>Check probe: not reading soil</h3>
            <p>This node reads ${data.humidity}% moisture and ${(data.ec / 1000).toFixed(2)} dS/m EC. Real soil never reads exactly 0, so the probe is likely out of the soil or not in contact with it. Push the probe fully into the soil. This reading is left out of the soil condition and the Field Assessment.</p>
        </div>
    `;
}

function clearParameterCards() {
    document.querySelectorAll('.parameter-card').forEach(card => {
        const v = card.querySelector('.param-value');
        if (v) {
            v.textContent = '--';
            v.classList.remove('good','moderate','bad');
        }
        const s = card.querySelector('.param-status');
        if (s) {
            s.textContent = '--';
            s.classList.remove('good','moderate','bad');
        }
        card.classList.remove('good','moderate','bad');
        const f = card.querySelector('.range-fill');
        if (f) f.style.width = '0%';
    });
    const rec = document.getElementById('recommendation-section');
    if (rec) rec.innerHTML = '';
}

function handleTimeRangeChange() {
    const range = mapRangeToBackend(document.getElementById('time-range').value);
    updateParametersForNode(currentNode, range);
}

function animateValueUpdate(selector, values) {
    document.querySelectorAll(selector).forEach(el => {
        const card = el.closest('.parameter-card');
        if (!card) return;
        const title = card.querySelector('h3')?.textContent;
        if (title && values[title] !== undefined) {
            setTimeout(() => { el.textContent = values[title]; }, 300);
        }
    });
}

// ─── Soil Rating Rules ───────────────────────────────────────────────────────
// Same thresholds as train_soil_rf.py (Tables 3–6). Returns the CSS class:
// 'good' = Healthy, 'moderate' = Moderate, 'bad' = Poor.
const RATING_LABEL = { good: 'Healthy', moderate: 'Moderate', bad: 'Poor' };

// Sensor reports EC in µS/cm; the salinity table is in dS/m
function ecToDsm(ecUScm) {
    return Number(ecUScm) / 1000;
}

function ratePh(ph) {
    // Table 3: 6.5–7.5 neutral; acidic or alkaline = Moderate (no Poor class)
    return (ph >= 6.5 && ph <= 7.5) ? 'good' : 'moderate';
}

function rateTemperature(t) {
    // Table 6: ≤ 90 °F (32.2 °C) ok, 90–100 °F growth slows, > 100 °F (37.8 °C) moisture lost
    if (t <= 32.2) return 'good';
    if (t <= 37.8) return 'moderate';
    return 'bad';
}

function rateEc(ecDsm) {
    // Table 4: < 2 non-saline, 2–8 very slightly / slightly saline, ≥ 8 moderately–strongly saline
    if (ecDsm < 2.0) return 'good';
    if (ecDsm < 8.0) return 'moderate';
    return 'bad';
}

// Soil moisture for palay (lowland rice) on Bulaoen clay loam, volumetric %
const WILTING_POINT = 24.0;   // clay loam (Easton & Bock, 2021)
const SATURATION    = 46.4;   // clay loam porosity (Rawls et al., 1982) — PROVISIONAL: verify or measure in the field
const P_RICE        = 0.20;   // rice: allowable depletion = 0.20 of saturation (FAO-56, Table 22)
const MOISTURE_HEALTHY_MIN = SATURATION - P_RICE * (SATURATION - WILTING_POINT);   // ≈ 41.9 %

function rateHumidity(h) {
    if (h >= MOISTURE_HEALTHY_MIN) return 'good';      // near saturation
    if (h > WILTING_POINT)         return 'moderate';  // drying, irrigate
    return 'bad';                                       // at or below wilting point
}

function rateAll(data) {
    return {
        ph:          ratePh(data.ph),
        temperature: rateTemperature(data.temperature),
        ec:          rateEc(ecToDsm(data.ec)),
        humidity:    rateHumidity(data.humidity),
    };
}

// Maximum limitation method: the worst parameter decides
function overallRating(ratings) {
    const values = Object.values(ratings);
    if (values.includes('bad'))      return 'bad';
    if (values.includes('moderate')) return 'moderate';
    return 'good';
}

function updateProgressBars(data) {
    document.querySelectorAll('.range-fill').forEach(fill => {
        const title = fill.closest('.parameter-card')?.querySelector('h3')?.textContent;
        if (title === 'pH Level')               fill.style.width = `${Math.min((data.ph / 14) * 100, 100)}%`;
        if (title === 'Temperature')            fill.style.width = `${Math.min((data.temperature / 40) * 100, 100)}%`;
        if (title === 'Electrical Conductivity')fill.style.width = `${Math.min((ecToDsm(data.ec) / 8) * 100, 100)}%`;
        if (title === 'Humidity')               fill.style.width = `${Math.min(data.humidity, 100)}%`;
    });
}

function updateStatuses(data) {
    const ratings = rateAll(data);
    const byTitle = {
        'pH Level':                ratings.ph,
        'Temperature':             ratings.temperature,
        'Electrical Conductivity': ratings.ec,
        'Humidity':                ratings.humidity,
    };

    document.querySelectorAll('.parameter-card').forEach(card => {
        const title = card.querySelector('h3')?.textContent;
        const statusEl = card.querySelector('.param-status');

        if (!statusEl || !title) return;

        statusEl.classList.remove('good','moderate','bad');
        card.classList.remove('good','moderate','bad');

        const rating = byTitle[title];
        if (!rating) {
            statusEl.textContent = '--';
            return;
        }
        statusEl.classList.add(rating);
        card.classList.add(rating);
        statusEl.textContent = RATING_LABEL[rating];
    });
}

function updateRecommendation(data) {
    const ratings = rateAll(data);
    const ecDsm = ecToDsm(data.ec);

    // ── pH ──
    let phRec;
    if (ratings.ph === 'good') {
        phRec = `pH ${data.ph} is neutral — perfect for most crops. No action needed at this time.`;
    } else if (data.ph < 5.5) {
        phRec = `pH ${data.ph} is strongly acidic — plants cannot absorb nutrients properly. Apply lime and consult your local agriculturist.`;
    } else if (data.ph < 6.5) {
        phRec = `pH ${data.ph} is acidic. Apply agricultural lime to raise it closer to 6.5. Recheck after 2 weeks.`;
    } else if (data.ph <= 8.5) {
        phRec = `pH ${data.ph} is alkaline. Apply compost or elemental sulfur to bring it down. Avoid irrigating with hard water.`;
    } else {
        phRec = `pH ${data.ph} is strongly alkaline — iron, zinc, and other nutrients may be locked out. Use an acidifying fertilizer or sulfur treatment.`;
    }

    // ── Temperature ──
    let tempRec;
    if (ratings.temperature === 'good') {
        tempRec = `Soil temperature is ${data.temperature}°C — within the normal range (up to 32.2°C / 90°F). No action needed.`;
    } else if (ratings.temperature === 'moderate') {
        tempRec = `Soil temperature is ${data.temperature}°C — plant growth slows above 32.2°C (90°F). Apply mulch and water early in the morning or late afternoon.`;
    } else {
        tempRec = `Soil temperature is ${data.temperature}°C — above 37.8°C (100°F), most soil moisture is lost. Mulch, provide shade, and irrigate right away.`;
    }

    // ── EC (Electrical Conductivity) ──
    let ecRec;
    if (ecDsm < 2.0) {
        ecRec = `EC is ${ecDsm.toFixed(2)} dS/m — Non-Saline. Salt levels are safe and plants can absorb water and nutrients freely. No action needed.`;
    } else if (ecDsm < 4.0) {
        ecRec = `EC is ${ecDsm.toFixed(2)} dS/m — Very Slightly Saline. Reduce fertilizer application and water deeply to flush excess salts through the soil.`;
    } else if (ecDsm < 8.0) {
        ecRec = `EC is ${ecDsm.toFixed(2)} dS/m — Slightly Saline. Sensitive crops may already be affected. Apply deep irrigation and pause fertilizer until levels drop.`;
    } else if (ecDsm < 16) {
        ecRec = `EC is ${ecDsm.toFixed(2)} dS/m — Moderately Saline. Most crops struggle at this level. Perform deep leaching with clean water and consult an expert.`;
    } else {
        ecRec = `EC is ${ecDsm.toFixed(2)} dS/m — Strongly Saline. Most crops cannot survive. Do not plant until EC is lowered; seek immediate expert guidance.`;
    }

    // ── Humidity ──
    let humRec;
    if (ratings.humidity === 'good') {
        humRec = `Soil moisture is ${data.humidity}% — the soil is near saturation, as palay needs. No irrigation needed.`;
    } else if (ratings.humidity === 'moderate') {
        humRec = `Soil moisture is ${data.humidity}% — the soil is drying. Irrigate or re-flood to bring it back above ${MOISTURE_HEALTHY_MIN.toFixed(0)}%.`;
    } else {
        humRec = `Soil moisture is ${data.humidity}% — at or below the wilting point (${WILTING_POINT}%). Irrigate immediately.`;
    }

    // ── Overall (maximum limitation method) ──
    const overall = overallRating(ratings);
    const limiting = [
        ['pH', ratings.ph], ['temperature', ratings.temperature],
        ['EC', ratings.ec], ['soil moisture', ratings.humidity],
    ].filter(([, r]) => r === overall).map(([name]) => name);
    const overallRec = overall === 'good'
        ? 'All four parameters are within the healthy range.'
        : `Limited by ${limiting.join(', ')}. The worst parameter decides the overall soil condition.`;

    const recGrid = document.getElementById('recommendation-section');
    if (!recGrid) return;

    recGrid.innerHTML = `
        <div class="recommendation-header" style="grid-column: 1 / -1; margin-bottom: 16px;">
            <h2 class="section-title" style="font-size: 1.25rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 10px; margin: 0;">
                <i class="fas fa-lightbulb" style="color: var(--text-primary);"></i> Recommendations
            </h2>
        </div>
        <div class="rec-card overall-card">
            <h3>Soil Condition: ${RATING_LABEL[overall]}</h3>
            <p>${overallRec}</p>
        </div>
        <div class="rec-card ${ratings.ph}-card">
            <h3>Soil pH</h3>
            <p>${phRec}</p>
        </div>
        <div class="rec-card ${ratings.temperature}-card">
            <h3>Temperature</h3>
            <p>${tempRec}</p>
        </div>
        <div class="rec-card ${ratings.ec}-card">
            <h3>Salt Level (EC)</h3>
            <p>${ecRec}</p>
        </div>
        <div class="rec-card ${ratings.humidity}-card">
            <h3>Soil Humidity</h3>
            <p>${humRec}</p>
        </div>
    `;
}

// ─── Live Updates ─────────────────────────────────────────────────────────────
function startLiveUpdates() {
    setInterval(() => {
        const range = document.getElementById('time-range')?.value;
        if (range === 'realtime' || range === 'day') {
            updateParametersForNode(currentNode, mapRangeToBackend(range));
        }
    }, 5000);
}

// ─── Notification ─────────────────────────────────────────────────────────────
function showNotification(message, type = 'info') {
    const old = document.querySelector('.notification');
    if (old) old.remove();

    const note = document.createElement('div');
    note.className = 'notification';
    note.style.cssText = `
        position:fixed;top:20px;right:20px;
        padding:16px 24px;border-radius:8px;
        color:white;font-weight:500;z-index:99999;
        box-shadow:0 4px 12px rgba(0,0,0,0.2);
        animation:slideIn 0.3s ease;
        font-family:'Inter',sans-serif;
    `;
    const colors = { success:'#10b981', error:'#ef4444', warning:'#f59e0b', info:'#0f766e' };
    note.style.backgroundColor = colors[type] || colors.info;
    note.textContent = message;
    document.body.appendChild(note);

    setTimeout(() => {
        if (note.parentNode) {
            note.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => note.remove(), 300);
        }
    }, 3000);
}

// ─── Modal (node detail) ──────────────────────────────────────────────────────
function closeModal() {
    const m = document.getElementById('node-modal');
    if (m) m.style.display = 'none';
}

// ─── Injected Styles ──────────────────────────────────────────────────────────
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn { from{transform:translateX(100%);opacity:0} to{transform:translateX(0);opacity:1} }
    @keyframes slideOut{ from{transform:translateX(0);opacity:1}    to{transform:translateX(100%);opacity:0} }

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
        border: 1px solid var(--border);
        background: var(--bg-surface);
        box-shadow: var(--shadow-sm);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .rec-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
    .rec-card h3 { font-size:0.9rem; font-weight:600; margin-bottom:8px; color:var(--text-secondary); }
    .rec-card p  { font-size:0.85rem; line-height:1.4; margin:0; color:var(--text-muted); }
    .rec-card.overall-card { background:var(--brand-light); border-left:4px solid var(--brand); }
    .rec-card.overall-card h3,
    .rec-card.overall-card p { color: var(--brand-dark); }
    #confirm-add-node:disabled { opacity:0.7; cursor:not-allowed; transform:none; }

    @media(max-width:1200px){ .recommendation-grid{ grid-template-columns:repeat(3,1fr); } }
    @media(max-width:768px) { .recommendation-grid{ grid-template-columns:repeat(2,1fr); } }
    @media(max-width:480px) { .recommendation-grid{ grid-template-columns:1fr; } }
`;
document.head.appendChild(style);