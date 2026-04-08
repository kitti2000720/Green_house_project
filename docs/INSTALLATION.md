# Greenhouse Automation System - Installation Guide

## Project Overview

This is a real-time greenhouse automation system featuring:
- **Real-time C Controller** (Linux RT) - Decision-making engine
- **Sensor Simulator** (Python) - Temperature, humidity, soil moisture
- **MQTT Broker** - Local message broker for IoT communication
- **Firebase Cloud Sync** (Python) - Cloud database integration
- **Web Dashboard** - Real-time monitoring and control interface

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WEB DASHBOARD (HTML/JS)                  │
│              Real-time Monitoring & Manual Control          │
└─────────────────────────────────────────────────────────────┘
                            ↑↓ HTTP/WebSocket
┌──────────────────┐   ┌──────────────────┐   ┌────────────────┐
│  Sensor Sim.     │   │  RT C Controller │   │  Firebase Sync │
│  (Python)        │   │  (Linux C RT)    │   │  (Python)      │
│  - Publishes     │   │  - Subscribes    │   │  - Syncs to    │
│  sensor data     │   │  - Executes      │   │  Cloud DB      │
│               ↓       │  Rules 1,2,3    │  ↓                 │
└──────────────────┘    │  - Publishes    │   └────────────────┘
                        │  actuator cmds  │
                        └──────────────────┘
                            ↓↑ MQTT
                    ┌────────────────────┐
                    │ MQTT Broker        │
                    │ (mosquitto)        │
                    │ localhost:1883     │
                    └────────────────────┘
```

## Prerequisites

### Windows (Host Machine)
- Windows 10/11
- WSL 2 (Windows Subsystem for Linux)
- Ubuntu 20.04 or 22.04 (installed in WSL)
- Python 3.7+ (on Windows or WSL)

### Linux Requirements
- gcc compiler
- libmosquitto-dev
- libpaho-mqtt-dev
- Python 3.7+
- pip package manager

## Step 1: Install WSL2 with Ubuntu

### On Windows (PowerShell as Administrator):

```powershell
# Enable WSL2
wsl --install -d Ubuntu-22.04

# After installation, start Ubuntu and set username/password
# Test installation
wsl --list --verbose
```

## Step 2: Install Required Linux Packages

### In WSL Ubuntu Terminal:

```bash
# Update package manager
sudo apt update
sudo apt upgrade -y

# Install MQTT broker
sudo apt install -y mosquitto mosquitto-clients

# Install development tools
sudo apt install -y build-essential
sudo apt install -y gcc make cmake
sudo apt install -y libmosquitto-dev libmosquitto0
sudo apt install -y python3 python3-pip python3-venv

# Install Python MQTT client
pip3 install paho-mqtt

# (Optional) Install Firebase admin SDK
pip3 install firebase-admin
```

### Verify installations:

```bash
mosquitto --version
gcc --version
python3 --version
pip3 list | grep paho-mqtt
```

## Step 3: Configure and Start MQTT Broker

### Setup mosquitto:

```bash
# Create mosquitto directories
mkdir -p ~/mosquitto/config ~/mosquitto/data ~/mosquitto/log

# Create configuration from the provided mosquitto.conf
# Copy config/mosquitto.conf to ~/.mosquitto/mosquitto.conf
cp mosquitto.conf ~/.mosquitto/mosquitto.conf

# Create mosquitto user (optional, required if not running as current user)
sudo useradd -r -s /bin/false mosquitto 2>/dev/null || true

# Start mosquitto in WSL
mosquitto -c ~/.mosquitto/mosquitto.conf -v
```

### Verify broker is running:

In another WSL terminal:
```bash
mosquitto_sub -h localhost -t 'greenhouse/#'
```

## Step 4: Compile the C Real-Time Controller

### In WSL Ubuntu Terminal:

```bash
cd ~/Beadando/rt_controller

# Compile
make clean
make

