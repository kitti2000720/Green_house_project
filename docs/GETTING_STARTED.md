# 🚀 RENDSZER INDÍTÁSA (3 variáció)

## 1️⃣ Leggyorsabb Mód (Automatikus, Linux/WSL)

```bash
cd ~/Beadando
chmod +x quickstart.sh
./quickstart.sh
```

Ez automatikusan elindítja:
- ✅ MQTT Broker
- ✅ Szenzor Szimulátor
- ✅ RT Controller
- ✅ Firebase Sync (DEMO móddal)

---

## 2️⃣ Kézi Mód (5 terminál, szétválasztva)

**Terminal 1 - MQTT Broker:**
```bash
mosquitto -c ~/.mosquitto/mosquitto.conf -v
```
Wait for: `mosquitto version X.X ready`

**Terminal 2 - Szenzor Szimulátor:**
```bash
cd ~/Beadando
python3 sensors/sensor_simulator.py
```
Wait for: `[Sensors] Connected to MQTT broker`

**Terminal 3 - RT Controller:**
```bash
cd ~/Beadando/rt_controller
sudo ./greenhouse_controller
```
Wait for: `[RT-Controller] System running`

**Terminal 4 - Firebase Sync (DEMO):**
```bash
cd ~/Beadando
python3 firebase_sync/firebase_sync.py
```
Output: `[Firebase] Sync service running [DEMO 🔄]`

**Terminal 5 - Web Dashboard:**
```bash
cd ~/Beadando
python3 -m http.server 8000
```
Nyisd meg: http://localhost:8000/dashboard/index.html

---

## 3️⃣ Firebase Sync LIVE Móddal

**🌱 Firebase Adatbázis:**
```
https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app/
```

**Előfeltételek:**
1. Firebase projekt létrehozása (https://console.firebase.google.com/)
2. Service Account kulcs letöltése
3. Másolás: `config/firebase-credentials.json`

**Terminal 4 - Firebase Sync (LIVE):**
```bash
cd ~/Beadando
python3 firebase_sync.py --credentials config/firebase-credentials.json
```
Output: `[Firebase] ✅ Connected to Firebase`

Lásd: [FIREBASE_QUICK_START.md](./docs/FIREBASE_QUICK_START.md)

---

## ✅ Ellenőrzési Lépések

### 1. Minden komponens fut?
```bash
# Másik terminálban
ps aux | grep -E "mosquitto|sensor_simulator|greenhouse_controller|firebase_sync"
```

### 2. MQTT üzenetek küldenek?
```bash
mosquitto_sub -h localhost -t 'greenhouse/#' -v
```

Látnod kellene:
```
greenhouse/1/env/temp 23
greenhouse/1/env/humidity 65
greenhouse/1/plant/1/soil 50
...
```

### 3. Dashboard működik?
- Nyisd meg: http://localhost:8000/dashboard/index.html
- Valós szenzor adatok jelenjenek meg ✅
- Zöld kapcsolatjelző ✅

### 4. Firebase (ha bekapcsolt)
- https://console.firebase.google.com/
- Projekt kiválasztása
- "Realtime Database" tabban adat jelenjen meg

---

## 🎯 Teljes Teszt Scenario

```bash
# 1. Összes komponens indítása
./quickstart.sh

# 2. Új terminálban - talajnedvesség csökkentése (teszt)
# Várj, míg talajnedvesség < 30%
# Az RT Controller automatikusan bekapcsolja a szivattyút

# 3. Manuális teszt
mosquitto_pub -h localhost -t 'greenhouse/1/plant/1/pump' -m 'ON'

# 4. Figyeld az eredményt
mosquitto_sub -h localhost -t 'greenhouse/#' -v
# Az 1. növény nedvessége nőjön

# 5. Dashboard
# http://localhost:8000/dashboard/index.html
# Összesen frissüljenek az adatok
```

---

## 💡 Parancsok Gyorslista

| Parancs | Mit csinál |
|---------|-----------|
| `./quickstart.sh` | Az összes komponens indítása |
| `mosquitto_sub -h localhost -t greenhouse/#` | MQTT üzenetek figyelése |
| `mosquitto_pub -h localhost -t greenhouse/1/plant/1/pump -m ON` | Szivattyú bekapcsolása |
| `pkill mosquitto` | MQTT Broker leállítása |
| `pkill -f sensor_simulator` | Szenzor szimulátor leállítása |
| `ps aux \| grep greenhouse` | Futó komponensek listázása |
| `python3 -m http.server 8000` | Web szerver indítása |

---

## 🔧 Troubleshooting

**MQTT Broker nem indul:**
```bash
sudo lsof -i :1883  # Foglalt port?
pkill mosquitto
mosquitto -c ~/.mosquitto/mosquitto.conf -v
```

**Python modul hiba:**
```bash
pip install paho-mqtt firebase-admin
```

**C Program nem fut:**
```bash
cd rt_controller
make clean && make
sudo ./greenhouse_controller
```

**Dashboard nem frissül:**
- F12 debugger ellenőrzés
- MQTT szenzor ellenőrzés: `mosquitto_sub -h localhost -t greenhouse/#`
- Böngésző cache törlés (Ctrl+Shift+Delete)

---

## 📊 Komponens Státusz Dashboard

```
✅ MQTT Broker          - localhost:1883
✅ Szenzor Simulator    - Adatokat küld
✅ RT Controller        - Szabályokat végrehajt
✅ Firebase Sync        - DEMO vagy LIVE
✅ Web Dashboard        - http://localhost:8000
```

---

## 🎓 Következő Lépések

1. **Firebase beállítása**: [FIREBASE_QUICK_START.md](./docs/FIREBASE_QUICK_START.md)
2. **Telepítési útmutató**: [INSTALLATION.md](./docs/INSTALLATION.md)
3. **Teljes dokumentáció**: [README.md](./README.md)

---

**Kérdés?** Lásd a [INSTALLATION.md](./docs/INSTALLATION.md) Troubleshooting szekciót.
