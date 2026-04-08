#!/bin/bash
# Quick Start Guide - Get the system running in 5 minutes

echo "🌱 Greenhouse Automation System - Quick Start"
echo "=============================================="
echo ""

# Check if running in WSL
if grep -qi microsoft /proc/version; then
    echo "✓ Running in WSL"
else
    echo "⚠ WARNING: Not running in WSL. This system is optimized for WSL2 + Ubuntu"
fi

echo ""
echo "Step 1: Checking dependencies..."
echo "================================"

# Check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

deps_ok=true

if command_exists mosquitto; then
    echo "✓ mosquitto installed"
else
    echo "✗ mosquitto NOT installed"
    echo "  Run: sudo apt install mosquitto mosquitto-clients"
    deps_ok=false
fi

if command_exists gcc; then
    echo "✓ GCC installed"
else
    echo "✗ GCC NOT installed"
    echo "  Run: sudo apt install build-essential"
    deps_ok=false
fi

if command_exists python3; then
    echo "✓ Python3 installed"
else
    echo "✗ Python3 NOT installed"
    echo "  Run: sudo apt install python3 python3-pip"
    deps_ok=false
fi

if ! python3 -c "import paho.mqtt" 2>/dev/null; then
    echo "✗ paho-mqtt NOT installed"
    echo "  Run: pip3 install paho-mqtt"
    deps_ok=false
else
    echo "✓ paho-mqtt installed"
fi

if [ "$deps_ok" = false ]; then
    echo ""
    echo "❌ Some dependencies are missing. Install them and try again."
    exit 1
fi

echo ""
echo "Step 2: Compiling C controller..."
echo "================================"

if [ ! -d "rt_controller" ]; then
    echo "❌ rt_controller directory not found"
    exit 1
fi

cd rt_controller
if ! make clean >/dev/null 2>&1; then
    echo "✗ Make failed"
    exit 1
fi

if ! make >/dev/null 2>&1; then
    echo "❌ Compilation failed"
    cd ..
    exit 1
fi

if [ ! -f "greenhouse_controller" ]; then
    echo "❌ Compilation did not produce executable"
    exit 1
fi

echo "✓ RT Controller compiled successfully"
cd ..

echo ""
echo "Step 3: Starting components..."
echo "=============================="
echo ""

# Kill any existing processes
pkill -f mosquitto 2>/dev/null
pkill -f greenhouse_controller 2>/dev/null
pkill -f sensor_simulator 2>/dev/null
pkill -f firebase_sync 2>/dev/null

sleep 1

# Start MQTT Broker
echo "[1/4] Starting MQTT Broker..."
mosquitto -c config/mosquitto.conf -v > /tmp/mosquitto.log 2>&1 &
MQTT_PID=$!
sleep 2

# Check if broker started
if ! kill -0 $MQTT_PID 2>/dev/null; then
    echo "❌ Failed to start MQTT Broker"
    cat /tmp/mosquitto.log
    exit 1
fi
echo "✓ MQTT Broker started (PID: $MQTT_PID)"

# Test broker connectivity
if mosquitto_pub -h localhost -p 1883 -t test/connection -m '{"test":"ok"}' 2>/dev/null; then
    echo "✓ MQTT Broker is responding"
    mosquitto_pub -h localhost -p 1883 -t test/connection -m "" -n >/dev/null 2>&1
else
    echo "⚠ MQTT Broker connectivity test failed"
fi

# Start Sensor Simulator
echo "[2/4] Starting Sensor Simulator..."
python3 sensors/sensor_simulator.py --greenhouse-id 1 --plants 3 --interval 5 > /tmp/sensor_sim.log 2>&1 &
SENSOR_PID=$!
sleep 2

if ! kill -0 $SENSOR_PID 2>/dev/null; then
    echo "❌ Failed to start Sensor Simulator"
    cat /tmp/sensor_sim.log
    exit 1
fi
echo "✓ Sensor Simulator started (PID: $SENSOR_PID)"

# Start RT Controller
echo "[3/4] Starting RT Controller..."
cd rt_controller

# Try with sudo for real-time scheduling
if sudo -n ./greenhouse_controller > /tmp/rt_controller.log 2>&1 &
then
    CONTROLLER_PID=$!
elif ./greenhouse_controller > /tmp/rt_controller.log 2>&1 &
then
    CONTROLLER_PID=$!
    echo "⚠ RT Controller running without real-time scheduling (requires sudo)"
else
    echo "❌ Failed to start RT Controller"
    cat /tmp/rt_controller.log
    exit 1
fi

sleep 2

if ! kill -0 $CONTROLLER_PID 2>/dev/null; then
    echo "❌ RT Controller died unexpectedly"
    cat /tmp/rt_controller.log
    exit 1
fi

echo "✓ RT Controller started (PID: $CONTROLLER_PID)"
cd ..

# Start Firebase Sync
echo "[4/4] Starting Firebase Sync Service..."
python3 firebase_sync/firebase_sync.py --greenhouse-id 1 > /tmp/firebase_sync.log 2>&1 &
SYNC_PID=$!
sleep 2

if ! kill -0 $SYNC_PID 2>/dev/null; then
    echo "⚠ Firebase Sync failed to start (this is OK if no Firebase credentials)"
else
    echo "✓ Firebase Sync started (PID: $SYNC_PID)"
fi

echo ""
echo "✅ System started successfully!"
echo ""
echo "📊 Dashboard: http://localhost:8000/dashboard/index.html"
echo "   (Run: python3 -m http.server 8000)"
echo ""
echo "📡 View MQTT messages in another terminal:"
echo "   mosquitto_sub -h localhost -t 'greenhouse/#' -v"
echo ""
echo "🔧 Manual control (example - turn pump ON for plant 1):"
echo "   mosquitto_pub -h localhost -t 'greenhouse/1/plant/1/pump' -m 'ON'"
echo ""
echo "📝 System information:"
echo "   MQTT Broker:      localhost:1883 (PID: $MQTT_PID)"
echo "   Sensor Sim:       PID: $SENSOR_PID"
echo "   RT Controller:    PID: $CONTROLLER_PID"
echo "   Firebase Sync:    PID: $SYNC_PID"
echo ""
echo "⚠ To stop all services:"
echo "   pkill -P $$"
echo ""

# Wait for user interrupt
echo "Press Ctrl+C to stop all services..."
wait
