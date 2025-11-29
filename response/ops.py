import os
import shutil
import json
import glob
import requests
import threading
from datetime import datetime
from config import load_config, INCIDENTS_FILE
from logging_utils.logger import get_logger, log_incident

logger = get_logger()

def _manual_splunk_push(event_type, severity="WARNING", **kwargs):
    """
    Fail-safe mechanism to ensure critical alerts reach Splunk
    even if the main Logger hasn't refreshed its config yet.
    Allows specifying severity level.
    """
    def _send():
        try:
            cfg = load_config()
            url = cfg.get("splunk_url")
            token = cfg.get("splunk_token")

            if not url or not token: return

            if "collector" not in url:
                url = f"{url}/services/collector/event"

            headers = {"Authorization": f"Splunk {token}"}
            payload = {
                "time": datetime.utcnow().timestamp(),
                "sourcetype": "_json",
                "event": {
                    "app": "Detonat8r",
                    "severity": severity,
                    "event_type": event_type,
                    "details": kwargs
                }
            }
            # Send with short timeout to not block anything
            requests.post(url, json=payload, headers=headers, verify=False, timeout=3)
            print(f"[*] Fail-Safe Alert Sent to Splunk: {event_type} [{severity}]")
        except Exception as e:
            print(f"[!] Fail-Safe Splunk Error: {e}")

    # Run in background thread
    threading.Thread(target=_send, daemon=True).start()

def create_backup(custom_name=None) -> str:
    """
    Creates a full folder copy (snapshot) of the work_dir.
    """
    cfg = load_config()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = custom_name if custom_name else f"backup_{timestamp}"

    backup_path = os.path.join(cfg["backup_dir"], name)
    target_dir = cfg["work_dir"]

    # Safety check: Don't backup if target is empty/missing
    if not os.path.exists(target_dir):
        logger.error(f"Cannot backup: Target dir {target_dir} missing.")
        return None

    try:
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)

        shutil.copytree(target_dir, backup_path)
        logger.info(f"Snapshot created successfully: {name}")

        # Primary Logging
        log_incident("BACKUP_CREATED", path=backup_path, snapshot_name=name)
        # Fail-Safe Logging
        _manual_splunk_push("BACKUP_CREATED", severity="INFO", path=backup_path, snapshot_name=name)

        return backup_path
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return None

def list_backups():
    """
    Returns list of tuples: (folder_name, created_timestamp_string)
    Sorted by newest first.
    """
    cfg = load_config()
    backups = []
    if not os.path.exists(cfg["backup_dir"]): return []

    try:
        for entry in os.scandir(cfg["backup_dir"]):
            if entry.is_dir():
                ts = datetime.fromtimestamp(entry.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                backups.append((entry.name, ts))
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return []

    return sorted(backups, key=lambda x: x[1], reverse=True)

def restore_backup(backup_name):
    """
    Wipes the current work_dir and restores contents from the backup snapshot.
    """
    cfg = load_config()
    src = os.path.join(cfg["backup_dir"], backup_name)
    dst = cfg["work_dir"]

    if not os.path.exists(src):
        logger.error(f"Restore failed: Snapshot {backup_name} not found.")
        return False

    logger.info(f"Initiating Restore Procedure from {backup_name}...")

    try:
        # 1. Wipe current workdir (The "Infected" state)
        if os.path.exists(dst):
            for item in os.listdir(dst):
                # Don't delete lockfiles or hidden config if they exist
                if item.startswith("."): continue

                s = os.path.join(dst, item)
                if os.path.isdir(s):
                    shutil.rmtree(s)
                else:
                    os.unlink(s)
        else:
            os.makedirs(dst)

        # 2. Copy backup contents to workdir
        shutil.copytree(src, dst, dirs_exist_ok=True)

        logger.info("System Restoration Complete. Integrity Verified.")

        # Primary Logging
        log_incident("RESTORE_SUCCESS", source_snapshot=backup_name)
        # Fail-Safe Logging
        _manual_splunk_push("RESTORE_SUCCESS", severity="WARNING", source_snapshot=backup_name)

        return True
    except Exception as e:
        logger.error(f"CRITICAL RESTORE FAILURE: {e}")
        return False

def simulate_isolation():
    """
    Simulates network isolation by creating a lock file.
    """
    cfg = load_config()
    flag_file = os.path.join(cfg["work_dir"], "NETWORK_ISOLATED.lock")
    try:
        with open(flag_file, "w") as f:
            f.write("HOST ISOLATED BY DETON8R SECURITY PROTOCOL\n")
            f.write(f"Timestamp: {datetime.now()}")
        logger.warning("Host Network Interface Disabled (Simulated via Lockfile)")

        # Primary Logging
        log_incident("HOST_ISOLATION", method="Simulation", status="Success")
        # Fail-Safe Logging
        _manual_splunk_push("HOST_ISOLATION", severity="CRITICAL", method="Simulation", status="Success")

    except Exception as e:
        logger.error(f"Isolation failed: {e}")

def generate_report():
    """
    Generates a Markdown report of all incidents.
    """
    cfg = load_config()
    report_name = f"Incident_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = os.path.join(cfg["logs_dir"], report_name)

    try:
        with open(report_path, "w") as r:
            r.write(f"# DETON8R Incident Report\n")
            r.write(f"**Generated:** {datetime.now()}\n\n")
            r.write("## Executive Summary\n")
            r.write("This document details the timeline of the recent security event detected by the Detonat8r platform.\n\n")
            r.write("## Event Timeline\n")

            if os.path.exists(INCIDENTS_FILE):
                with open(INCIDENTS_FILE, "r") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            # Format for readability
                            r.write(f"- **{data['ts']}** | **{data['event']}**\n")
                            # Add details if they exist
                            details = {k:v for k,v in data.items() if k not in ['ts', 'event', 'app']}
                            if details:
                                r.write(f"    - *Details:* {details}\n")
                        except: continue
            else:
                r.write("_No incidents recorded in the log file._\n")

        logger.info(f"Report generated successfully: {report_path}")
        return report_path
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return None