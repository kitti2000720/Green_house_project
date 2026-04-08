# Firebase Cloud Setup Guide

## Áttekintés

A rendszer szenzor adatait **Firebase Realtime Database**-be szinkronizálja. Ez lehetővé teszi:
- 🌍 Felhőbeli adat tárolást
- 📊 Történeti adatok megtekintését
- 📱 Mobil alkalmazás fejlesztést
- 🔐 Biztonságos adat elérést

## 🌱 Production Database URL

```
https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app/
```

---

## Firebase Project Létrehozása

### Lépés 1: Firebase Console Megnyitása

1. Nyisd meg: https://console.firebase.google.com/
2. Bejelentkezés Google fiókkal (ha szükséges, regisztrálj)

### Lépés 2: Új Projekt Létrehozása

1. Kattints **"Create Project"** gombra
2. Projekt név: `greenhouse-project` (vagy saját név)
3. Kattints **"Continue"**

### Lépés 3: Google Analytics Engedélyezése (Opcionális)

- Válaszd: **"Enable Google Analytics [optional]"**
- Kattints **"Create Project"**
- Várj a projekt initialization-ra (~1-2 perc)

### Lépés 4: Realtime Database Aktiválása

1. A bal oldali menüben, válaszd: **"Build"** → **"Realtime Database"**
2. Kattints **"Create Database"**
3. Válaszd az adatbázis helyét (pl. **Europe-west1**)
4. **Security rules:** Válaszd **"Start in test mode"** (csak fejlesztéshez!)
5. Kattints **"Enable"**

### Lépés 5: Szolgáltatási Fiók Kulcs Letöltése

Ezzel a Python alkalmazás hitelesíthetik magát:

1. Bal oldali menü: **"Project settings"** (fogaskerék ikon) → **"Service Accounts"**
2. Kattints **"Generate a new private key"**
3. Kattints **"Generate key"**
4. **JSON fájl automatikusan letöltődik**

⚠️ **WICHTIG**: Tartsd ezt a fájlt biztonságban! NEM public repo-ba!

---

## Python Beállítása

### 1. Szükséges Csomag Telepítése

```bash
pip install firebase-admin
```

### 2. Letöltött Kulcs Másolása

A letöltött JSON fájlt másold a projekt mappába:

```bash
# Windows/WSL
cp ~/Downloads/greenhouse-project-XXXXX.json ~/Beadando/config/firebase-credentials.json
```

### 3. Ellenőrzés

```bash
ls -la config/firebase-credentials.json
```

---

## Firebase Sync Indítása

### Demo Mód (Jelenlegi)

Jelenleg **demo módban** fut (csak konzolon naplózás):

```bash
cd ~/Beadando
python3 firebase_sync/firebase_sync.py
```

### Teljes Firebase Szinkronizáció

Hitelesítési kulccsal:

```bash
cd ~/Beadando
python3 firebase_sync/firebase_sync.py \
    --credentials config/firebase-credentials.json \
    --greenhouse-id 1
```

---

## Adat Ellenőrzése Firebase Console-ban

### 1. Firebase Konzol Megnyitása

Menj: https://console.firebase.google.com/ → Projekt kiválasztása

### 2. Realtime Database Tab

Bal oldali menü: **"Build"** → **"Realtime Database"**

### 3. Adat Szerkesztő

Látod az adat hierarchiát:

```
greenhouse/
  └─ 1/
      ├── latest/
      │   ├── greenhouse/1/env/temp
      │   ├── greenhouse/1/env/humidity
      │   └── ...
      └── events/
          ├── 1723456789000/
          │   ├── timestamp
          │   ├── value
          │   └── topic
          ├── 1723456790000/
          └── ...
```

### 4. Valós Idejű Frissítések

Ahogy az adatok érkeznek, életben frissülnek:
- ✅ "latest" csomópont mutatja az utolsó értékeket
- ✅ "events" csomópont tárja el a történetet

---

## Security Rules (Éles Telepítéshez)

### Teszt Mód (Jelenlegi - CSAK FEJLESZTÉSHEZ!)

```json
{
  "rules": {
    ".read": true,
    ".write": true
  }
}
```

⚠️ **Bárki olvashat/írhat!** Csak fejlesztéshez.

### Éles Mód (Production - Biztonságos)

#### Szerkesztés

1. Firebase Console → **Realtime Database**
2. **"Rules"** tab
3. Kódot cseréld:

```json
{
  "rules": {
    "greenhouse": {
      "$greenhouse_id": {
        ".read": true,
        ".write": "root.child('authorized_ids').child($greenhouse_id).val() === auth.uid",
        "latest": {
          ".read": true,
          ".write": "root.child('authorized_users').child(auth.uid).val() === true"
        },
        "events": {
          ".read": true,
          ".write": "root.child('authorized_users').child(auth.uid).val() === true",
          "$event_id": {
            ".validate": "newData.hasChildren(['timestamp', 'value', 'topic'])"
          }
        }
      }
    }
  }
}
```

4. Kattints **"Publish"**

### Felhasználók Hozzáadása

Authentication beállítása:

1. Bal oldali menü: **"Build"** → **"Authentication"**
2. Kattints **"Get started"**
3. Kattints **"Email/Password"** provider
4. Engedélyezd és mentsd
5. **"Users"** tabban add hozzá a felhasználókat

---

## Python Firebase Integration

### Firebase Credentials Beállítása

Automatikus bejelentkezés:

```python
import firebase_admin
from firebase_admin import credentials, db

# Hitelesítés
cred = credentials.Certificate('config/firebase-credentials.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://greenhouse-project.firebaseio.com'
})

# Adat írása
ref = db.reference('greenhouse/1/latest')
ref.set({
    'temp': 23.5,
    'humidity': 65,
    'timestamp': '2024-01-20T10:30:00'
})

# Adat olvasása
data = ref.get()
print(data)
```

