# 🍓 Raspberry Pi Szenzor Integráció

## Áttekintés

A rendszer támogatja a **Raspberry Pi-t** valós szenzoral alapuló adatgyűjtéshez. Ekkor ezt szenzor szimulátor helyett (vagy mellett) használhatod.

## Támogatott Szenzorok

| Szenzor | Típus | Model | Csatlakozás |
|---------|-------|-------|------------|
| 🌡️ Hőmérséklet + Páratartalom | Digital | DHT22 | GPIO (vezeték) |
| 🌱 Talajnedvesség | Analog | Capacitive/Resistive | I2C ADC (ADS1115) |
| 💡 Fény (opcionális) | I2C | TSL2561 | I2C |

## Hardware Szükségletek

### Alapvető
- **Raspberry Pi 4/5** (4GB RAM+ ajánlott)
- **8GB+ SD kártya**
- **5V / 3A tápegység**
- **USB-C kábel**

### Szenzorok
- **DHT22** hőmérsékleti szenzor (alkatrész)
- **Talajnedvesség szenzor** (kapacitív)
- **ADS1115** I2C ADC (analog konverter)
- **Kannaioksi kábel**

## Lépés 1: Raspberry Pi OS Telepítése

### 1. Imager Letöltése
- https://www.raspberrypi.com/software/
- "Raspberry Pi OS (64-bit)" vigyen

### 2. SD Kártya Feltöltése
```bash
# Linux/Mac szerint
sudo dd if=raspberry-pi.img of=/dev/sdX bs=4M

# Vagy használj Imager-t (GUI)
```

### 3. Első Boot
1. SD kártya behelyezése
2. Monitor csatlakoztatása
3. Питание bekapcsolása
4. Username: `pi`, Password: `raspberry` (alapértelmezett)

### 4. Frissítés
```bash
sudo apt update
sudo apt upgrade -y
```

## Lépés 2: Python & MQTT Telepítése

```bash
# Python csomag
sudo apt install -y python3 python3-pip

# MQTT kliens
pip3 install paho-mqtt

# Szenzor könyvtárak
pip3 install Adafruit_DHT
pip3 install adafruit-circuitpython-ads1x15

# GPIO támogatás (ha szükséges)
pip3 install RPi.GPIO
```

## Lépés 3: Szenzor Csatlakoztatása

### DHT22 Csatlakozás

```
DHT22 pin (szennyek)
├─ Pin 1 (VCC) → Raspberry Pi 3.3V (pin 1)
├─ Pin 2 (DATA) → Raspberry Pi GPIO 17 (pin 11)
├─ Pin 3 (NC) → Sem csatlakozás
└─ Pin 4 (GND) → Raspberry Pi GND (pin 9)

Ellenállás: 4.7kΩ DHT22 pin 1 és pin 2 között
```

### ADS1115 ADC Csatlakozás (I2C)

```
ADS1115 I2C ADC Pinout:
├─ VDD → Raspberry Pi 3.3V (pin 1)
├─ GND → Raspberry Pi GND (pin 9)
├─ SCL → Raspberry Pi GPIO 3/SCL (pin 5)
├─ SDA → Raspberry Pi GPIO 2/SDA (pin 3)
└─ ADDR → GND (cím: 0x48)

Talajnedvesség szenzorok:
├─ A0 → Növény 1
├─ A1 → Növény 2
├─ A2 → Növény 3
└─ A3 → Tartalék
```

### Raspberry Pi Pinout Referencia

```
         +3.3V Pin 1
         +5V   Pin 2
GPIO 2   SDA   Pin 3
         GND   Pin 4
GPIO 3   SCL   Pin 5
         GND   Pin 6
GPIO 4   GPIO4 Pin 7
GPIO17   GPIO17 Pin 11  ← DHT22 DATA
         GND   Pin 9
         MOSI  Pin 19
         MISO  Pin 21
         CLK   Pin 23
         CE0   Pin 24
```

## Lépés 4: I2C Engedélyezése (ADS1115-hez)

```bash
# Raspi-config megnyitása
sudo raspi-config

# Menü: Interfacing Options → I2C → Enable
# Kilépés és újraindítás

sudo reboot
```

Ellenőrzés:
```bash
# I2C eszközök listázása
i2cdetect -y 1

# Output (ADS1115 detektálva a 0x48-on):
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:          -- -- -- -- -- -- -- -- -- -- -- -- --
# 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 40: -- -- -- -- -- -- -- -- 48 -- -- -- -- -- -- --
```

## Lépés 5: RPI Szenzor Olvasó Indítása

### Projekt Másolása Raspberry Pi-re

```bash
# A saját számítógépedről
scp -r ~/Beadando pi@raspberrypi.local:~/

# vagy SSH-n keresztül
ssh pi@raspberrypi.local
cd Beadando
```

### Szenzor Olvasó Futtatása

```bash
# Terminal 1: MQTT Broker (szükséges!)
mosquitto -d

# Terminal 2: Raspberry Pi szenzor olvasó
python3 sensors/rpi_sensor_reader.py \
    --mqtt-host raspberrypi.local \
    --mqtt-port 1883 \
    --greenhouse-id 1 \
    --dht-pin 17 \
    --ads-address 0x48 \
    --interval 5
```

### Kimenet (Várt)

```
[RaspberryPi] ✅ DHT22 configured on GPIO 17
[RaspberryPi] ✅ ADS1115 ADC configured (address: 0x48)
[RaspberryPi/MQTT] ✅ Connected to raspberrypi.local:1883

[RaspberryPi] Sensor readings starting (interval: 5s)

📡 greenhouse/1/env/temp = 23°C
📡 greenhouse/1/env/humidity = 65%
📡 greenhouse/1/plant/1/soil = 50%
📡 greenhouse/1/plant/2/soil = 45%
📡 greenhouse/1/plant/3/soil = 55%
```

