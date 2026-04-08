# 📚 Dokumentáció Index

## 🚀 Gyors Kezdés (Olvasd el ELŐSZÖR!)

1. **[GETTING_STARTED.md](./docs/GETTING_STARTED.md)** - 3 Indítási mód
   - Automatikus indítás (`./quickstart.sh`)
   - Kézi indítás (5 terminál)
   - Firebase integrációval

2. **[PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)** - Projekt Overview
   - Komponensek leírása
   - Architektúra diagram
   - Megvalósított végpontok

---

## 📖 Teljes Dokumentáció

### Teljes Dokumentáció

### Telepítés & Konfigurálás
- **[INSTALLATION.md](./INSTALLATION.md)** - Részletes telepítési útmutató
  - WSL2 + Ubuntu beállítás
  - Függőségek telepítése
  - Komponensek fordítása
  - Hibaelhárítás

- **[RASPBERRY_PI_SETUP.md](./RASPBERRY_PI_SETUP.md)** - 🍓 Raspberry Pi valós szenzorok
  - DHT22 hőmérséklet szenzor
  - ADS1115 talajnedvesség-mérő
  - I2C csatlakoztatás
  - Systemd service setup

### Firebase Cloud Szinkronizálás
- **[FIREBASE_SETUP.md](./docs/FIREBASE_SETUP.md)** - Teljes Firebase dokumentáció
  - Firebase projekt létrehozása
  - Service Account kulcs letöltése
  - Python integrálás
  - Security Rules beállítás

- **[FIREBASE_QUICK_START.md](./docs/FIREBASE_QUICK_START.md)** - Firebase 5 perc alatt
  - Gyors projekt setup
  - Adat ellenőrzése
  - Troubleshooting

### Technikai Dokumentáció
- **[README.md](./README.md)** - Teljes technikai referencia
  - Rendszer architektúra
  - MQTT topic szerkezet
  - Real-time teljesítmény
  - Skalálhatóság
  - Hibaellátás
  - Komponens részletek

---

## 🗂️ Projekt Szerkezet

```
Beadando/
├── 📄 README.md                         ← Teljes dokumentáció
├── 📄 PROJECT_SUMMARY.md                ← Projekt összefoglalás
├── 📄 requirements.txt                  ← Python függőségek
├── 📄 Makefile                          ← Build rendszer
├── 🔧 quickstart.sh                     ← Automatikus indítás
├── ✅ verify_setup.sh                   ← Rendszer ellenőrzés
│
├── 📁 docs/
│   ├── 🚀 GETTING_STARTED.md            ← Itt KEZDJ (3 indítási mód)
│   ├── 📖 INSTALLATION.md               ← Teljes telepítés
│   ├── 🔥 FIREBASE_SETUP.md             ← Firebase config
│   ├── ⚡ FIREBASE_QUICK_START.md       ← Firebase 5 min
│   └── 📋 (ez az index)
│
├── 📁 rt_controller/
│   ├── 🔧 greenhouse_controller.c       ← Real-time C kód
│   └── Makefile                         ← C fordítás
│
├── 📁 sensors/
│   └── 🌡️  sensor_simulator.py          ← Szenzor szimuláció
│
├── 📁 firebase_sync/
│   └── ☁️  firebase_sync.py             ← Felhő szinkronizálás
│
├── 📁 dashboard/
│   └── 🎨 index.html                    ← Web felület
│
└── 📁 config/
    ├── 🔌 mosquitto.conf                ← MQTT broker config
    ├── 🔐 firebase-credentials.json     ← Firebase kulcs (opcionális)
    └── 📄 firebase-schema-example.json  ← Adat séma
```

---

## 🎯 Olvasási Sorrendje

### Felhasználók (Üzemeltetés)
1. ✅ `GETTING_STARTED.md` - Indítás
2. ✅ `PROJECT_SUMMARY.md` - Mi az ez?
3. ✅ `INSTALLATION.md` - Teljes telepítés (ha szükséges)

### Fejlesztők (Kód módosítás)
1. ✅ `README.md` - Architektura
2. ✅ Komponens fájlok (`.c`, `.py`)
3. ✅ `INSTALLATION.md` - Fordítás & teszt

### DevOps (Felhő deployment)
1. ✅ `FIREBASE_SETUP.md` - Firebase projekt
2. ✅ `FIREBASE_QUICK_START.md` - Gyors config
3. ✅ `GETTING_STARTED.md` - Indítás Firebase-szel

---

## 📊 Komponens Dokumentáció

### 1. Real-Time C Controller
- **Fajl**: `rt_controller/greenhouse_controller.c`
- **Dokumentáció**: `README.md` → "Real-Time C component"
- **Fordítás**: `make -C rt_controller`
- **Indítás**: `sudo ./rt_controller/greenhouse_controller`

### 2. Szenzor Szimulátor
- **Fajl**: `sensors/sensor_simulator.py`
- **Dokumentáció**: `README.md` → "Sensor Simulator"
- **Indítás**: `python3 sensors/sensor_simulator.py`

