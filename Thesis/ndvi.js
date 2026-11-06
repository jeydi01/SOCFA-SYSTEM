// ─── Theme ───────────────────────────────────────────────────────────────────
function initTheme() { applyTheme(localStorage.getItem('socfa-theme') || 'light'); }
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('theme-icon');
    const logoText = document.querySelector('.logo-text');
    const microscopeIcon = document.querySelector('.upload-title i');
    if (icon) icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    if (logoText) logoText.style.color = theme === 'dark' ? '#ffffff' : '#000000';
    if (microscopeIcon) microscopeIcon.style.color = theme === 'dark' ? '#ffffff' : '#000000';
    localStorage.setItem('socfa-theme', theme);
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    document.getElementById('theme-toggle')?.addEventListener('click', () => {
        applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });
    document.getElementById('upload-input')?.addEventListener('change', handleUploadFile);
    document.querySelectorAll('#view-switch button').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));
    document.getElementById('clear-upload-btn')?.addEventListener('click', clearUploadPreview);
    document.getElementById('drone-btn')?.addEventListener('click', openDroneModal);
    document.getElementById('capture-btn')?.addEventListener('click', takePhotosNow);
    document.getElementById('close-drone-modal')?.addEventListener('click', closeDroneModal);
    document.getElementById('drone-modal')?.addEventListener('click', e => { if (e.target.id === 'drone-modal') closeDroneModal(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDroneModal(); });
    updateTime();
    setInterval(updateTime, 1000);
    updateLastUpdateTime();
    loadNdviThresholds();
    initCaptureOpts();
    checkDroneLatest();
    setInterval(checkDroneLatest, 10000);
    pollCaptureStatus();
    setInterval(pollCaptureStatus, 3000);
});

// ─── NDVI guide ranges (thresholds come from app.py / ndvi_core.py) ──────────
async function loadNdviThresholds() {
    try {
        const res = await fetch(`${API}/health`);
        const data = await res.json();
        if (data.ndvi_thresholds) applyNdviThresholds(data.ndvi_thresholds);
    } catch (e) {
        // app.py not running yet: the guide keeps its Table 7 defaults
    }
}

function applyNdviThresholds(th) {
    const fmt = v => Number(v).toFixed(2);
    const ranges = {
        bare:   `0.00 to ${fmt(th.poor_max)}`,
        sparse: `${fmt(th.poor_max)} to ${fmt(th.moderate_max)}`,
        dense:  `above ${fmt(th.moderate_max)}`,
    };
    document.querySelectorAll('[data-ndvi-range]').forEach(el => {
        el.textContent = ranges[el.dataset.ndviRange];
    });
}

// ─── State ────────────────────────────────────────────────────────────────────
let uploadedImage = null;
let currentCapture = null;   // {flight, pair} when the image came from the drone
let viewImages = {}, currentView = null;   // drone result views: rgb / noir / ndvi
const API = 'http://localhost:5000';

