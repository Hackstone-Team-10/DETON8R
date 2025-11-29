import os
import sys
import threading
import time
import json
import zipfile
import shutil
import requests
from flask import Flask, render_template, jsonify, request

# Ensure we can import our local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import load_config, save_config
from logging_utils.logger import get_logger, log_incident
from detector.file_detector import FileChangeDetector
from response.ops import create_backup, list_backups, restore_backup, simulate_isolation, generate_report

app = Flask(__name__)
logger = get_logger()

# Global State
detector_thread = None
system_status = "IDLE"

# --- API ENDPOINTS ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    global system_status
    cfg = load_config()
    is_monitoring = detector_thread is not None and detector_thread.is_alive()

    if is_monitoring and "CRITICAL" not in system_status:
        system_status = "MONITORING"
    elif not is_monitoring and system_status == "MONITORING":
        system_status = "IDLE"

    return jsonify({
        "status": system_status,
        "target_dir": cfg["work_dir"],
        "monitoring": is_monitoring
    })

@app.route('/api/logs')
def get_logs():
    cfg = load_config()
    log_path = os.path.join(cfg["logs_dir"], "detonat8r.log")
    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                logs = f.readlines()[-50:]
        except:
            pass
    return jsonify(logs)

@app.route('/api/detector/start', methods=['POST'])
def start_detector():
    global detector_thread, system_status
    if detector_thread and detector_thread.is_alive():
        return jsonify({"message": "Already running"}), 200

    def alert_callback(count):
        global system_status
        system_status = f"CRITICAL ({count} FILES)"
        logger.warning(f"WEB ALERT: {count} files changed.")

    detector_thread = FileChangeDetector(alert_callback)
    detector_thread.start()
    system_status = "MONITORING"
    logger.info("Detector started via Web UI.")
    return jsonify({"message": "Started"}), 200

@app.route('/api/detector/stop', methods=['POST'])
def stop_detector():
    global detector_thread, system_status
    if detector_thread:
        detector_thread.stop()
        detector_thread = None
    system_status = "IDLE"
    logger.info("Detector stopped via Web UI.")
    return jsonify({"message": "Stopped"}), 200

@app.route('/api/response/isolate', methods=['POST'])
def isolate():
    global system_status
    simulate_isolation()
    system_status = "ISOLATED"
    return jsonify({"message": "Host Isolated"}), 200

# --- ADVANCED BACKUP ENDPOINTS ---

@app.route('/api/backups', methods=['GET'])
def backups():
    return jsonify(list_backups())

@app.route('/api/backups/create', methods=['POST'])
def backup_create():
    path = create_backup()
    return jsonify({"success": bool(path), "path": path})

@app.route('/api/backups/<name>', methods=['DELETE'])
def backup_delete(name):
    cfg = load_config()
    path = os.path.join(cfg["backup_dir"], name)

    # Try deleting as folder
    if os.path.exists(path) and os.path.isdir(path):
        shutil.rmtree(path)
        logger.info(f"Backup folder deleted: {name}")
        return jsonify({"success": True})

    # Try deleting as zip if folder not found
    zip_path = path + ".zip"
    if os.path.exists(zip_path):
        os.remove(zip_path)
        logger.info(f"Backup zip deleted: {name}")
        return jsonify({"success": True})

    return jsonify({"success": False, "error": "Not found"}), 404

@app.route('/api/backups/files', methods=['GET'])
def backup_files():
    name = request.args.get('name')
    cfg = load_config()
    path = os.path.join(cfg["backup_dir"], name)
    file_list = []

    try:
        # Case 1: Backup is a Directory
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, path)
                    file_list.append(rel_path)

        # Case 2: Backup is a Zip File (fallback check)
        elif os.path.exists(path + ".zip"):
            with zipfile.ZipFile(path + ".zip", 'r') as z:
                file_list = z.namelist()

        # Case 3: Path points directly to a zip without extension in name var
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, 'r') as z:
                file_list = z.namelist()

    except Exception as e:
        logger.error(f"Error reading backup {name}: {e}")
        return jsonify([])

    return jsonify(file_list)

@app.route('/api/backups/restore', methods=['POST'])
def backup_restore():
    data = request.json
    name = data.get("name")
    if restore_backup(name):
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route('/api/backups/restore-selective', methods=['POST'])
def restore_selective():
    data = request.json
    name = data.get("name")
    files_to_restore = data.get("files", [])

    cfg = load_config()
    src_base = os.path.join(cfg["backup_dir"], name)
    dst_base = cfg["work_dir"]

    restored_count = 0
    try:
        # Handle Folder-based backups
        if os.path.isdir(src_base):
            for rel_path in files_to_restore:
                src = os.path.join(src_base, rel_path)
                dst = os.path.join(dst_base, rel_path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                    restored_count += 1
        # Handle ZIP-based backups
        elif os.path.exists(src_base + ".zip") or zipfile.is_zipfile(src_base):
            zip_path = src_base if zipfile.is_zipfile(src_base) else src_base + ".zip"
            with zipfile.ZipFile(zip_path, 'r') as z:
                for rel_path in files_to_restore:
                    z.extract(rel_path, dst_base)
                    restored_count += 1

        logger.info(f"Selective restore: {restored_count} files restored from {name}")
        return jsonify({"success": True, "count": restored_count})
    except Exception as e:
        logger.error(f"Selective restore failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# --- CONFIG & SPLUNK ---

@app.route('/api/config', methods=['GET', 'POST'])
def config_api():
    if request.method == 'POST':
        data = request.json
        save_config(
            data.get('work_dir'),
            data.get('backup_dir'),
            data.get('splunk_url'),
            data.get('splunk_token')
        )

        # --- NEW: FORCE LOGGER REFRESH ---
        # This ensures the new token is used immediately for subsequent alerts
        get_logger().info("Configuration Saved. Refreshing Splunk Connection...")

        return jsonify({"success": True})
    return jsonify(load_config())

@app.route('/api/test-alert', methods=['POST'])
def test_alert():
    """
    Synchronously tests the Splunk connection and returns the EXACT error.
    """
    cfg = load_config()
    url = cfg.get("splunk_url")
    token = cfg.get("splunk_token")

    if not url or not token:
        return jsonify({"success": False, "error": "Missing URL or Token in Config"})

    headers = {"Authorization": f"Splunk {token}"}
    payload = {
        "event": {
            "message": "DETON8R Connectivity Check",
            "status": "TEST_OK"
        }
    }

    try:
        endpoint = url if "collector" in url else f"{url}/services/collector/event"
        resp = requests.post(endpoint, json=payload, headers=headers, verify=False, timeout=5)

        if resp.status_code == 200:
            log_incident("SPLUNK_TEST_SUCCESS", status="Verified")
            return jsonify({"success": True, "splunk_response": resp.json()})
        else:
            return jsonify({"success": False, "error": f"Splunk returned {resp.status_code}: {resp.text}"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    print("Starting DETON8R Web Server on http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)