## Lépés 6: Adat Ellenőrzése

### A fejlesztő gépen (pl. Windows/WSL)

```bash
# Az MQTT adatok figyelése
mosquitto_sub -h raspberrypi.local -t 'greenhouse/#' -v

# Output:
# greenhouse/1/env/temp 23
# greenhouse/1/env/humidity 65
# greenhouse/1/plant/1/soil 50
# ...
```

## Lépés 7: Systemd Service Létrehozása (Automatic Start)

```bash
# Service fájl létrehozása
sudo nano /etc/systemd/system/rpi-sensors.service
```

Tartalom:
```ini
[Unit]
Description=Greenhouse RPI Sensor Reader
After=network.target mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Beadando
ExecStart=/usr/bin/python3 sensors/rpi_sensor_reader.py \
    --mqtt-host localhost \
    --mqtt-port 1883 \
    --greenhouse-id 1 \
    --interval 5
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktiválás:
```bash
# Engedélyezés
sudo systemctl daemon-reload
sudo systemctl enable rpi-sensors.service

# Indítás
sudo systemctl start rpi-sensors.service

# Státusz ellenőrzése
sudo systemctl status rpi-sensors.service

# Naplók
sudo journalctl -u rpi-sensors.service -f
```

## Raspberry Pi vs Szenzor Szimulátor

| Jellemző | RPI Szenzor | Szimulátor |
|----------|-------------|-----------|
| Valós adatok | ✅ | ❌ |
| Hardver szükséglet | ✅ | ❌ |
| Működik bármilyen gépen | ❌ | ✅ |
| Dinamika szimulálás | ❌ | ✅ |
| Indítási idő | ~1 perc | Azonnali |
| Telepítési komplexitás | Magas | Alacsony |

## Hibás Szenzorok Kezelése

### DHT22 nem olvas adatokat

```bash
# 1. Csatlakozás ellenőrzése
gpio readall | grep GPIO17

# 2. Ellenállás ellenőrzése (4.7kΩ)
# 3. DHT22 szikrázás ellenőrzése (új szenzor?)

# 4. Próba egyszer futtatni
python3 -c "
import Adafruit_DHT
h, t = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, 17)
print(f'Temp: {t}°C, Humidity: {h}%')
"
```

### ADS1115 nem detektálható

```bash
# I2C eszközök ellenőrzése
sudo i2cdetect -y 1

# Ha 48 nem jelenik meg:
# 1. U kikapcsolás + újraindítás
# 2. Csatlakozás ellenőrzése (SCL/SDA-hez)
# 3. Cím próbálgatása: 
#    0x48 (alapérték - GND)
#    0x49 (VDD csatlakoztatva)
#    0x4A (SDA csatlakoztatva)
#    0x4B (SCL csatlakoztatva)
```

### MQTT kapcsolat nem működik

```bash
# 1. Mosquitto fut-e?
mosquitto -v

# 2. Raspberry Pi és fejlesztő gép ugyanabban a hálózatban?
ping raspberrypi.local

# 3. Firewall blokkolja-e a 1883-as portot?
sudo ufw allow 1883
```

## Teljes Integrálás: RPI + MQTT + Cloud

### Firebase Adatbázis

**Production Database URL:**
```
https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app/
```

Az összes szenzor adat szinkronizálódik erre az URL-re (Firebase JSON-ban tárolva).

### Teljes workflow

```bash
# Raspberry Pi-n:
# Terminal 1
mosquitto -d

# Terminal 2
python3 sensors/rpi_sensor_reader.py --mqtt-host localhost


# Fejlesztő gépen (Windows/WSL):
# Terminal 1
mosquitto -c config/mosquitto.conf -v

# Terminal 2
cd rt_controller && sudo ./greenhouse_controller

# Terminal 3
# Firebase szinkronizálás (cloud-ba küldi az adatokat)
python3 firebase_sync.py --credentials config/firebase-credentials.json

# Terminal 4
python3 -m http.server 8000
# Dashboard: http://localhost:8000/dashboard/index.html
# Firebase Live: https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app/
```

## Raspberry Pi Ház 3D Nyomtatott Projekt Doboz

Opcionális: 3D nyomtatott ház a komponensekhez
- Thingiverse: "Raspberry Pi greenhouse case"
- vagy DIY: plexiglas doboz

## Teljesítmény Tippek

### Energia megtakarítás
```bash
# Alacsony teljesítmény mód
sudo nano /boot/config.txt
# Hozzáadni: gpu_mem=16, arm_freq=800
```

### Adatok gyorsítása
```bash
# Adatbázis caching
# SQLite cache az MQTT üzenetekhez
```

## Referencia

### Python Könyvtárak
- **Adafruit_DHT**: https://github.com/adafruit/Adafruit_Python_DHT
- **ADS1x15**: https://github.com/adafruit/Adafruit_CircuitPython_ADS1x15
- **paho-mqtt**: https://github.com/eclipse/paho.mqtt.python

### GPIO Pinnout
- https://pinout.xyz/

### Adafruit Tutorials
- DHT22: https://learn.adafruit.com/dht-humidity-sensing-on-raspberry-pi-with-gdrive-logging

---

**Raspberry Pi verzió:** 4 Model B+ vagy 5
**Raspberry Pi OS:** Bullseye/Bookworm (2023+)
**Python:** 3.7+