# Verify executable was created
ls -la greenhouse_controller
```

### Prerequisites for C compilation:
If compilation fails, install:
```bash
sudo apt install -y libpaho-mqtt-dev
```

## Step 5: Configure Python Environment

### Setup virtual environment (recommended):

```bash
cd ~/Beadando

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install paho-mqtt
pip install firebase-admin  # Optional
```

## Step 6: Start All Components

### Terminal 1 - MQTT Broker (WSL):
```bash
mosquitto -c ~/.mosquitto/mosquitto.conf -v
```

### Terminal 2 - Sensor Simulator (WSL):
```bash
cd ~/Beadando
source venv/bin/activate  # If using venv
python3 sensors/sensor_simulator.py \
    --host localhost \
    --port 1883 \
    --greenhouse-id 1 \
    --plants 3 \
    --interval 5
```

### Terminal 3 - RT C Controller (WSL):
```bash
cd ~/Beadando/rt_controller
sudo ./greenhouse_controller
# Note: Requires sudo for real-time scheduling (SCHED_FIFO)
```

### Terminal 4 - Firebase Sync (WSL):
```bash
cd ~/Beadando
source venv/bin/activate  # If using venv
python3 firebase_sync/firebase_sync.py
# Runs in DEMO mode (no Firebase)
```

**With Firebase Cloud Sync**:
```bash
python3 firebase_sync/firebase_sync.py \
    --credentials config/firebase-credentials.json
# Runs in LIVE mode (syncs to Firebase)
```

See: [FIREBASE_QUICK_START.md](./FIREBASE_QUICK_START.md) for setup

### Terminal 5 - Web Dashboard:
Open in any web browser:
```
http://localhost:8000/dashboard/index.html
```

Or serve with Python:
```bash
cd ~/Beadando
python3 -m http.server 8000
# Then open: http://localhost:8000/dashboard/index.html
```

## Step 7: Test the System

### Check MQTT messages:

In a new WSL terminal:
```bash
# Subscribe to all greenhouse topics
mosquitto_sub -h localhost -t 'greenhouse/#' -v
```

You should see messages like:
```
greenhouse/1/env/temp 22
greenhouse/1/env/humidity 65
greenhouse/1/plant/1/soil 50
greenhouse/1/plant/2/soil 45
greenhouse/1/plant/3/soil 55
```

### Test manual pump control:

```bash
# Turn pump ON for plant 1
mosquitto_pub -h localhost -t 'greenhouse/1/plant/1/pump' -m 'ON'

# Turn pump OFF
mosquitto_pub -h localhost -t 'greenhouse/1/plant/1/pump' -m 'OFF'

# Watch sensor response - moisture should increase
```

### Test RT controller rules:

1. **Rule 1 (Watering)**: Drop soil moisture below 30% - RT controller should activate pump
2. **Rule 2 (Ventilation)**: Raise temperature above 30°C - RT controller should open window
3. **Rule 3 (Safety Alert)**: Raise CO2 above 1500 ppm - RT controller should trigger alarm

## Quick Start Script

Create `start_system.sh` in the project root:

```bash
#!/bin/bash

# Source directory
cd "$(dirname "$0")" || exit

# Kill any existing processes
pkill -f mosquitto
pkill -f greenhouse_controller
pkill -f sensor_simulator
pkill -f firebase_sync

sleep 1

# Start MQTT Broker
echo "[1/4] Starting MQTT Broker..."
mosquitto -c ~/.mosquitto/mosquitto.conf -v &
MQTT_PID=$!
sleep 2

# Start Sensor Simulator
echo "[2/4] Starting Sensor Simulator..."
source venv/bin/activate
python3 sensors/sensor_simulator.py &
SENSOR_PID=$!
sleep 1

# Start RT Controller
echo "[3/4] Starting RT Controller (requires sudo for real-time scheduling)..."
cd rt_controller
sudo ./greenhouse_controller &
CONTROLLER_PID=$!
cd ..

# Start Firebase Sync
echo "[4/4] Starting Firebase Sync..."
python3 firebase_sync/firebase_sync.py &
SYNC_PID=$!

echo ""
echo "========================================="
echo "System Started Successfully!"
echo "========================================="
echo ""
echo "Components:"
echo "  MQTT Broker: localhost:1883"
echo "  Sensor Simulator: PID $SENSOR_PID"
echo "  RT Controller: PID $CONTROLLER_PID"
echo "  Firebase Sync: PID $SYNC_PID"
echo ""
echo "Dashboard: Open http://localhost:8000/dashboard/index.html"
echo ""
echo "To stop all services, run: pkill -P $$"
echo ""

