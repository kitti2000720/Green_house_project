#!/bin/bash
# Quick Start - launches all system components.

set -euo pipefail

echo "Greenhouse Automation System - Quick Start"
echo "==========================================="
echo ""

# ------------------------------------------------------------------
# Detect WSL
# ------------------------------------------------------------------
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "[Check] Running in WSL"
else
    echo "[Warn]  Not running in WSL. This system is optimised for WSL2 + Ubuntu."
fi

# ------------------------------------------------------------------
# Dependency checks
# ------------------------------------------------------------------
echo ""
echo "Checking dependencies..."

check_cmd() {
    if command -v "$1" >/dev/null 2>&1; then
        echo "  [OK]  $1"
    else
        echo "  [FAIL] $1 not found. Run: $2"
        return 1
    fi
}

deps_ok=true

check_cmd mosquitto "sudo apt install mosquitto mosquitto-clients" || deps_ok=false
check_cmd gcc       "sudo apt install build-essential"            || deps_ok=false
check_cmd python3   "sudo apt install python3 python3-pip"        || deps_ok=false

if python3 -c "import paho.mqtt" 2>/dev/null; then
    echo "  [OK]  paho-mqtt"
else
    echo "  [FAIL] paho-mqtt not installed. Run: pip3 install paho-mqtt"
    deps_ok=false
fi

if [ "$deps_ok" = false ]; then
    echo ""
    echo "[Error] Some dependencies are missing. Install them and try again."
    exit 1
fi

# ------------------------------------------------------------------
# Build RT controller
# ------------------------------------------------------------------
echo ""
echo "Building RT Controller..."

cd rt_controller
make clean  >/dev/null 2>&1 || true
if ! make   >/dev/null 2>&1; then
    echo "[Error] Compilation failed. Run 'make -C rt_controller' for details."
    exit 1
fi
if [ ! -f "greenhouse_controller" ]; then
    echo "[Error] Compiled binary not found."
    exit 1
fi
echo "[OK] RT Controller built."
cd ..

# ------------------------------------------------------------------
# Kill any leftover processes
# ------------------------------------------------------------------
pkill -f mosquitto            2>/dev/null || true
pkill -f greenhouse_controller 2>/dev/null || true
pkill -f sensor_simulator      2>/dev/null || true
pkill -f firebase_sync         2>/dev/null || true
sleep 1

# ------------------------------------------------------------------
# 1. MQTT Broker
# ------------------------------------------------------------------
echo ""
echo "[1/4] Starting MQTT Broker..."
mosquitto -c config/mosquitto.conf -v >/tmp/mosquitto.log 2>&1 &
MQTT_PID=$!
sleep 2

if ! kill -0 "$MQTT_PID" 2>/dev/null; then
    echo "[Error] MQTT Broker failed to start."
    cat /tmp/mosquitto.log
    exit 1
fi
echo "      MQTT Broker running (PID: $MQTT_PID)"

# Connectivity test
if mosquitto_pub -h localhost -p 1883 -t test/connection -m ok 2>/dev/null; then
    echo "      Broker connectivity verified."
fi

# ------------------------------------------------------------------
# 2. Sensor Simulator
# ------------------------------------------------------------------
echo ""
echo "[2/4] Starting Sensor Simulator..."
python3 sensors/sensor_simulator.py \
    --greenhouse-id 1 --plants 3 --interval 5 \
    >/tmp/sensor_sim.log 2>&1 &
SENSOR_PID=$!
sleep 2

if ! kill -0 "$SENSOR_PID" 2>/dev/null; then
    echo "[Error] Sensor Simulator failed to start."
    cat /tmp/sensor_sim.log
    exit 1
fi
echo "      Sensor Simulator running (PID: $SENSOR_PID)"

# ------------------------------------------------------------------
# 3. RT Controller
# ------------------------------------------------------------------
echo ""
echo "[3/4] Starting RT Controller..."
cd rt_controller

if sudo -n ./greenhouse_controller >/tmp/rt_controller.log 2>&1 & then
    CONTROLLER_PID=$!
else
    ./greenhouse_controller >/tmp/rt_controller.log 2>&1 &
    CONTROLLER_PID=$!
    echo "      Note: running without real-time scheduling (no sudo access)"
fi

sleep 2
if ! kill -0 "$CONTROLLER_PID" 2>/dev/null; then
    echo "[Error] RT Controller died unexpectedly."
    cat /tmp/rt_controller.log
    exit 1
fi
echo "      RT Controller running (PID: $CONTROLLER_PID)"
cd ..

# ------------------------------------------------------------------
# 4. Firebase Sync
# ------------------------------------------------------------------
echo ""
echo "[4/4] Starting Firebase Sync Service..."
CREDS_FILE="green-house-d7b7f-firebase-adminsdk-fbsvc-bf0cb07c7c.json"
FIREBASE_ARGS="--greenhouse-id 1 --firebase-url https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app"

if [ -f "$CREDS_FILE" ]; then
    FIREBASE_ARGS="$FIREBASE_ARGS --credentials $CREDS_FILE"
    echo "      Credentials found - starting in LIVE mode."
else
    echo "      Credentials not found - starting in DEMO mode."
fi

# shellcheck disable=SC2086
python3 firebase_sync/firebase_sync.py $FIREBASE_ARGS >/tmp/firebase_sync.log 2>&1 &
SYNC_PID=$!
sleep 2

if kill -0 "$SYNC_PID" 2>/dev/null; then
    echo "      Firebase Sync running (PID: $SYNC_PID)"
else
    echo "      Firebase Sync failed to start (check /tmp/firebase_sync.log)"
fi

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo "System started."
echo ""
echo "  Dashboard : http://localhost:8000/dashboard/index.html"
echo "              (run 'python3 -m http.server 8000' in another terminal)"
echo ""
echo "  Monitor MQTT:"
echo "    mosquitto_sub -h localhost -t 'greenhouse/#' -v"
echo ""
echo "  Manual pump control:"
echo "    mosquitto_pub -h localhost -t 'greenhouse/1/plant/1/pump' -m 'ON'"
echo ""
echo "  PIDs:  MQTT=$MQTT_PID  Sensors=$SENSOR_PID  Controller=$CONTROLLER_PID  Firebase=$SYNC_PID"
echo ""
echo "Press Ctrl+C to stop all components."
echo ""

wait
