#!/usr/bin/env python3
"""
Web-based UI for Spectacle Order Automation
Runs as a local web server - open in your browser.
"""

import os
import sys
import threading
from typing import Dict, Optional
from flask import Flask, render_template_string, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_parser import SpectacleOrderParser
from eyefinity_automation import EyefinityAutomation

app = Flask(__name__)
app.config['SECRET_KEY'] = 'spectacle-order-app-secret'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

automation: Optional[EyefinityAutomation] = None
extracted_data: Dict[str, str] = {}
login_status = {"state": "idle", "message": "Not connected"}

HTML_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spectacle Order Automation</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; padding: 20px;
        }
        .container {
            max-width: 1200px; margin: 0 auto; background: white;
            border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white; padding: 24px 32px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .header h1 { font-size: 24px; font-weight: 600; }
        .header span { opacity: 0.8; font-size: 14px; }
        .content { padding: 32px; }
        .step {
            background: #f8f9fa; border-radius: 12px; padding: 24px;
            margin-bottom: 24px; border: 2px solid transparent;
        }
        .step.completed { border-color: #28a745; }
        .step-title {
            font-size: 18px; font-weight: 600; color: #333;
            margin-bottom: 16px; display: flex; align-items: center; gap: 10px;
        }
        .step-title .badge {
            background: #667eea; color: white; width: 28px; height: 28px;
            border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-size: 14px; font-weight: 700;
        }
        .form-group { margin-bottom: 16px; }
        input[type="file"] {
            width: 100%; padding: 10px; border: 2px solid #e0e0e0;
            border-radius: 8px; font-size: 14px; background: white;
        }
        textarea {
            width: 100%; padding: 10px 14px; border: 2px solid #e0e0e0;
            border-radius: 8px; font-size: 14px; resize: vertical;
            min-height: 80px; font-family: 'Courier New', monospace;
        }
        .btn {
            padding: 10px 24px; border: none; border-radius: 8px;
            font-size: 14px; font-weight: 600; cursor: pointer;
            display: inline-flex; align-items: center; gap: 8px;
        }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-primary { background: #667eea; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-warning { background: #ffc107; color: #333; }
        .btn-outline { background: transparent; border: 2px solid #667eea; color: #667eea; }
        .btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin: 12px 0; }
        .status-bar {
            padding: 12px 24px; border-radius: 8px; font-weight: 500; margin-bottom: 16px;
        }
        .status-bar.info { background: #cce5ff; color: #004085; border: 1px solid #b8daff; }
        .status-bar.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status-bar.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .status-bar.warning { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
        .log-box {
            background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 8px;
            font-family: 'Courier New', monospace; font-size: 12px;
            height: 200px; overflow-y: auto; white-space: pre-wrap; line-height: 1.5;
        }
        .log-box .time { color: #6c757d; }
        .log-box .ok { color: #28a745; }
        .log-box .err { color: #dc3545; }
        .log-box .warn { color: #ffc107; }
        .hidden { display: none !important; }
        .filename { font-size: 13px; color: #666; margin-top: 8px; }
        .field-section { margin-bottom: 20px; }
        .field-section h3 {
            font-size: 14px; font-weight: 600; color: #667eea;
            margin-bottom: 10px; padding-bottom: 6px; border-bottom: 2px solid #e8e8e8;
        }
        .field-row { display: flex; margin-bottom: 8px; align-items: center; }
        .field-row label { width: 140px; font-size: 13px; color: #666; flex-shrink: 0; }
        .field-row input {
            flex: 1; padding: 6px 10px; border: 1px solid #ddd;
            border-radius: 6px; font-size: 13px;
        }
        @media (max-width: 768px) {
            .content { padding: 16px; }
        }
        .spinner { display: inline-block; width: 16px; height: 16px;
            border: 2px solid rgba(255,255,255,0.3); border-radius: 50%;
            border-top-color: white; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>👓 Spectacle Order Automation</h1>
        <span>VSP PDF → Eyefinity</span>
    </div>
    <div class="content">
        <div id="status" class="status-bar info">Select a PDF to begin</div>

        <!-- Step 1 -->
        <div id="step1" class="step">
            <div class="step-title"><span class="badge">1</span> Select Spectacle Order PDF</div>
            <div class="form-group">
                <input type="file" id="pdfInput" accept=".pdf">
            </div>
            <div id="fileName" class="filename"></div>
            <div class="btn-group">
                <button class="btn btn-primary" id="parseBtn" onclick="parsePDF()">🔍 Parse PDF</button>
            </div>
        </div>

        <!-- Step 2 -->
        <div id="step2" class="step hidden">
            <div class="step-title"><span class="badge">2</span> Review Extracted Data</div>
            <div id="parseStatus"></div>
            <div class="btn-group">
                <button class="btn btn-outline" onclick="showTab('formatted')">📄 Formatted View</button>
                <button class="btn btn-outline" onclick="showTab('fields')">✏️ Edit Fields</button>
            </div>
            <div id="tabFormatted">
                <textarea id="formattedText" readonly style="min-height:300px;background:#1e1e1e;color:#d4d4d4;border:none;padding:16px;border-radius:8px;"></textarea>
            </div>
            <div id="tabFields" class="hidden">
                <div id="fieldEditor"></div>
            </div>
        </div>

        <!-- Step 3 -->
        <div id="step3" class="step hidden">
            <div class="step-title"><span class="badge">3</span> Eyefinity Automation</div>
            <div id="autoStatus" class="status-bar info">Not connected</div>
            <div class="btn-group">
                <button class="btn btn-primary" id="loginBtn" onclick="login()">🔑 Login to Eyefinity</button>
                <button class="btn btn-success" id="populateBtn" disabled onclick="populate()">📝 Populate Form</button>
                <button class="btn btn-warning" id="submitBtn" disabled onclick="submitOrder()">✅ Submit Order</button>
                <button class="btn btn-danger" id="closeBtn" disabled onclick="closeBrowser()">❌ Close Browser</button>
            </div>
        </div>

        <!-- Log -->
        <div style="margin-top:24px;">
            <div class="step-title" style="margin-bottom:8px;"><span>📋 Activity Log</span></div>
            <div class="log-box" id="logBox">[System] Ready. Select a PDF file and click Parse PDF.<br></div>
        </div>
    </div>
</div>

<script>
// ===== File selection - simpler approach =====
document.getElementById('pdfInput').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (!file) return;
    document.getElementById('fileName').textContent = '📄 ' + file.name + ' (' + (file.size/1024).toFixed(1) + ' KB)';
    document.getElementById('parseBtn').disabled = false;
    setStatus('PDF selected - click Parse PDF', 'info');
    log('Selected PDF: ' + file.name);
});

function setStatus(msg, type) {
    const s = document.getElementById('status');
    s.textContent = msg;
    s.className = 'status-bar ' + type;
}

function setAutoStatus(msg, type) {
    const s = document.getElementById('autoStatus');
    s.textContent = msg;
    s.className = 'status-bar ' + type;
}

function log(msg, cls) {
    const box = document.getElementById('logBox');
    const now = new Date();
    const t = now.toLocaleTimeString();
    const span = cls ? '<span class="' + cls + '">' : '<span>';
    box.innerHTML += '<span class="time">[' + t + ']</span> ' + span + msg + '</span><br>';
    box.scrollTop = box.scrollHeight;
}

// ===== Parse PDF =====
function parsePDF() {
    const file = document.getElementById('pdfInput').files[0];
    if (!file) { alert('Please select a PDF file first.'); return; }

    const btn = document.getElementById('parseBtn');
    btn.disabled = true;
    btn.innerHTML = '⏳ Parsing...';
    setStatus('Parsing PDF...', 'info');
    log('Parsing PDF...');

    const fd = new FormData();
    fd.append('pdf', file);

    fetch('/parse', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(result => {
        if (result.success) {
            showData(result.data, result.formatted);
            document.getElementById('step2').className = 'step completed';
            document.getElementById('step3').className = 'step';
            setStatus('✓ Extracted ' + Object.keys(result.data).length + ' fields', 'success');
            log('✓ Parsed successfully - ' + Object.keys(result.data).length + ' fields', 'ok');
        } else {
            setStatus('✗ ' + result.error, 'error');
            log('✗ Parse failed: ' + result.error, 'err');
        }
    })
    .catch(err => {
        setStatus('✗ Network error', 'error');
        log('✗ Error: ' + err, 'err');
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '🔍 Parse PDF';
    });
}

function showData(data, formatted) {
    document.getElementById('step2').classList.remove('hidden');
    document.getElementById('formattedText').value = formatted;

    // Build field editor
    const editor = document.getElementById('fieldEditor');
    editor.innerHTML = '';
    const sections = [
        {name:'Patient', fields:[
            ['patient_name','Patient Name'],['patient_dob','DOB'],
            ['doctor_name','Doctor'],['order_date','Order Date'],
            ['vsp_auth','VSP Authorization #']
        ]},
        {name:'Right Eye (OD)', fields:[
            ['od_sph','Sphere'],['od_cyl','Cylinder'],['od_axis','Axis'],['od_add','Add']
        ]},
        {name:'Left Eye (OS)', fields:[
            ['os_sph','Sphere'],['os_cyl','Cylinder'],['os_axis','Axis'],['os_add','Add']
        ]},
        {name:'Pupillary Distance & Seg Height', fields:[
            ['od_pd_distance','OD (R) Dist PD (MPD-D)'],
            ['os_pd_distance','OS (L) Dist PD (MPD-D)'],
            ['pd_distance','Binocular Dist PD'],
            ['pd_near','Binocular Near PD'],
            ['od_seg_height','OD (R) Seg Height (MPD-N)'],
            ['os_seg_height','OS (L) Seg Height (MPD-N)']
        ]},
        {name:'Frame', fields:[
            ['frame_manufacturer','Manufacturer'],['frame_model','Model'],
            ['frame_color','Color'],
            ['frame_bridge','Bridge'],['frame_eye','Eye'],['frame_temple','Temple']
        ]},
        {name:'Lens', fields:[
            ['lens_type','Type'],['lens_material','Material'],['lens_coatings','Coatings'],
            ['lens_tint','Tint Factor'],
            ['lens_photochromic','Photochromic'],['lens_polarized','Polarized'],
            ['lens_scratch_coat','Scratch Coat']
        ]},
        {name:'Other', fields:[
            ['order_number','Order #'],['comments','Comments']
        ]}
    ];
    sections.forEach(s => {
        let hasData = s.fields.some(f => data[f[0]]);
        if (!hasData) return;
        let html = '<div class="field-section"><h3>' + s.name + '</h3>';
        s.fields.forEach(f => {
            let val = data[f[0]] || '';
            html += '<div class="field-row"><label>' + f[1] + '</label>' +
                '<input type="text" data-key="' + f[0] + '" value="' + val.replace(/"/g,'"') + '"></div>';
        });
        html += '</div>';
        editor.innerHTML += html;
    });

    // Add change listeners
    editor.querySelectorAll('input').forEach(inp => {
        inp.addEventListener('change', function() {
            const key = this.getAttribute('data-key');
            data[key] = this.value;
        });
    });

    showTab('formatted');
}

function showTab(name) {
    document.getElementById('tabFormatted').className = name === 'formatted' ? '' : 'hidden';
    document.getElementById('tabFields').className = name === 'fields' ? '' : 'hidden';
}

// ===== Automation =====
function login() {
    const btn = document.getElementById('loginBtn');
    btn.disabled = true;
    btn.innerHTML = '⏳ Logging in...';
    setAutoStatus('Logging in...', 'info');
    log('Starting Eyefinity login...');

    fetch('/login', { method: 'POST' })
    .then(r => r.json())
    .then(result => {
        if (result.success) {
            log('Login started - waiting for browser...', 'warn');
            // Poll for login status
            pollLoginStatus(btn);
        } else {
            setAutoStatus('✗ Login failed', 'error');
            log('✗ Login failed: ' + (result.error || 'Check credentials'), 'err');
            btn.disabled = false; btn.innerHTML = '🔑 Login to Eyefinity';
        }
    })
    .catch(err => {
        setAutoStatus('✗ Error', 'error');
        log('✗ ' + err, 'err');
        btn.disabled = false; btn.innerHTML = '🔑 Login to Eyefinity';
    });
}

function pollLoginStatus(btn) {
    let attempts = 0;
    const maxAttempts = 30; // 30 * 5s = 150 seconds max
    const interval = setInterval(() => {
        attempts++;
        fetch('/status')
        .then(r => r.json())
        .then(status => {
            if (status.logged_in) {
                clearInterval(interval);
                setAutoStatus('✓ Logged in', 'success');
                document.getElementById('populateBtn').disabled = false;
                document.getElementById('closeBtn').disabled = false;
                log('✓ Login successful', 'ok');
                btn.disabled = false; btn.innerHTML = '🔑 Login to Eyefinity';
            } else if (attempts >= maxAttempts) {
                clearInterval(interval);
                setAutoStatus('✗ Login failed - check browser', 'error');
                log('✗ Login failed - check browser window', 'err');
                btn.disabled = false; btn.innerHTML = '🔑 Login to Eyefinity';
            } else {
                setAutoStatus('Waiting for login... (' + attempts + 's)', 'info');
            }
        })
        .catch(() => {
            clearInterval(interval);
            setAutoStatus('✗ Error checking status', 'error');
            btn.disabled = false; btn.innerHTML = '🔑 Login to Eyefinity';
        });
    }, 5000);
}

function getFieldData() {
    const data = {};
    document.querySelectorAll('#fieldEditor input').forEach(inp => {
        const key = inp.getAttribute('data-key');
        if (inp.value.trim()) data[key] = inp.value.trim();
    });
    return data;
}

function populate() {
    const btn = document.getElementById('populateBtn');
    btn.disabled = true;
    btn.innerHTML = '⏳ Populating...';
    log('Populating order form...');

    fetch('/populate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({data: getFieldData()})
    })
    .then(r => r.json())
    .then(result => {
        if (result.success) {
            document.getElementById('submitBtn').disabled = false;
            log('✓ Form populated', 'ok');
        } else {
            log('⚠ Some fields may not have been filled', 'warn');
        }
    })
    .catch(err => log('✗ ' + err, 'err'))
    .finally(() => { btn.disabled = false; btn.innerHTML = '📝 Populate Form'; });
}

function submitOrder() {
    if (!confirm('Submit this order? Verify data first.')) return;
    const btn = document.getElementById('submitBtn');
    btn.disabled = true; btn.innerHTML = '⏳ Submitting...';
    log('Submitting...');
    fetch('/submit', { method: 'POST' })
    .then(r => r.json())
    .then(result => {
        if (result.success) { log('✓ Submitted!', 'ok'); setStatus('Order submitted!', 'success'); }
        else { log('⚠ Could not auto-submit', 'warn'); }
    })
    .catch(err => log('✗ ' + err, 'err'))
    .finally(() => { btn.disabled = false; btn.innerHTML = '✅ Submit Order'; });
}

function closeBrowser() {
    fetch('/close_browser', { method: 'POST' })
    .then(r => r.json())
    .then(() => {
        document.getElementById('populateBtn').disabled = true;
        document.getElementById('submitBtn').disabled = true;
        document.getElementById('closeBtn').disabled = true;
        setAutoStatus('Browser closed', 'info');
        log('Browser closed');
    });
}
</script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/parse', methods=['POST'])
def parse_pdf():
    global extracted_data
    if 'pdf' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        parser = SpectacleOrderParser()
        data = parser.parse(filepath)
        extracted_data = data
        if data:
            return jsonify({'success': True, 'data': data, 'formatted': parser.get_formatted_prescription()})
        else:
            return jsonify({'success': False, 'error': 'No data extracted. Use debug_pdf.py to check the format.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/login', methods=['POST'])
def login():
    global automation
    login_status["state"] = "starting"
    login_status["message"] = "Starting browser..."
    def task():
        global automation
        try:
            if not automation:
                automation = EyefinityAutomation()
            login_status["state"] = "logging_in"
            login_status["message"] = "Browser opened - filling credentials..."
            automation.login()
            if automation.logged_in:
                login_status["state"] = "logged_in"
                login_status["message"] = "Logged in successfully"
            else:
                login_status["state"] = "failed"
                login_status["message"] = "Login failed - check credentials or browser"
        except Exception as e:
            login_status["state"] = "error"
            login_status["message"] = str(e)
            print(f"Login error: {e}")
    # Start login in background thread - don't block
    t = threading.Thread(target=task, daemon=True)
    t.start()
    return jsonify({'success': True, 'message': 'Login started - check status'})


@app.route('/populate', methods=['POST'])
def populate():
    global automation, extracted_data
    if not automation or not automation.logged_in:
        return jsonify({'success': False, 'error': 'Not logged in'})
    try:
        data = request.json.get('data', {}) or extracted_data
        success = automation.populate_order_form(data)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/submit', methods=['POST'])
def submit():
    global automation
    if not automation:
        return jsonify({'success': False, 'error': 'Not connected'})
    try:
        return jsonify({'success': automation.submit_order()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/status')
def get_status():
    global automation
    logged_in = automation is not None and automation.logged_in
    return jsonify({
        'logged_in': logged_in,
        'extracted_fields': len(extracted_data),
        'login_state': login_status.get("state", "idle"),
        'login_message': login_status.get("message", "")
    })


@app.route('/close_browser', methods=['POST'])
def close_browser():
    global automation
    if automation:
        try:
            automation.close()
        except:
            pass
        automation = None
    return jsonify({'success': True})


def main():
    print("=" * 60)
    print("  Spectacle Order Automation")
    print("  VSP PDF → Eyefinity Order Entry")
    print("=" * 60)
    print()
    print("  🌐 Open in your browser:")
    print("     http://127.0.0.1:5000")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=False)


if __name__ == "__main__":
    main()