# Wait for interruption
wait
```

Make it executable:
```bash
chmod +x start_system.sh
./start_system.sh
```

## MQTT Topic Structure

### Sensor Publishers (Data Flow):
- `greenhouse/1/env/temp` - Temperature (int, °C)
- `greenhouse/1/env/humidity` - Humidity (int, %)
- `greenhouse/1/env/co2` - CO₂ level (int, ppm)
- `greenhouse/1/plant/[1-3]/soil` - Soil moisture (int, %)

### Actuator Subscribers (Control Flow):
- `greenhouse/1/plant/[1-3]/pump` - Pump control (`ON`/`OFF`)
- `greenhouse/1/actuators/window` - Ventilation (`OPEN`/`CLOSE`)
- `greenhouse/1/status/alarm` - System alert (`CRITICAL`/`NORMAL`)

## Real-Time Controller Rules

### Rule 1: Targeted Watering
```
IF greenhouse/1/plant/X/soil < 30% THEN
  PUBLISH "ON" to greenhouse/1/plant/X/pump
```

### Rule 2: Ventilation Control
```
IF greenhouse/1/env/temp > 30°C THEN
  PUBLISH "OPEN" to greenhouse/1/actuators/window
```

### Rule 3: Safety Alert
```
IF greenhouse/1/env/co2 > 1500 ppm THEN
  PUBLISH "CRITICAL" to greenhouse/1/status/alarm
```

## Troubleshooting

### MQTT Broker won't start
```bash
# Check if port 1883 is already in use
sudo lsof -i :1883

# Kill existing mosquitto process
pkill mosquitto

# Try starting again
mosquitto -c ~/.mosquitto/mosquitto.conf -v
```

### C Compilation errors
```bash
# Install missing libraries
sudo apt install -y libpaho-mqtt-dev libmosquitto-dev

# Try compilation again
cd rt_controller
make clean && make
```

### Python module not found
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall packages
pip install --upgrade paho-mqtt firebase-admin
```

### Real-time scheduling not available
On Windows WSL, real-time scheduling (SCHED_FIFO) may not be fully supported. The system will fall back to normal scheduling with a warning. To get true real-time scheduling, use:
- ELTE server (if available)
- Dedicated Linux machine
- Raspberry Pi with real-time kernel patches (though not recommended for production)

### Dashboard not updating
1. Check if sensor simulator is sending data: `mosquitto_sub -h localhost -t 'greenhouse/#' -v`
2. Check browser console for JavaScript errors (F12)
3. Verify firewall isn't blocking localhost:8000

## File Structure

```
Beadando/
├── rt_controller/
│   ├── greenhouse_controller.c       # Real-time C controller
│   └── Makefile                       # Build configuration
├── sensors/
│   └── sensor_simulator.py            # Sensor data simulator
├── firebase_sync/
│   └── firebase_sync.py               # Cloud sync service
├── dashboard/
│   └── index.html                     # Web interface
├── config/
│   └── mosquitto.conf                 # MQTT broker config
└── docs/
    └── INSTALLATION.md                # This file
```

## Production Deployment Notes

1. **Use real-time Linux OS**: Current system uses WSL which may have latency. For production, use:
   - ELTE server
   - Real Linux machine
   - Raspberry Pi with RT patches

2. **Enable authentication**: Add MQTT username/password in mosquitto.conf

3. **Use SSL/TLS**: Configure certificate-based communication

4. **Setup database**: Integrate proper Firebase project or database

5. **Deploy dashboard**: Use web server (nginx/Apache) instead of Python's http.server

6. **Monitor system**: Add logging and monitoring tools (Prometheus, Grafana)

## Support

For issues or questions:
1. Check system logs: `tail -f ~/.mosquitto/mosquitto.log`
2. Verify component connectivity with mosquitto_sub/pub
3. Check Python error messages and stack traces
4. Review C program output for real-time scheduling warnings

---

**Last Updated**: 2026-04-08
**System Version**: 1.0
**Component Requirements**: ✓ Linux C RT, ✓ Sensors, ✓ MQTT, ✓ Cloud Sync, ✓ Dashboard, ✓ Real-time Communication
