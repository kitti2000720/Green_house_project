#!/bin/bash
# Run from WSL project root: bash start.sh

PROJECT_DIR="/mnt/c/Users/molar/Green_house_project"
VENV="$PROJECT_DIR/venv/bin/activate"
RT_DIR="$PROJECT_DIR/rt_controller"
CREDS="green-house-d7b7f-firebase-adminsdk-fbsvc-bf0cb07c7c.json"
FIREBASE_URL="https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[start]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $1"; }
err()  { echo -e "${RED}[error]${NC} $1"; }

PIDS=()

cleanup() {
    echo ""
    log "Stopping..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    sudo pkill -f greenhouse_controller 2>/dev/null || true
    log "All stopped."
}
trap cleanup EXIT INT TERM

cd "$PROJECT_DIR" || { err "Project directory not found: $PROJECT_DIR"; exit 1; }
source "$VENV"    || { err "venv not found: $VENV"; exit 1; }

log "Authenticating sudo (required for RT controller)..."
sudo -v || { err "sudo failed"; exit 1; }

log "Building RT controller..."
(cd "$RT_DIR" && make -s) || { err "make failed"; exit 1; }

log "Starting MQTT broker (port 1883, ws 9001)..."
mkdir -p /tmp/mosquitto
mosquitto -c "$PROJECT_DIR/config/mosquitto.conf" &
PIDS+=($!)
sleep 1

log "Starting RT Controller gh=1..."
(cd "$RT_DIR" && sudo ./greenhouse_controller --greenhouse-id 1 2>&1 | sed 's/^/[rt-gh1] /') &
PIDS+=($!)

log "Starting RT Controller gh=2..."
(cd "$RT_DIR" && sudo ./greenhouse_controller --greenhouse-id 2 2>&1 | sed 's/^/[rt-gh2] /') &
PIDS+=($!)
sleep 1

log "Starting Simulator gh=1 plant=2,3..."
python3 sensors/sensor_simulator.py \
    --greenhouse-ids 1 --plant-ids 2,3 --interval 5 \
    2>&1 | sed 's/^/[sim-gh1] /' &
PIDS+=($!)

log "Starting Simulator gh=2 plant=1,2,3..."
python3 sensors/sensor_simulator.py \
    --greenhouse-ids 2 --plants 3 --interval 5 \
    2>&1 | sed 's/^/[sim-gh2] /' &
PIDS+=($!)

if [ -f "$CREDS" ]; then
    log "Starting Firebase Sync..."
    python3 firebase_sync/firebase_sync.py \
        --credentials "$CREDS" \
        --firebase-url "$FIREBASE_URL" \
        --greenhouse-ids 1,2 \
        2>&1 | sed 's/^/[firebase] /' &
    PIDS+=($!)
else
    warn "Firebase credentials not found, skipping."
fi

log "Starting dashboard web server (port 8000)..."
python3 -m http.server 8000 2>&1 | sed 's/^/[http] /' &
PIDS+=($!)

echo ""
log "=========================================="
log "All components started."
log "Dashboard: http://localhost:8000/dashboard/index.html"
log "Stop with Ctrl+C"
log "=========================================="
echo ""

wait
