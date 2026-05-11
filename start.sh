#!/bin/bash
# Greenhouse rendszer indítása — minden komponens külön processzként
# Futtatás: bash start.sh   (WSL-ből, a projekt gyökérből)

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
    log "Leállítás..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    sudo pkill -f greenhouse_controller 2>/dev/null || true
    log "Minden leállt."
}
trap cleanup EXIT INT TERM

cd "$PROJECT_DIR" || { err "Projekt mappa nem található: $PROJECT_DIR"; exit 1; }
source "$VENV"    || { err "venv nem található: $VENV"; exit 1; }

# ── 1. RT controller fordítás ─────────────────────────────────────
log "RT controller fordítása..."
(cd "$RT_DIR" && make -s) || { err "make sikertelen"; exit 1; }

# ── 2. MQTT Broker ────────────────────────────────────────────────
log "MQTT broker indítása (port 1883, ws 9001)..."
mkdir -p /tmp/mosquitto
mosquitto -c "$PROJECT_DIR/config/mosquitto.conf" &
PIDS+=($!)
sleep 1

# ── 3. RT Controller — Greenhouse 1 ──────────────────────────────
log "RT Controller gh=1..."
(cd "$RT_DIR" && sudo ./greenhouse_controller --greenhouse-id 1 2>&1 | sed 's/^/[rt-gh1] /') &
PIDS+=($!)

# ── 4. RT Controller — Greenhouse 2 ──────────────────────────────
log "RT Controller gh=2..."
(cd "$RT_DIR" && sudo ./greenhouse_controller --greenhouse-id 2 2>&1 | sed 's/^/[rt-gh2] /') &
PIDS+=($!)
sleep 1

# ── 5. Szimulátor — gh1 plant 2,3 ────────────────────────────────
log "Szimulátor gh=1 plant=2,3..."
python3 sensors/sensor_simulator.py \
    --greenhouse-ids 1 --plant-ids 2,3 --interval 5 \
    2>&1 | sed 's/^/[sim-gh1] /' &
PIDS+=($!)

# ── 6. Szimulátor — gh2 összes plant ─────────────────────────────
log "Szimulátor gh=2 plant=1,2,3..."
python3 sensors/sensor_simulator.py \
    --greenhouse-ids 2 --plants 3 --interval 5 \
    2>&1 | sed 's/^/[sim-gh2] /' &
PIDS+=($!)

# ── 7. Firebase Sync ──────────────────────────────────────────────
if [ -f "$CREDS" ]; then
    log "Firebase Sync..."
    python3 firebase_sync/firebase_sync.py \
        --credentials "$CREDS" \
        --firebase-url "$FIREBASE_URL" \
        --greenhouse-ids 1,2 \
        2>&1 | sed 's/^/[firebase] /' &
    PIDS+=($!)
else
    warn "Firebase credentials nem található, kihagyva."
fi

# ── 8. Dashboard webszerver ───────────────────────────────────────
log "Dashboard webszerver (port 8000)..."
python3 -m http.server 8000 2>&1 | sed 's/^/[http] /' &
PIDS+=($!)

echo ""
log "══════════════════════════════════════════"
log "Minden komponens elindult."
log "Dashboard: http://localhost:8000/dashboard/index.html"
log "Leállításhoz: Ctrl+C"
log "══════════════════════════════════════════"
echo ""

wait
