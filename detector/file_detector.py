import os
import hashlib
import threading
import time
from config import load_config
from logging_utils.logger import get_logger, log_incident

logger = get_logger()

def hash_file(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, FileNotFoundError):
        return None

def snapshot_directory(path):
    result = {}
    if not os.path.exists(path):
        return result

    for root, _, files in os.walk(path):
        for name in files:
            full_path = os.path.join(root, name)
            if "backup" in full_path.lower(): continue
            if name.endswith(".lock"): continue
            if name == "detonat8r.log": continue

            h = hash_file(full_path)
            if h:
                result[full_path] = h
    return result

class FileChangeDetector(threading.Thread):
    def __init__(self, on_alert_callback):
        super().__init__(daemon=True)
        self.on_alert = on_alert_callback
        self.stop_event = threading.Event()

        cfg = load_config()
        self.target_dir = cfg["work_dir"]
        self.threshold = cfg["change_threshold"]
        self.poll_interval = cfg["poll_interval"]
        self.last_state = {}

    def run(self):
        logger.info(f"Detector Service Started. Watching: {self.target_dir}")
        self.last_state = snapshot_directory(self.target_dir)

        while not self.stop_event.is_set():
            time.sleep(self.poll_interval)

            # Dynamic Config Reload
            cfg = load_config()
            if cfg["work_dir"] != self.target_dir:
                self.target_dir = cfg["work_dir"]
                logger.info(f"Retargeting Sensor to: {self.target_dir}")
                self.last_state = snapshot_directory(self.target_dir)
                continue

            current_state = snapshot_directory(self.target_dir)
            changes = 0

            all_files = set(self.last_state.keys()) | set(current_state.keys())

            for f in all_files:
                old_hash = self.last_state.get(f)
                new_hash = current_state.get(f)
                if old_hash != new_hash:
                    changes += 1

            if changes >= self.threshold:
                # THIS IS THE LINE THAT TRIGGERS SPLUNK
                msg = f"HIGH ALERT: Mass modification detected ({changes} files)"
                logger.warning(msg)

                # Send detailed JSON event
                log_incident("MASS_FILE_MODIFICATION", count=changes, target=self.target_dir)

                if self.on_alert:
                    self.on_alert(changes)

            self.last_state = current_state

        logger.info("Detector Service Stopped")

    def stop(self):
        self.stop_event.set()