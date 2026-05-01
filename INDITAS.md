# Greenhouse rendszer indítása

## Terminal 1 — MQTT Broker
```bash
mkdir -p /tmp/mosquitto && mosquitto -c /mnt/c/Users/molar/Green_house_project/config/mosquitto.conf -v

```

---

## Terminal 2 — RT Controller
```bash
cd /mnt/c/Users/molar/Green_house_project/rt_controller
sudo ./greenhouse_controller --greenhouse-id 1
```

---

## Terminal 3 — Szimulátor (plant 2 és 3, mert plant 1 = RPi)
```bash
cd /mnt/c/Users/molar/Green_house_project
source venv/bin/activate
python3 sensors/sensor_simulator.py --num-greenhouses 1 --plants 3 --interval 5
```

---

## Terminal 4 — Firebase Sync
```bash
cd /mnt/c/Users/molar/Green_house_project
source venv/bin/activate
python3 firebase_sync/firebase_sync.py \
    --credentials green-house-d7b7f-firebase-adminsdk-fbsvc-bf0cb07c7c.json \
    --firebase-url https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app \
    --greenhouse-ids 1
```

---

## Terminal 5 — Dashboard webszerver
```bash
cd /mnt/c/Users/molar/Green_house_project
python3 -m http.server 8000
```
Böngészőben: `http://localhost:8000/dashboard/index.html`

---

## Raspberry Pi (plant 1)
```bash
python3 sensors/rpi_sensor_reader.py \
    --host <WSL_IP> \
    --greenhouse-id 1 \
    --plant-id 1 \
    --interval 5
```
WSL IP lekérdezése: `hostname -I | awk '{print $1}'`

---

## MQTT ellenőrzés (opcionális)
```bash
mosquitto_sub -h localhost -t 'greenhouse/#' -v
```

---

## Megjegyzések
- A broker újraindítása előtt: `sudo pkill mosquitto`
- RT controller sudo nélkül is fut, de SCHED_FIFO csak sudo-val aktív
- A szimulátor plant 1 adatait is generálja — ha az RPi fut, azokat felülírja
