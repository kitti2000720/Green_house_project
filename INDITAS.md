# Greenhouse System — Startup Guide

## Quick Start (recommended)

Start all components from WSL with a single command:
```bash
cd /mnt/c/Users/molar/Green_house_project
bash start.sh
```
Stop with **Ctrl+C** — all processes shut down automatically.

---

## Manual Startup

### Terminal 1 — MQTT Broker
```bash
mkdir -p /tmp/mosquitto
mosquitto -c /mnt/c/Users/molar/Green_house_project/config/mosquitto.conf -v
```

### Terminal 2 — RT Controller (Greenhouse 1)
```bash
cd /mnt/c/Users/molar/Green_house_project/rt_controller
sudo ./greenhouse_controller --greenhouse-id 1
```

### Terminal 3 — RT Controller (Greenhouse 2)
```bash
cd /mnt/c/Users/molar/Green_house_project/rt_controller
sudo ./greenhouse_controller --greenhouse-id 2
```

### Terminal 4a — Simulator: Greenhouse 1 plants 2–3
```bash
cd /mnt/c/Users/molar/Green_house_project
source venv/bin/activate
python3 sensors/sensor_simulator.py --greenhouse-ids 1 --plant-ids 2,3 --interval 5
```

### Terminal 4b — Simulator: Greenhouse 2 all plants
```bash
cd /mnt/c/Users/molar/Green_house_project
source venv/bin/activate
python3 sensors/sensor_simulator.py --greenhouse-ids 2 --plants 3 --interval 5
```

Data sources:
- Greenhouse 1 plant 1 → Raspberry Pi
- Greenhouse 1 plant 2–3 → Simulator (Terminal 4a)
- Greenhouse 2 plant 1–3 → Simulator (Terminal 4b)

### Terminal 5 — Firebase Sync
```bash
cd /mnt/c/Users/molar/Green_house_project
source venv/bin/activate
python3 firebase_sync/firebase_sync.py \
    --credentials green-house-d7b7f-firebase-adminsdk-fbsvc-bf0cb07c7c.json \
    --firebase-url https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app \
    --greenhouse-ids 1,2
```

### Terminal 6 — Dashboard
```bash
python3 -m http.server 8000
```
Open: `http://localhost:8000/dashboard/index.html`

---

## Raspberry Pi — plant 1 (greenhouse 1)

SSH from Windows PowerShell:
```powershell
ssh erts2026@10.157.157.105
```

On the RPi:
```bash
venv/bin/python3 rpi_sensor_reader.py --host 10.157.157.226 --greenhouse-id 1 --plant-id 1 --interval 5
```

Note: use the Windows host IP (10.157.157.226), not the WSL IP.

Port forwarding (one-time, admin PowerShell):
```powershell
netsh interface portproxy add v4tov4 listenport=1883 listenaddress=0.0.0.0 connectport=1883 connectaddress=172.27.140.198
netsh interface portproxy add v4tov4 listenport=9001 listenaddress=0.0.0.0 connectport=9001 connectaddress=172.27.140.198
New-NetFirewallRule -DisplayName "MQTT 1883" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow
```

---

## Control Rules

| Actuator | On | Off |
|---|---|---|
| Pump | soil < 30% | soil ≥ 55% |
| Window | temp > 30 °C or CO2 > 1200 ppm | temp ≤ 25 °C and CO2 < 900 ppm |
| CO2 Enricher | CO2 < 600 ppm | CO2 ≥ 900 ppm |
| Alarm | CO2 > 1500 ppm | CO2 drops below 1500 ppm |

---

## Notes
- Kill broker before restart: `sudo pkill mosquitto`
- RT controller runs without sudo but SCHED_FIFO requires root
- Monitor all topics: `mosquitto_sub -h localhost -t 'greenhouse/#' -v`