### Python Script Futtatása

A `firebase_sync.py` automatikusan:

1. Csatlakozik MQTT brokerhez
2. Feliratkozik az összes topic-ra
3. Szinkronizálja az adatokat Firebase-be

```bash
python3 firebase_sync/firebase_sync.py \
    --credentials config/firebase-credentials.json \
    --greenhouse-id 1
```

---

## Telemonitoring - Web Alkalmazás

### Lehet Firebase Hosting-ot használni

#### 1. Firebase CLI Telepítése

```bash
npm install -g firebase-tools
```

#### 2. Bejelentkezés

```bash
firebase login
```

#### 3. Dashboard Üzembe helyezése

```bash
cd ~/Beadando
firebase init hosting
# Válaszd: 
# - public directory: dashboard
# - Single page app: N
# - Overwrite index.html: N

firebase deploy
```

#### 4. Közvetlenül Elérhető

```
https://greenhouse-project.web.app/index.html
```

---

## Adatok Megjelenítése a Dashboardban

### Firebase Realtime Listener

```javascript
// index.html-be hozzáadni:

<script src="https://www.gstatic.com/firebasejs/9.0.0/firebase-app.js"></script>
<script src="https://www.gstatic.com/firebasejs/9.0.0/firebase-database.js"></script>

<script>
  // Firebase Config (PROJECT SETTINGS-ből)
  const firebaseConfig = {
    apiKey: "AIzaSy...",
    authDomain: "greenhouse-project.firebaseapp.com",
    databaseURL: "https://greenhouse-project.firebaseio.com",
    projectId: "greenhouse-project",
    storageBucket: "greenhouse-project.appspot.com",
    messagingSenderId: "...",
    appId: "..."
  };

  // Initialize Firebase
  firebase.initializeApp(firebaseConfig);
  const db = firebase.database();

  // Valós idejű adatok
  db.ref('greenhouse/1/latest').on('value', (snapshot) => {
    const data = snapshot.val();
    console.log('Realtime data:', data);
    
    // Dashboard frissítése
    document.getElementById('tempValue').textContent = data.temp;
    document.getElementById('humidityValue').textContent = data.humidity;
  });
</script>
```

---

## Ellenőrzési Lépések

### 1. Firebase Console - Adat Szinkronizáció

```bash
# Terminal 1: MQTT Broker
mosquitto -c ~/.mosquitto/mosquitto.conf -v

# Terminal 2: Szenzor
python3 sensors/sensor_simulator.py

# Terminal 3: Firebase Sync
python3 firebase_sync/firebase_sync.py \
    --credentials config/firebase-credentials.json
```

### 2. Firebase Console Megnyitása

- https://console.firebase.google.com/
- Realtime Database → nyomj F5 néhányszor
- Látod az adatok jelenését

### 3. Utolsó Értékek Ellenőrzése

```bash
# WSL-ben
curl -X GET 'https://greenhouse-project.firebaseio.com/greenhouse/1/latest.json'
```

Kimenet:
```json
{
  "temp": 23.5,
  "humidity": 65.2,
  "co2": 850,
  "timestamp": "2024-01-20T10:30:45.123456Z"
}
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'firebase_admin'"

```bash
pip install firebase-admin
```

### "Permission denied" - Firebase Adatbázis

1. Firebase Console → **Realtime Database** → **Rules**
2. Beállítás: "test mode" (minden olvasható/írható)
3. Kattints **Publish**

### "Authentication failed"

1. Ellenőrizd a credentials JSON fájlt: `config/firebase-credentials.json`
2. Legyen a fájl a helyes helyen
3. Jogok: `chmod 600 config/firebase-credentials.json`

### Adat Nem Szinkronizálódik

```bash
# Ellenőrizd Python logot
python3 firebase_sync/firebase_sync.py --credentials ... 2>&1 | head -50

# Szenzor küld-e MQTT üzeneteket?
mosquitto_sub -h localhost -t 'greenhouse/#' -v
```

---

## Megjegyzések

| Komponens | Státusz | Megjegyzés |
|-----------|---------|-----------|
| MQTT Broker | ✅ Video | Lokális, gyors |
| Szenzor Szimulátor | ✅ Teljes | Szimulált adatok |
| RT Controller | ✅ Teljes | Valós idejű döntések |
| Firebase Sync | ✅ **Demo** | Demo módban fut |
| Firebase DB | ✅ Opcionális | Szükséges hitelesítéshez |
| Web Dashboard | ✅ Teljes | Lokális működik |
| Firebase Hosting | ⚠️ Opcionális | Nyilvános eléréséhez |

---

## Teljes Firebase Workflow

```bash
# 1. Projekt létrehozása (egyszer)
# - Firebase Console: https://console.firebase.google.com/
# - Projekt: greenhouse-project
# - Realtime Database: Europe-west1
# - Service Account Key letöltése

# 2. Kulcs másolása
cp ~/Downloads/greenhouse-*-key.json ~/Beadando/config/firebase-credentials.json

# 3. Python csomag
pip install firebase-admin

# 4. Szenzor + Sync indítása
python3 sensors/sensor_simulator.py &
python3 firebase_sync/firebase_sync.py \
    --credentials config/firebase-credentials.json &

# 5. Firebase Console megnyitása
# https://console.firebase.google.com/
# Realtime Database → live adatok jelennek meg

# 6. Dashboard
http://localhost:8000/dashboard/index.html
```

---

**Segítségre van szükséged?** Nézd meg a [INSTALLATION.md](./INSTALLATION.md) fájlt vagy a [README.md](./README.md) fájlt.
