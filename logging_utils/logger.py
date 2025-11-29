import logging
import os
import json
import requests
import threading
from datetime import datetime
from config import load_config, APP_NAME, INCIDENTS_FILE, LOG_FILE_PATH

_logger = None

class SplunkHECHandler(logging.Handler):
    """
    Sends logs to Splunk HTTP Event Collector in real-time.
    """
    def __init__(self, url, token):
        super().__init__()
        self.url = url
        self.token = token
        self.verify_ssl = False

        # Fix URL if user forgot the endpoint
        if "collector" not in self.url:
            self.url = f"{self.url}/services/collector/event"

    def emit(self, record):
        # Send INFO, WARNING, ERROR, CRITICAL
        if record.levelno < logging.INFO:
            return

        try:
            msg_data = record.getMessage()
            # Try to parse if it's already JSON string
            try:
                if msg_data.startswith("{"):
                    msg_data = json.loads(msg_data)
            except:
                pass

            payload = {
                "time": record.created,
                "host": os.getenv('COMPUTERNAME', 'DETON8R_HOST'),
                "source": "deton8r_app",
                "sourcetype": "_json",
                "event": {
                    "severity": record.levelname,
                    "message": msg_data,
                    "module": record.module,
                    "app": APP_NAME
                }
            }

            threading.Thread(target=self._send_async, args=(payload,), daemon=True).start()
        except Exception:
            self.handleError(record)

    def _send_async(self, payload):
        headers = {"Authorization": f"Splunk {self.token}"}
        try:
            requests.post(self.url, json=payload, headers=headers, verify=self.verify_ssl, timeout=5)
        except Exception as e:
            print(f"(!) Splunk Send Failed: {e}")

class TkinterReadonlyHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        try:
            msg = self.format(record)
            # Web interface doesn't use this, but kept for compatibility
            if hasattr(self.text_widget, 'after'):
                self.text_widget.after(0, self._append, msg)
        except Exception:
            self.handleError(record)

    def _append(self, msg: str):
        try:
            self.text_widget.configure(state='normal')
            self.text_widget.insert("end", msg + "\n")
            self.text_widget.see("end")
            self.text_widget.configure(state='disabled')
        except:
            pass

def _check_splunk_handler(logger):
    """
    DYNAMIC RELOAD: Checks if Splunk config exists but handler is missing.
    This fixes the issue where saving config didn't update the running app.
    """
    has_splunk = any(isinstance(h, SplunkHECHandler) for h in logger.handlers)

    if not has_splunk:
        cfg = load_config()
        if cfg.get("splunk_url") and cfg.get("splunk_token"):
            print("[*] Hot-Loading Splunk Handler...")
            splunk_h = SplunkHECHandler(cfg["splunk_url"], cfg["splunk_token"])
            logger.addHandler(splunk_h)
            logger.info("Splunk Connection Established (Hot-Loaded)")

def get_logger():
    global _logger
    if _logger is not None:
        # Check for config changes every time we get the logger
        _check_splunk_handler(_logger)
        return _logger

    cfg = load_config()
    os.makedirs(cfg["logs_dir"], exist_ok=True)

    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # File Handler
    fh = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"))
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)

    # Initial Splunk Check
    _check_splunk_handler(logger)

    _logger = logger
    return logger

def attach_ui_handler(text_widget):
    logger = get_logger()
    # Remove old UI handlers to avoid duplicates
    for h in logger.handlers:
        if isinstance(h, TkinterReadonlyHandler):
            logger.removeHandler(h)

    handler = TkinterReadonlyHandler(text_widget)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)

def log_incident(event_type: str, **kwargs):
    """
    Logs a structured incident. Triggers Splunk auto-discovery.
    """
    # 1. Ensure Splunk is attached if config exists
    logger = get_logger()

    ts = datetime.utcnow().isoformat() + "Z"

    # 2. Save to local JSON file
    record = {"ts": ts, "app": APP_NAME, "event": event_type, **kwargs}
    try:
        with open(INCIDENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"Log Error: {e}")

    # 3. Send to Logger (Triggers SplunkHECHandler)
    logger.warning(json.dumps({
        "alert_type": event_type,
        "details": kwargs
    }))