### 3. MQTT Broker
- **Config**: `config/mosquitto.conf`
- **Dokumentáció**: `INSTALLATION.md` → "Configure MQTT Broker"
- **Indítás**: `mosquitto -c config/mosquitto.conf -v`

### 4. Firebase Sync
- **Fajl**: `firebase_sync/firebase_sync.py`
- **Dokumentáció**: 
  - Demo mód: `README.md`
  - Teljes Firebase: `FIREBASE_SETUP.md`
- **Indítás**: 
  - Demo: `python3 firebase_sync/firebase_sync.py`
  - Live: `python3 firebase_sync/firebase_sync.py --credentials config/firebase-credentials.json`

### 5. Web Dashboard
- **Fajl**: `dashboard/index.html`
- **Dokumentáció**: `README.md` → "Web Dashboard"
- **Indítás**: `python3 -m http.server 8000`
- **URL**: `http://localhost:8000/dashboard/index.html`

---

## ❓ FAQ / Gyakori Kérdések

### Hol kezdjem?
→ Nyisd meg: [GETTING_STARTED.md](./docs/GETTING_STARTED.md)

### Hogyan indítsam el a rendszert?
→ Futtass: `./quickstart.sh`

### Hogyan ellenőrizze, hogy minden működik?
→ Futtass: `./verify_setup.sh`

### Hogyan állítsam be a Firebase-t?
→ Lásd: [FIREBASE_QUICK_START.md](./docs/FIREBASE_QUICK_START.md)

### Hol van a teljes dokumentáció?
→ Lásd: [README.md](./README.md)

### Hogyan lehet megjavítani az eszközöket?
→ Lásd: [INSTALLATION.md](./docs/INSTALLATION.md) → Troubleshooting

### Mi történik ha hibám van?
→ `grep -r "ERROR\|WARNING" /tmp/` (naplók)

### Hogyan lehet a kódot módosítani?
→ 1. Megváltoztatod a forráskódot (`.c`, `.py`)
→ 2. Módosít: `make -C rt_controller` (C kódnál)
→ 3. Újraindít: `./quickstart.sh`

---

## 📈 Fejlődési Térkép

| Szakasz | Státusz | Dokumentáció |
|---------|---------|--------------|
| 🟢 Beállítás | Kész | INSTALLATION.md |
| 🟢 Indítás | Kész | GETTING_STARTED.md |
| 🟢 Alapható | Kész | README.md |
| 🟢 Firebase | Kész | FIREBASE_*.md |
| 🟡 Deployment | Terv | (hamarosan) |
| 🟡 Monitoring | Terv | (hamarosan) |
| 🔴 Mobil app | Terv | (hamarosan) |

---

## 🔗 Hivatkozások

### Külső Dokumentáció
- **MQTT**: https://mqtt.org/
- **Mosquitto**: https://mosquitto.org/documentation/
- **Firebase**: https://firebase.google.com/docs/realtime-database
- **Linux RT**: https://wiki.linuxfoundation.org/realtime/

### Kódmodulink
- **paho-mqtt Python**: https://github.com/eclipse/paho.mqtt.python
- **firebase-admin Python**: https://github.com/firebase/firebase-admin-python
- **libmosquitto C**: https://mosquitto.org/api/c/

---

## ✅ Végzettségi Értékelés

Mindenemez általi tanulás:

| Tanulási Eredmény | Dokumentáció |
|------------------|--------------|
| Real-time Linux programozás | README.md + rt_controller/ |
| IoT MQTT kommunikáció | INSTALLATION.md + README.md |
| Szenzor adatkezelés | sensors/ + README.md |
| Felhő integrálás | FIREBASE_*.md |
| Web fejlesztés | dashboard/ + README.md |
| Rendszer design | PROJECT_SUMMARY.md |
| Teljes szoftverstack | GETTING_STARTED.md |

---

## 🤝 Csapat Szerepek

Javasolt felosztás egy 2-3 fős csapatban:

| Szerepkör | Felelősség | Dokumentáció |
|----------|----------|--------------|
| **Real-Time Dev** | C kód, MQTT logika | rt_controller/ + README.md |
| **Cloud Dev** | Firebase, Python | firebase_sync/ + FIREBASE_*.md |
| **Frontend Dev** | Dashboard, UI/UX | dashboard/ + README.md |
| **DevOps/Lead** | Telepítés, integrálás | INSTALLATION.md + GETTING_STARTED.md |

---

## 📞 Támogatás

**Hibaelhárítás lépcsői:**

1. Olvasd el: `GETTING_STARTED.md`
2. Futtass: `./verify_setup.sh`
3. Ellenőrizd: MQTT üzenetek (`mosquitto_sub -h localhost -t greenhouse/#`)
4. Nézd meg: Naplók (`/tmp/mosquitto.log`, `/tmp/sensor_sim.log`)
5. Lásd: `INSTALLATION.md` → Troubleshooting

---

**Utolsó frissítés:** 2026-04-08  
**Verzió:** 1.0  
**Státusz:** ✅ Üzemkész
