# DETON8R | Advanced Ransomware Defense Grid

DETON8R is an automated "Purple Team" orchestration platform designed to detect, isolate, and recover from ransomware attacks in real-time. Built for SOC analysts and cybersecurity training, it bridges the gap between detection and response by providing a unified console for file integrity monitoring, hard network isolation, and granular system recovery.

## 🚀 Key Features

### 🛡️ Detection & Monitoring

* Heuristic Sensor: Real-time file integrity monitoring using SHA-256 hashing.

* Velocity Detection: Automatically triggers critical alerts if file modification rates exceed a safe threshold (e.g., >3 files/sec).

* Live Threat Visualization: Real-time graph displaying file activity spikes on the dashboard.

### ⚡ Incident Response

* Hard Isolation: Executes OS-level firewall commands (netsh on Windows, iptables on Linux) to physically block all outbound network traffic, cutting off C2 communication.

* Network Rejoin: One-click restoration of network connectivity after the threat is neutralized.

### 💾 Resilience & Recovery

* Granular Auto-Backups: Advanced scheduler allowing backups to be set by Month, Day, Hour, Minute, and Second.

* Selective Restore: View the contents of any snapshot and restore specific files without rolling back the entire system.

* Full Rollback: Instant restoration of the entire monitored directory to a clean state.

### 📊 Enterprise Logging (Splunk)

* Real-Time HEC Integration: Pushes structured JSON logs (INFO, WARNING, CRITICAL) directly to Splunk via HTTP Event Collector.

* Fail-Safe Logging: Ensures critical alerts (Backup, Restore, Isolation) are sent even if the main logger thread is busy.

* Self-Healing: Automatically reloads Splunk configuration without requiring an application restart.

### 🛠️ Installation & Setup

#### Prerequisites

Python 3.8+

Administrator/Root privileges (Required for Firewall Isolation)

#### 1. Clone & Install
```
git clone https://github.com/Hackstone-Team-10/DETON8R.git
cd DETON8R
pip install -r requirements.txt
```

#### 2. Run the Application

Note: You must run the application as Administrator (Windows) or sudo (Linux) for the Network Isolation features to work.

# Windows (Run PowerShell/CMD as Admin)
```
python app.py
```
# Linux
```
sudo python3 app.py
```

#### 3. Access the Dashboard

Open your web browser and navigate to:
http://localhost:5000

### 📖 Usage Guide

#### 1. Configuration (First Step)

* Navigate to the ⚙️ Configuration tab:

* Monitor Directory: Select the folder you want to protect (The "Victim").

* Backup Directory: Select where snapshots should be stored.

* Splunk Integration:

  * HEC URL: e.g., https://192.168.1.10:8088 (Use http if SSL is disabled).

  * HEC Token: Your Splunk HTTP Event Collector token.

  * Click Save Configuration.

#### 2. Dashboard Operations

* Start Sensor: Activates the file monitoring engine.

* Red Team Intel: Copy the target path to your clipboard to configure your attack script (e.g., PSRansom.ps1).

* Isolate Host: Immediately blocks all network traffic. Use this when you see a threat spike.

#### 3. Recovery Center

* Snapshot Now: Manually create a backup point.

* Auto-Backup: Toggle the switch and set the interval (M/D/H/M/S) for automated protection.

* View/Restore: Click "VIEW" on any backup to see files inside and perform a Selective Restore.

### 📂 Project Structure
```
DETON8R/
│
├── detector/
│   ├── __init__.py
│   └── file_detector.py      # Background Thread for File Hashing & Velocity Checks
│
├── logging_utils/
│   ├── __init__.py
│   └── logger.py             # Splunk HEC Handler & Thread-Safe Logging
│
├── response/
│   ├── __init__.py
│   └── ops.py                # Logic for Backup, Restore, and Firewall Isolation
│
├── templates/
│   └── index.html            # The Cyber-Dark Web Interface (HTML/JS/CSS)
│
├── lab_data/                 # Storage for Workdir and Backups
│   ├── backups/              # Encrypted/Clean Snapshots
│   └── workdir/              # The "Victim" folder for simulation
│
├── logs/                     # Local log storage
│   ├── detonat8r.log         # Application system logs
│   └── incidents.jsonl       # Structured incident history
│
├── app.py                    # Main Flask Server & API Endpoints
├── config.py                 # Configuration Loader/Saver Logic
├── deton8r_config.json       # User settings (Excluded from Repo)
└── requirements.txt          # Python dependencies
```

### ⚠️ Disclaimer

* DETON8R is a security tool designed for educational and simulation purposes only.

* The "Isolate Host" function modifies system firewall rules. Use with caution on production machines.

* Always ensure you have permission to monitor files and modify network settings on the host machine.
