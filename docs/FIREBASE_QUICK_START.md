# 🔥 Firebase Quick Start (5 percben)

## 🌱 Projekt Adatbázis

**Database URL:**
```
https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app/
```

## Lépés 1: Firebase Projekt

1. Nyisd meg: https://console.firebase.google.com/
2. Kattints: **"Create Project"**
3. Név: `greenhouse-project`
4. Kattints: **"Continue"** → **"Create Project"** → Várd meg

## Lépés 2: Realtime Database

1. Bal oldal: **"Build"** → **"Realtime Database"**
2. Kattints: **"Create Database"**
3. Régió: **"Europe-west1"** (az EU-hoz)
4. Security: **"Start in test mode"** (fejlesztéshez)
5. Kattints: **"Enable"**

## Lépés 3: Szolgáltatási Kulcs Letöltése

1. Bal oldal: Fogaskerék ikon (Project settings)
2. Tab: **"Service Accounts"**
3. Gomb: **"Generate a new private key"**
4. Kattints: **"Generate key"**
5. **JSON fájl letöltődik** (mentsd meg!)

## Lépés 4: Python Projekt Beállítása

```bash
# 1. Másolj a letöltött fájlt
cp ~/Downloads/greenhouse-*-key.json ~/Beadando/config/firebase-credentials.json

# 2. Firebase SDK telepítése
pip install firebase-admin

# 3. Indítás Firebase-szel
python3 firebase_sync.py --credentials config/firebase-credentials.json
```

## Ellenőrzés

### Firebase Console-ban

1. https://console.firebase.google.com/ megnyitása
2. Projekt kiválasztása
3. **"Realtime Database"** tab
4. Adat él jelenjen meg 5-10 másodpercenként ✅

### Python Output-ban

```
[Firebase] ✅ Connected to Firebase
[Firebase] Database: https://greenhouse-project.firebaseio.com
[Firebase] Sync service running [LIVE ✅]
```

## Demo Vs. Live

| Jellemző | DEMO 🔄 | LIVE ✅ |
|----------|--------|-------|
| Működik firebase nélkül | ✅ | ❌ |
| Adat mentése | ❌ | ✅ |
| Bejelentkezés | Nincs | Szükséges |
| Parancs | `python3 firebase_sync.py` | `python3 firebase_sync.py --credentials config/firebase-credentials.json` |

## Hibaelhárítás

### "ModuleNotFoundError: firebase_admin"
```bash
pip install firebase-admin
```

### "Permission denied" Firebase Database
- Firebase Console → **Rules**
- Legyen: "test mode" (olvasható/írható mindenkinek)
- Publish

### Adat nem szinkronizálódik
```bash
# Ellenőrizd MQTT üzeneteket
mosquitto_sub -h localhost -t 'greenhouse/#' -v
```

## Teljes Workflow

```bash
# Terminal 1 - MQTT Broker
mosquitto -c config/mosquitto.conf -v

# Terminal 2 - Szenzor Szimulátor
python3 sensors/sensor_simulator.py

# Terminal 3 - Firebase Sync (LIVE móddal)
python3 firebase_sync.py --credentials config/firebase-credentials.json

# Böngésző
https://console.firebase.google.com/ (adatok jelennek meg ✅)
```

---

**Több infó**: [FIREBASE_SETUP.md](./FIREBASE_SETUP.md)
