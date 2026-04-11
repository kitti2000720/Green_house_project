# Greenhouse rendszer indítása

## Architektúra gyorsan

```
Raspberry Pi (1 db / növény)          WSL2 / Linux
  DHT22  --> temp, humidity    -->  MQTT Broker (Mosquitto)
  ADS1115--> soil moisture     -->     |
  MH-Z19 --> co2               -->     +-- RT Controller (C)  --> pump / window / alarm
                                        +-- Firebase Sync      --> Firebase DB
                                        +-- Dashboard          --> böngésző
```

**MQTT topic struktúra:**
```
greenhouse/{id}/plant/{plant_id}/temp
greenhouse/{id}/plant/{plant_id}/humidity
greenhouse/{id}/plant/{plant_id}/co2
greenhouse/{id}/plant/{plant_id}/soil
greenhouse/{id}/plant/{plant_id}/pump      (aktuátor)
greenhouse/{id}/actuators/window           (aktuátor)
greenhouse/{id}/status/alarm
```

---

## Előfeltételek (WSL2 / Ubuntu)

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients \
                   build-essential libmosquitto-dev \
                   python3 python3-pip python3-venv
```

Ellenőrzés:
```bash
mosquitto --version
gcc --version
python3 --version
```

---

## 1. Python csomagok telepítése

```bash
cd ~/Green_house_project

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install paho-mqtt firebase-admin
```

---

## 2. C controller fordítása

```bash
cd rt_controller
make
cd ..
```

Sikeres fordítás eredménye: `rt_controller/greenhouse_controller` bináris.

Ha hibát kapsz (`mqtt.h: No such file`):
```bash
sudo apt install libmosquitto-dev
```

---

## 3. Rendszer indítása (szimulátor módban)

Minden komponens **külön terminálban** fut. Nyiss 4 terminált WSL-ben.

### Terminal 1 - MQTT Broker
```bash
cd ~/Green_house_project
mosquitto -c config/mosquitto.conf -v
```

Várt kimenet:
```
Opening ipv4 listen socket on port 1883.
Opening ipv4 listen socket on port 9001.
```

---

### Terminal 2 - Szenzor szimulátor (2 greenhouse, 3 növény mindegyikben)
```bash
cd ~/Green_house_project
source venv/bin/activate
python3 sensors/sensor_simulator.py --num-greenhouses 2 --plants 3 --interval 5
```

Egyéb lehetőségek:
```bash
# Csak 1 greenhouse, 4 növény
python3 sensors/sensor_simulator.py --num-greenhouses 1 --plants 4

# Konkrét greenhouse ID-kkal
python3 sensors/sensor_simulator.py --greenhouse-ids 1,3 --plants 3
```

---

### Terminal 3 - RT Controller (1 greenhouse-hoz)
```bash
cd ~/Green_house_project/rt_controller
sudo ./greenhouse_controller --greenhouse-id 1
```

Ha sudo nélkül akarod futtatni (valós idejű ütemezés nélkül):
```bash
./greenhouse_controller --greenhouse-id 1
```

Várt kimenet:
```
=== Greenhouse RT-Controller (greenhouse_id=1) ===
[MQTT] Connected (greenhouse_id=1)
[MQTT] Subscribed: greenhouse/1/plant/+/soil
[MQTT] Subscribed: greenhouse/1/plant/+/temp
[MQTT] Subscribed: greenhouse/1/plant/+/co2
```

---

### Terminal 4 - Firebase Sync

**DEMO mód** (Firebase nélkül, csak logolás):
```bash
cd ~/Green_house_project
source venv/bin/activate
python3 firebase_sync/firebase_sync.py --greenhouse-ids 1,2
```

**LIVE mód** (valódi Firebase-be ír):
```bash
python3 firebase_sync/firebase_sync.py \
    --credentials green-house-d7b7f-firebase-adminsdk-fbsvc-bf0cb07c7c.json \
    --firebase-url https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app \
    --greenhouse-ids 1,2
```

---

### Dashboard - böngészőben

```bash
cd ~/Green_house_project
python3 -m http.server 8000
```

Majd böngészőben (Windows-on):
```
http://localhost:8000/dashboard/index.html
```

A dashboard automatikusan csatlakozik az MQTT brokerhez (WebSocket port 9001).
Ha a broker nem elérhető, szimulációs módra vált.

---

## 4. Valódi Raspberry Pi indítása

Minden RPi-n futtasd (a megfelelő ID-kkal):

```bash
# Telepítés RPi-n:
pip install paho-mqtt Adafruit-DHT adafruit-circuitpython-ads1x15 RPi.GPIO mh-z19

# Indítás (greenhouse 1, plant 2):
python3 sensors/rpi_sensor_reader.py \
    --host <WSL_IP_CIME> \
    --greenhouse-id 1 \
    --plant-id 2 \
    --interval 5
```

WSL IP cím lekérdezése (WSL-ben):
```bash
hostname -I | awk '{print $1}'
```

---

## 5. MQTT üzenetek ellenőrzése

```bash
# Minden üzenet
mosquitto_sub -h localhost -t 'greenhouse/#' -v

# Csak 1 greenhouse
mosquitto_sub -h localhost -t 'greenhouse/1/#' -v

# Manuális pump vezérlés
mosquitto_pub -h localhost -t 'greenhouse/1/plant/1/pump' -m 'ON'
mosquitto_pub -h localhost -t 'greenhouse/1/actuators/window' -m 'OPEN'
```

---

## 6. Firebase adatok ellenőrzése

1. Nyisd meg: https://console.firebase.google.com/
2. Projekt: `green-house-d7b7f`
3. Build > Realtime Database
4. Az adatok 5-10 másodpercenként frissülnek

Firebase adatstruktúra:
```
greenhouse/
  1/
    latest/
      greenhouse/1/plant/1/temp:  { value: "23", timestamp: "..." }
      greenhouse/1/plant/1/soil:  { value: "45", timestamp: "..." }
    events/
      1705750245000: { topic: "...", value: "23", timestamp: "..." }
```

---

## Gyors hibaelhárítás

| Hiba | Megoldás |
|------|----------|
| `Connection refused` (MQTT) | Ellenőrizd, hogy fut-e a mosquitto (Terminal 1) |
| `Permission denied` (RT controller) | Futtasd `sudo`-val, vagy hagyd el a sudo-t |
| `mqtt.h: No such file` (fordítás) | `sudo apt install libmosquitto-dev` |
| Dashboard nem tölt be adatot | Ellenőrizd a mosquitto.conf-ban a WebSocket listener port 9001-et |
| Firebase: `Permission denied` | Firebase Console > Realtime Database > Rules > test mode |
| RPi nem csatlakozik | Ellenőrizd a `--host` paramétert (WSL IP kell, nem localhost) |
