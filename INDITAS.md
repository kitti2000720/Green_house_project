# Greenhouse rendszer indítása

## Gyors indítás — `start.sh` (ajánlott)

Minden komponenst egyszerre indít WSL-ből:
```bash
cd /mnt/c/Users/molar/Green_house_project
bash start.sh
```
Leállítás: **Ctrl+C** — az összes folyamat automatikusan leáll.

A script sorrendben elindítja: fordítás → mosquitto → 2× RT controller → 2× szimulátor → Firebase sync → HTTP szerver.  
Minden komponens kimenete előtaggal jelenik meg: `[rt-gh1]`, `[sim-gh1]`, `[firebase]`, stb.

---

## Manuális indítás (terminálonként)

## Terminal 1 — MQTT Broker (WSL)
```bash
mkdir -p /tmp/mosquitto
mosquitto -c /mnt/c/Users/molar/Green_house_project/config/mosquitto.conf -v
```

---

## Terminal 2 — RT Controller — Greenhouse 1 (WSL)
```bash
cd /mnt/c/Users/molar/Green_house_project/rt_controller
sudo ./greenhouse_controller --greenhouse-id 1
```

## Terminal 3 — RT Controller — Greenhouse 2 (WSL)
```bash
cd /mnt/c/Users/molar/Green_house_project/rt_controller
sudo ./greenhouse_controller --greenhouse-id 2
```

A controller 100ms-es RT ciklusban fut (SCHED_FIFO, clock_nanosleep TIMER_ABSTIME).  
Automatikusan vezérli:
- **Pump ON** ha soil < 30% → **Pump OFF** ha soil ≥ 55%
- **Window OPEN** ha temp > 30°C → **Window CLOSED** ha temp ≤ 25°C
- **CO2 ALARM** ha co2 > 1500 ppm

---

## Terminal 4a — Szimulátor: Greenhouse 1 plant 2-3 (WSL)
```bash
cd /mnt/c/Users/molar/Green_house_project
source venv/bin/activate
python3 sensors/sensor_simulator.py --greenhouse-ids 1 --plant-ids 2,3 --interval 5
```

## Terminal 4b — Szimulátor: Greenhouse 2 összes plant (WSL)
```bash
cd /mnt/c/Users/molar/Green_house_project
source venv/bin/activate
python3 sensors/sensor_simulator.py --greenhouse-ids 2 --plants 3 --interval 5
```

Adatforrások összefoglalása:
- Greenhouse 1 plant 1 → Raspberry Pi (valós/szimulált szenzor)
- Greenhouse 1 plant 2-3 → Szimulátor (Terminal 4a)
- Greenhouse 2 plant 1-3 → Szimulátor (Terminal 4b)

---

## Terminal 5 — Firebase Sync (WSL)
```bash
cd /mnt/c/Users/molar/Green_house_project
source venv/bin/activate
python3 firebase_sync/firebase_sync.py \
    --credentials green-house-d7b7f-firebase-adminsdk-fbsvc-bf0cb07c7c.json \
    --firebase-url https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app \
    --greenhouse-ids 1 2
```

---

## Terminal 6 — Dashboard webszerver (Windows PowerShell)
```powershell
cd /mnt/c/Users/molar/Green_house_project
python3 -m http.server 8000
```
Böngészőben: `http://localhost:8000/dashboard/index.html`

---

## Raspberry Pi — plant 1 (greenhouse 1)

SSH belépés (Windows PowerShell-ből):
```powershell
ssh erts2026@10.157.157.105
```

Az RPi-n (a `~/greenhouse` mappából):
```bash
python3 rpi_sensor_reader.py --host 10.157.157.226 --greenhouse-id 1 --plant-id 1 --interval 5
```

Megjegyzés: Windows host IP kell (10.157.157.226), NEM a WSL IP.
Port forwarding (egyszer, admin PowerShell-ben):
```powershell
netsh interface portproxy add v4tov4 listenport=1883 listenaddress=0.0.0.0 connectport=1883 connectaddress=172.27.140.198
netsh interface portproxy add v4tov4 listenport=9001 listenaddress=0.0.0.0 connectport=9001 connectaddress=172.27.140.198
New-NetFirewallRule -DisplayName "MQTT 1883" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow
```
---

## MQTT figyelés (opcionális)
```bash
mosquitto_sub -h localhost -t 'greenhouse/#' -v
```

---

## Automatikus vezérlési hurok

```
RPi / Szimulátor
      ↓  sensor adatok (MQTT)
  RT Controller  ←── 100ms SCHED_FIFO loop
      ↓  aktuátor parancsok (MQTT)
  Szimulátor (dinamika frissül)
      ↓
  Firebase Sync  →  Firebase Realtime DB
  Dashboard      →  böngésző (live MQTT WebSocket)
```

## Megjegyzések
- Broker újraindítás előtt: `sudo pkill mosquitto`
- RT controller sudo nélkül is fut, de SCHED_FIFO csak sudo-val aktív
- A szimulátor plant 1 adatait is generálja — ha az RPi fut, azokat felülírja
- Firebase sync --greenhouse-ids paramétere bővíthető új üvegházakkal