// ─── Upload File ──────────────────────────────────────────────────────────────
function handleUploadFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        const img = new Image();
        img.onload = function () {
            uploadedImage = img;
            currentCapture = null; resetViews();
            drawUploadPreview();
            document.getElementById('upload-overlay-text').style.display = 'none';
            document.getElementById('upload-status').textContent = 'Image loaded — analyzing automatically...';
            autoAnalyze();
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

// ─── Auto Analyze ─────────────────────────────────────────────────────────────
function autoAnalyze() {
    if (!uploadedImage) return;
    const canvas = document.createElement('canvas');
    canvas.width = uploadedImage.width; canvas.height = uploadedImage.height;
    canvas.getContext('2d').drawImage(uploadedImage, 0, 0);
    analyzeImage({ image: canvas.toDataURL('image/png') });
}

// ─── Draw Preview ─────────────────────────────────────────────────────────────
function drawUploadPreview() {
    const canvas = document.getElementById('upload-preview-canvas');
    // Drone result: the chosen view (aligned RGB / NoIR / NDVI maps); upload: the photo
    const img = (currentView && viewImages[currentView]) || uploadedImage;
    if (!canvas || !img) return;
    const ctx = canvas.getContext('2d');
    const container = canvas.parentElement;
    const maxW = Math.max(container.clientWidth - 2, 200), maxH = 420;
    const scale = Math.min(maxW / img.width, maxH / img.height, 1);
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
}

// ─── Preview views: RGB | NoIR | NDVI (drone results, aligned) ─────────────────
function resetViews() {
    viewImages = {};
    currentView = null;
    renderViewSwitch();
}

function loadView(name, src, makeCurrent = false) {
    const im = new Image();
    im.crossOrigin = 'anonymous';
    im.onload = () => {
        viewImages[name] = im;
        if (makeCurrent || !currentView) currentView = name;
        renderViewSwitch();
        drawUploadPreview();
    };
    im.src = src;
}

function setView(name) {
    if (!viewImages[name]) return;
    currentView = name;
    renderViewSwitch();
    drawUploadPreview();
}

function renderViewSwitch() {
    const box = document.getElementById('view-switch');
    if (!box) return;
    box.hidden = !viewImages.ndvi;                               // only drone results have views
    box.querySelectorAll('button').forEach(b => {
        b.hidden = !viewImages[b.dataset.view];
        b.classList.toggle('active', b.dataset.view === currentView);
    });
}

// ─── Clear ────────────────────────────────────────────────────────────────────
function clearUploadPreview() {
    uploadedImage = null;
    currentCapture = null; resetViews();
    const canvas = document.getElementById('upload-preview-canvas');
    if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    document.getElementById('upload-overlay-text').style.display = 'block';
    document.getElementById('upload-status').textContent = 'Ready — load or upload a field image to start analysis.';
    document.getElementById('upload-input').value = '';
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('results-empty').style.display = 'flex';
}

// ─── CNN Analysis ─────────────────────────────────────────────────────────────
// payload: { image: dataURL } for uploads, or { capture: {flight, pair} } for drone pairs
async function analyzeImage(payload) {
    document.getElementById('upload-status').textContent = 'Analyzing image...';
    let reached = false;   // true once app.py answered
    try {
        const res = await fetch(`${API}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, field: 'Field Analysis', coordinates: { lat: 14.5995, lng: 120.9842 } })
        });
        reached = true;
        const result = await res.json();
        if (result.success) {
            showAnalysis(result, 'Analysis complete — see results on the right.');
        } else throw new Error(result.error);
    } catch (err) {
        console.error(err);
        if (!reached) {
            showNotification('Could not reach Python API. Is app.py running?', 'error');
            document.getElementById('upload-status').textContent = 'Analysis failed. Make sure app.py is running on port 5000.';
        } else {
            showNotification(`Analysis error: ${err.message}`, 'error');
            document.getElementById('upload-status').textContent = `Analysis failed: ${err.message}`;
        }
    }
}

// Show an analysis result (from /analyze or from an automatic drone result)
function showAnalysis(result, statusText, notePrefix = '') {
    document.getElementById('upload-status').textContent = statusText;
    renderResults(result);
    if (result.ndvi_thresholds) applyNdviThresholds(result.ndvi_thresholds);
    // Drone pair: open on the map of the NDVI used for the class (NDVI_SOURCE in ndvi_core.py);
    // the other NDVI is still saved in auto_result.json, just not shown
    const flight = (currentCapture && currentCapture.flight) || result.flight;
    const decide = result.ndvi_source === 'red' && result.ndvi_red_map ? 'ndvi_red' : 'ndvi';
    if (result.aligned_files && flight) {
        const base = `${API}/captures/${encodeURIComponent(flight)}/`;
        loadView('rgb', base + encodeURIComponent(result.aligned_files.rgb));
        loadView('noir', base + encodeURIComponent(result.aligned_files.noir));
    } else if (uploadedImage && (result.ndvi_map || result.ndvi_red_map)) {
        viewImages.rgb = uploadedImage;
    }
    const usedMap = decide === 'ndvi_red' ? result.ndvi_red_map : result.ndvi_map;
    if (usedMap) loadView('ndvi', usedMap, true);
    document.getElementById('results-section').style.display = 'block';
    document.getElementById('results-empty').style.display = 'none';
    showNotification(notePrefix + (result.method === 'ndvi_cnn'
        ? `NDVI + CNN: ${result.health_class.toUpperCase()} (${Math.round(result.confidence*100)}%)`
        : `CNN only: ${result.health_class.toUpperCase()} (${Math.round(result.confidence*100)}%, no NoIR photo)`),
        result.health_class === 'healthy' ? 'success' : result.health_class === 'moderate' ? 'warning' : 'error');
}

// ─── Take Photos button + live capture indicator ─────────────────────────────
// The Pi takes CAPTURE_PAIRS photo pairs right away; when it finishes, app.py
// analyzes the flight and checkDroneLatest() shows the result automatically.
// The indicator shows the drone's real state (also for the capture at power-on).
const CAPTURE_OPTS_KEY = 'socfa-capture-opts';

// Spot label + number of pairs for Take Photos (remembered in this browser)
function initCaptureOpts() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(CAPTURE_OPTS_KEY) || '{}'); } catch (e) { saved = {}; }
    document.getElementById('spot-input').value = saved.spot || '';
    document.getElementById('pairs-select').value = String(saved.pairs || 3);
    const store = () => {
        try {
            localStorage.setItem(CAPTURE_OPTS_KEY, JSON.stringify({
                spot: document.getElementById('spot-input').value.trim(),
                pairs: Number(document.getElementById('pairs-select').value)
            }));
        } catch (e) { /* storage unavailable: options just aren't remembered */ }
    };
    document.getElementById('spot-input').addEventListener('change', store);
    document.getElementById('pairs-select').addEventListener('change', store);
}

// A-03 → A-04, B9 → B10 (keeps leading zeros); labels without a number stay the same
function nextSpot(spot) {
    const m = spot.match(/^(.*?)(\d+)$/);
    if (!m) return spot;
    const n = String(Number(m[2]) + 1).padStart(m[2].length, '0');
    return m[1] + n;
}
const CAPTURE_BTN_LABEL = '<i class="fas fa-camera"></i> Take Photos';
let captureRequestedAt = 0;   // button pressed, Pi not reporting the capture yet

async function takePhotosNow() {
    const btn = document.getElementById('capture-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
    try {
        const spotInput = document.getElementById('spot-input');
        const spot = spotInput.value.trim().toUpperCase().replace(/[^A-Z0-9_-]/g, '');
        const res = await fetch(`${API}/drone/capture`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count: Number(document.getElementById('pairs-select').value), spot })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Could not start the capture');
        captureRequestedAt = Date.now();
        showNotification(`Taking ${data.count} photo pairs${data.spot ? ` for spot ${data.spot}` : ''}. Keep the cameras still — the result appears here automatically.`, 'success');
        if (spot) {                                   // ready for the next spot
            spotInput.value = nextSpot(spot);
            spotInput.dispatchEvent(new Event('change'));
        }
        pollCaptureStatus();
    } catch (err) {
        showNotification(err.message === 'Failed to fetch'
            ? 'Could not reach app.py. Is it running?' : err.message, 'error');
        btn.disabled = false;
        btn.innerHTML = CAPTURE_BTN_LABEL;
    }
}

async function pollCaptureStatus() {
    let s = null;
    try {
        s = await (await fetch(`${API}/drone/capture-status`)).json();
    } catch (e) { /* app.py not running */ }
    const starting = Date.now() - captureRequestedAt < 12000;     // Pi takes a few seconds to start
    let state = s ? s.state : 'idle';
    if (state === 'idle' && starting) state = 'preparing';
    renderCaptureIndicator(state, s || {});
}

function renderCaptureIndicator(state, s) {
    const box = document.getElementById('capture-indicator');
    const text = document.getElementById('capture-indicator-text');
    const track = document.getElementById('capture-indicator-track');
    const fill = document.getElementById('capture-indicator-fill');
    const btn = document.getElementById('capture-btn');
    if (!box || !btn) return;

    box.classList.remove('preparing', 'capturing', 'analyzing');
    track.hidden = true;
    if (state === 'capturing') {
        const of = s.target ? ` of ${s.target}` : '';
        text.textContent = `Capturing${s.spot ? ` spot ${s.spot}` : ''} — ${s.pairs}${of} photo pairs. Keep the cameras still.`;
        if (s.target) { track.hidden = false; fill.style.width = `${Math.min(100, s.pairs / s.target * 100)}%`; }
        btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Capturing...';
    } else if (state === 'preparing') {
        text.textContent = 'Drone is getting ready to take photos...';
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
    } else if (state === 'analyzing') {
        text.textContent = 'Photos done — analyzing (NDVI + CNN)...';
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
    }
    const busy = state === 'capturing' || state === 'preparing' || state === 'analyzing';
    box.hidden = !busy;
    if (busy) box.classList.add(state);
    btn.disabled = busy;
    if (!busy) btn.innerHTML = CAPTURE_BTN_LABEL;
}

// ─── Automatic drone results ─────────────────────────────────────────────────
// After landing, app.py imports and analyzes each new flight by itself; this
// checks for the newest result and shows it without any button.
let autoShownAt = null;      // processed_at of the drone result on screen
let autoChecked = false;     // false until the first check after the page opened

async function checkDroneLatest() {
    let data;
    try {
        data = await (await fetch(`${API}/drone/latest`)).json();
    } catch (e) {
        return;              // app.py not running: nothing to show
    }
    const r = data.result;
    const isNew = r && r.processed_at !== autoShownAt;
    if (isNew) {
        autoShownAt = r.processed_at;
        if (r.success) showAutoResult(r, autoChecked);
        else if (autoChecked) showNotification(`Drone flight ${r.flight}: ${r.error}`, 'error');
    } else if (!uploadedImage && data.status) {
        document.getElementById('upload-status').textContent = data.status.message;
    }
    autoChecked = true;
}

function showAutoResult(r, isNewArrival) {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
        uploadedImage = img;
        currentCapture = { flight: r.flight, pair: r.pair }; resetViews();
        drawUploadPreview();
        document.getElementById('upload-overlay-text').style.display = 'none';
        showAnalysis(r,
            `Drone ${r.flight}${r.spot ? ` · spot ${r.spot}` : ''} — pair ${r.pair} of ${r.pairs_in_flight} (sharpest), analyzed automatically.`,
            isNewArrival ? 'New drone result — ' : '');
    };
    img.onerror = () => showAnalysis(r, `Drone ${r.flight} — analyzed automatically (photo not available).`);
    img.src = `${API}/captures/${encodeURIComponent(r.flight)}/${encodeURIComponent(r.rgb)}`;
}

// ─── Render Results ───────────────────────────────────────────────────────────
function renderResults(result) {
    const container = document.getElementById('results-content');
    if (!container) return;
    const cls = result.health_class;
    const conf = Math.round(result.confidence * 100);
    const hasNdvi = result.ndvi_value != null;                          // real NDVI from the NoIR photo
    const usesRed = result.ndvi_source === 'red' && result.ndvi_red_shares != null;
    const ndviMean = usesRed ? result.ndvi_red_value : result.ndvi_value;   // the NDVI used for the class
    // The class comes from the share of area in each NDVI class, not from the
    // average, so the average is shown as a plain number (no class colour/label)
    const th = result.ndvi_thresholds || { poor_max: 0.15, moderate_max: 0.55 };
    const probs = result.class_probabilities || {};
    // NDVI decides when there is a NoIR photo; otherwise the RGB CNN is the backup
    const byNdvi = result.method === 'ndvi_cnn';
    const confText = byNdvi ? `${conf}% · NDVI + CNN` : `${conf}% confidence · CNN only (no NoIR photo)`;

    const cfg = {
        healthy:  { color:'#1D9E75', bg:'#e1f5ee', icon:'fa-check-circle',        label:'Healthy Vegetation Detected',  rec:'Excellent vegetation health. Continue current farming practices and monitor for seasonal changes.' },
        moderate: { color:'#EF9F27', bg:'#fdf3e3', icon:'fa-exclamation-circle',   label:'Moderate Vegetation Detected', rec:'Moderate health. Monitor closely and consider soil testing or adjusted irrigation.' },
        poor:     { color:'#E24B4A', bg:'#fdecea', icon:'fa-exclamation-triangle', label:'Poor Vegetation Detected',     rec:'Immediate attention required. Check soil conditions, irrigation, and pest control.' }
    };
    const c = cfg[cls] || cfg.poor;

    container.innerHTML = `
        <div class="result-card">
            <div class="result-header" style="background:${c.bg};">
                <div class="health-indicator" style="background:${c.color};">
                    <i class="fas ${c.icon}"></i>
                </div>
                <div class="result-title">
                    <h4 style="color:${c.color};">${c.label}</h4>
                    <span class="confidence" style="color:${c.color};">${confText}</span>
                </div>
            </div>

            <div class="result-metrics" style="grid-template-columns:repeat(${hasNdvi ? 2 : 1},minmax(0,1fr));">
                ${hasNdvi ? `
                <div class="metric" title="Average over the whole photo. ${Math.round(result.ndvi_shares.healthy * 100)}% of the area at NDVI ≥ ${th.moderate_max}, ${Math.round(result.ndvi_shares.poor * 100)}% below ${th.poor_max}.">
                    <span class="metric-label">NDVI</span>
                    <span class="metric-value">${ndviMean != null ? ndviMean.toFixed(3) : '--'}</span>
                    <span class="metric-unit">Average</span>
                </div>` : ''}
                <div class="metric">
                    <span class="metric-label">Health Class</span>
                    <span class="metric-value" style="color:${c.color};">${cls.charAt(0).toUpperCase()+cls.slice(1)}</span>
                    <span class="metric-unit">${byNdvi ? 'NDVI + CNN' : 'CNN only'}</span>
                </div>
            </div>
            ${hasNdvi ? '' : `
            <div class="ndvi-missing" style="margin:10px 0 0;padding:8px 12px;border-radius:10px;font-size:12px;line-height:1.5;background:#fdf3e3;color:#9a5b0a;">
                <i class="fas fa-circle-info"></i> No NDVI for this photo — NDVI needs the NoIR photo, which comes with each drone capture.
                Pick a capture <b>From Drone</b> for the NDVI result.
            </div>`}
            ${hasNdvi && usesRed ? alignmentLine(result.alignment) : ''}
            ${hasNdvi ? ndviSection('NDVI', result.ndvi_shares, ndviMean, th, cfg, false, '') : ''}

            <div class="class-probabilities">
                <h5>${byNdvi ? 'Combined (average of CNN and NDVI)' : 'Class Probabilities (CNN)'}</h5>
                <div class="prob-bars">
                    <div class="prob-bar">
                        <span class="prob-label">Healthy:</span>
                        <div class="prob-fill" style="width:${((probs.healthy||0)*100).toFixed(1)}%;background:#1D9E75;"></div>
                        <span class="prob-value" style="color:#1D9E75;">${((probs.healthy||0)*100).toFixed(1)}%</span>
                    </div>
                    <div class="prob-bar">
                        <span class="prob-label">Moderate:</span>
                        <div class="prob-fill" style="width:${((probs.moderate||0)*100).toFixed(1)}%;background:#EF9F27;"></div>
                        <span class="prob-value" style="color:#EF9F27;">${((probs.moderate||0)*100).toFixed(1)}%</span>
                    </div>
                    <div class="prob-bar">
                        <span class="prob-label">Poor:</span>
                        <div class="prob-fill" style="width:${((probs.poor||0)*100).toFixed(1)}%;background:#E24B4A;"></div>
                        <span class="prob-value" style="color:#E24B4A;">${((probs.poor||0)*100).toFixed(1)}%</span>
                    </div>
                </div>
                ${byNdvi ? `
                <div class="prob-parts" style="margin-top:10px;font-size:12px;line-height:1.6;color:var(--text-muted);">
                    <div><b>CNN</b> (RGB photo): ${partLine(result.cnn_probabilities)}</div>
                    <div><b>NDVI</b> (share of area): ${partLine(result.ndvi_shares)}</div>
                </div>` : ''}
            </div>

        </div>
    `;
}

// How the NoIR photo was lined up with the RGB photo
function alignmentLine(a) {
    if (!a) return '';
    const text = a.method === 'auto'  ? `Photos aligned automatically (${a.inliers} matching points · ${Math.round(a.kept_pct)}% of the photo kept)`
               : a.method === 'saved' ? `Photos aligned with the last good alignment (this pair had too few details to match) · ${Math.round(a.kept_pct)}% kept`
               : 'Photos could not be aligned — red NDVI not available for this pair';
    const icon = a.method === 'none' ? 'fa-triangle-exclamation' : 'fa-object-group';
    return `<div style="margin:10px 0 0;font-size:12px;color:var(--text-muted);"><i class="fas ${icon}"></i> ${text}</div>`;
}

// One NDVI on its own: class = the NDVI class covering most of the area
function ndviSection(title, shares, mean, th, cfg, decides, badge) {
    const s = shares || {};
    const ndviCls = ['healthy', 'moderate', 'poor'].reduce((a, b) => (s[b] || 0) > (s[a] || 0) ? b : a);
    const c = cfg[ndviCls];
    const name = ndviCls.charAt(0).toUpperCase() + ndviCls.slice(1);
    const bar = (label, key, color, range) => `
        <div class="prob-bar" title="NDVI ${range}">
            <span class="prob-label">${label}:</span>
            <div class="prob-fill" style="width:${((s[key] || 0) * 100).toFixed(1)}%;background:${color};"></div>
            <span class="prob-value" style="color:${color};">${((s[key] || 0) * 100).toFixed(1)}%</span>
        </div>`;
    return `
            <div class="class-probabilities ndvi-result">
                <h5><i class="fas fa-leaf"></i> ${title}:
                    <span style="color:${c.color};">${name}</span>
                    <span style="font-weight:400;color:var(--text-muted);">· average ${mean != null ? mean.toFixed(3) : '--'}</span>
                    ${badge ? `<span class="ndvi-badge ${badge}">${badge}</span>` : ''}
                    ${decides ? '<span class="ndvi-badge decides" title="This NDVI is the one used in the result">used</span>' : ''}</h5>
                <div class="prob-bars">
                    ${bar('Healthy', 'healthy', '#1D9E75', `≥ ${th.moderate_max}`)}
                    ${bar('Moderate', 'moderate', '#EF9F27', `${th.poor_max} – ${th.moderate_max}`)}
                    ${bar('Poor', 'poor', '#E24B4A', `< ${th.poor_max}`)}
                </div>
                <div style="margin-top:6px;font-size:11.5px;color:var(--text-muted);">Share of the area in each NDVI class (Table 7).</div>
            </div>`;
}

function partLine(p) {
    p = p || {};
    const v = k => Math.round((p[k] || 0) * 100);
    return `Healthy ${v('healthy')}% · Moderate ${v('moderate')}% · Poor ${v('poor')}%`;
}

// ─── Time ─────────────────────────────────────────────────────────────────────
function updateTime() {
    const now = new Date();
    const el = document.getElementById('current-time');
    if (el) el.textContent =
        now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
        ' | ' + now.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
}
function updateLastUpdateTime() {
    const el = document.getElementById('last-update-time');
    if (el) el.textContent = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
}

// ─── Notifications ────────────────────────────────────────────────────────────
function showNotification(message, type = 'info') {
    document.querySelector('.notif-toast')?.remove();
    const note = document.createElement('div');
    note.className = 'notif-toast';
    const colors = { success: '#1D9E75', error: '#E24B4A', warning: '#EF9F27', info: '#1D9E75' };
    note.style.cssText = `position:fixed;top:20px;right:20px;padding:14px 22px;border-radius:8px;color:white;font-weight:500;z-index:99999;box-shadow:0 4px 12px rgba(0,0,0,0.2);font-family:'Inter',sans-serif;font-size:13px;background:${colors[type]||colors.info};`;
    note.textContent = message;
    document.body.appendChild(note);
    setTimeout(() => { if (note.parentNode) note.remove(); }, 3000);
}

// ─── Drone captures (Raspberry Pi) ───────────────────────────────────────────
function openDroneModal() {
    document.getElementById('drone-modal').style.display = 'flex';
    loadDroneLists();
}

function closeDroneModal() {
    const m = document.getElementById('drone-modal');
    if (m) m.style.display = 'none';
}

async function loadDroneLists() {
    const piBox = document.getElementById('drone-pi-list');
    const localBox = document.getElementById('drone-local-list');
    piBox.innerHTML = '<p class="drone-note">Looking for the drone...</p>';
    localBox.innerHTML = '<p class="drone-note">Loading...</p>';

    // Flights already on this laptop
    try {
        const flights = await (await fetch(`${API}/drone/captures`)).json();
        localBox.innerHTML = flights.length ? flights.map(f => `
            <div class="drone-flight">
                <div class="drone-flight-head"><b>${escapeText(f.flight)}${f.spot ? ` · spot ${escapeText(f.spot)}` : ''}</b><span>${f.pairs.length} pairs</span></div>
                <div class="drone-pairs">${f.pairs.map(p => `
                    <button class="drone-pair${p.id === f.auto_pair ? ' chosen' : ''}" data-flight="${escapeText(f.flight)}" data-pair="${p.id}" data-rgb="${escapeText(p.rgb)}"
                            title="Pair ${p.id} · ${escapeText(p.time)} · RGB photo (CNN) + NoIR photo (NDVI)${p.id === f.auto_pair ? ' · chosen automatically (sharpest)' : ''}">
                        <div class="pair-half">
                            <img loading="lazy" src="${API}/captures/${encodeURIComponent(f.flight)}/${encodeURIComponent(p.rgb)}" alt="Pair ${p.id} RGB photo">
                            <em>RGB</em>
                        </div>
                        <div class="pair-half">
                            <img loading="lazy" src="${API}/captures/${encodeURIComponent(f.flight)}/${encodeURIComponent(p.noir)}" alt="Pair ${p.id} NoIR photo">
                            <em>NoIR</em>
                        </div>
                        <span>${String(p.id).padStart(4, '0')}</span>
                        ${p.id === f.auto_pair ? '<strong class="pair-chosen"><i class="fas fa-check"></i> Used</strong>' : ''}
                    </button>`).join('')}
                </div>
            </div>`).join('') : '<p class="drone-note">No flights imported yet.</p>';
        localBox.querySelectorAll('.drone-pair').forEach(b =>
            b.addEventListener('click', () => selectCapture(b.dataset.flight, +b.dataset.pair, b.dataset.rgb)));
    } catch {
        localBox.innerHTML = '<p class="drone-note">Could not reach app.py on port 5000.</p>';
    }

    // Flights on the Pi (only when it is on the same Wi-Fi)
    try {
        const res = await fetch(`${API}/drone/flights`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
        piBox.innerHTML = data.length ? data.map(f => `
            <div class="drone-row">
                <div><b>${escapeText(f.flight)}${f.spot ? ` · spot ${escapeText(f.spot)}` : ''}</b><span>${f.pairs} pairs${f.started ? ' · ' + escapeText(f.started.replace('T', ' ')) : ''}</span></div>
                <button class="action-btn drone-import" data-flight="${escapeText(f.flight)}">
                    ${f.imported ? '<i class="fas fa-rotate"></i> Re-sync' : '<i class="fas fa-download"></i> Import'}
                </button>
            </div>`).join('') : '<p class="drone-note">The drone has no flights yet.</p>';
        piBox.querySelectorAll('.drone-import').forEach(b => b.addEventListener('click', () => importFlight(b)));
    } catch (err) {
        piBox.innerHTML = `<p class="drone-note"><i class="fas fa-wifi"></i> ${escapeText(err.message || 'Drone not reachable.')}</p>`;
    }
}

async function importFlight(btn) {
    const flight = btn.dataset.flight;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Importing...';
    try {
        const res = await fetch(`${API}/drone/import`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ flight })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
        showNotification(`Imported ${data.pairs} photo pairs from ${flight}.`, 'success');
        loadDroneLists();
    } catch (err) {
        showNotification(err.message || 'Import failed.', 'error');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-download"></i> Import';
    }
}

function selectCapture(flight, pair, rgbName) {
    closeDroneModal();
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
        uploadedImage = img;
        currentCapture = { flight, pair }; resetViews();
        drawUploadPreview();
        document.getElementById('upload-overlay-text').style.display = 'none';
        document.getElementById('upload-status').textContent =
            `Drone pair ${String(pair).padStart(4, '0')} (${flight}) — analyzing RGB + NoIR...`;
        analyzeImage({ capture: { flight, pair } });
    };
    img.onerror = () => showNotification('Could not load the drone photo from app.py.', 'error');
    img.src = `${API}/captures/${encodeURIComponent(flight)}/${encodeURIComponent(rgbName)}`;
}

function escapeText(str) {
    const d = document.createElement('div');
    d.textContent = str == null ? '' : String(str);
    return d.innerHTML.replace(/"/g, '&quot;');
}
