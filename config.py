import os
import json

# --- Constants ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "deton8r_config.json")

DEFAULT_WORKDIR = os.path.join(BASE_DIR, "lab_data", "workdir")
DEFAULT_BACKUP = os.path.join(BASE_DIR, "lab_data", "backups")
DEFAULT_LOGS = os.path.join(BASE_DIR, "logs")

for d in [DEFAULT_WORKDIR, DEFAULT_BACKUP, DEFAULT_LOGS]:
    os.makedirs(d, exist_ok=True)

APP_NAME = "Detonat8r"
INCIDENTS_FILE = os.path.join(DEFAULT_LOGS, "incidents.jsonl")
LOG_FILE_PATH = os.path.join(DEFAULT_LOGS, "detonat8r.log")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return {
                    "work_dir": data.get("work_dir", DEFAULT_WORKDIR),
                    "backup_dir": data.get("backup_dir", DEFAULT_BACKUP),
                    "logs_dir": data.get("logs_dir", DEFAULT_LOGS),
                    "poll_interval": data.get("poll_interval", 2),
                    "change_threshold": data.get("change_threshold", 3),
                    # Splunk Settings
                    "splunk_url": data.get("splunk_url", ""),
                    "splunk_token": data.get("splunk_token", "")
                }
        except Exception:
            pass

    return {
        "work_dir": DEFAULT_WORKDIR,
        "backup_dir": DEFAULT_BACKUP,
        "logs_dir": DEFAULT_LOGS,
        "poll_interval": 2,
        "change_threshold": 3,
        "splunk_url": "",
        "splunk_token": ""
    }

def save_config(work_dir, backup_dir, splunk_url="", splunk_token=""):
    cfg = load_config()
    cfg["work_dir"] = os.path.abspath(work_dir)
    cfg["backup_dir"] = os.path.abspath(backup_dir)
    cfg["splunk_url"] = splunk_url
    cfg["splunk_token"] = splunk_token

    os.makedirs(cfg["work_dir"], exist_ok=True)
    os.makedirs(cfg["backup_dir"], exist_ok=True)

    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)
    return cfg