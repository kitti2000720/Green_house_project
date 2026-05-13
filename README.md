# Greenhouse Automation System

Real-time greenhouse monitoring and control system. Sensor nodes publish data over MQTT, a C real-time controller evaluates rules and sends actuator commands, a web dashboard displays live data and allows manual overrides, and Firebase stores all events.

## Architecture

```
Sensor nodes (RPi / Simulator)
        │  sensor data (MQTT)
        ▼
   MQTT Broker (Mosquitto)
        │
        ├──► RT Controller (C, SCHED_FIFO, 100ms)
        │         │  actuator commands (MQTT, retained)
        │         ▼
        │    Simulator dynamics update
        │
        ├──► Firebase Sync  →  Firebase Realtime DB
        └──► Dashboard      →  browser (live WebSocket)
```

## Components

| Component | Language | Description |
|---|---|---|
| `rt_controller/` | C | Periodic control loop, SCHED_FIFO, 100 ms cycle, jitter monitoring |
| `sensors/sensor_simulator.py` | Python | Multi-greenhouse plant node simulator |
| `sensors/rpi_sensor_reader.py` | Python | Raspberry Pi sensor reader (Sense HAT + simulation fallback) |
| `sensors/dynamics.py` | Python | Physics model shared by simulator and RPi fallback |
| `firebase_sync/firebase_sync.py` | Python | MQTT to Firebase Realtime DB bridge |
| `dashboard/index.html` | HTML/JS | Live dashboard with MQTT WebSocket and manual controls |

## Quick Start

```bash
# From WSL
bash start.sh
```
Open: `http://localhost:8000/dashboard/index.html`

## MQTT Topics

```
greenhouse/{id}/plant/{id}/temp        sensor
greenhouse/{id}/plant/{id}/humidity    sensor
greenhouse/{id}/plant/{id}/co2         sensor
greenhouse/{id}/plant/{id}/soil        sensor
greenhouse/{id}/plant/{id}/pump        actuator  ON | OFF
greenhouse/{id}/window                 actuator  OPEN | CLOSED
greenhouse/{id}/co2_enricher           actuator  ON | OFF
greenhouse/{id}/status/alarm           status    CRITICAL | OK
```

## Control Rules

| Actuator | Turns ON | Turns OFF |
|---|---|---|
| Pump | soil < 30% | soil ≥ 55% |
| Window | temp > 30 °C or CO2 > 1200 ppm | temp ≤ 25 °C and CO2 < 900 ppm |
| CO2 Enricher | CO2 < 600 ppm (window closed) | CO2 ≥ 900 ppm or window opens |
| Alarm | CO2 > 1500 ppm | CO2 ≤ 1500 ppm |

## Requirements

**RT Controller**
```bash
sudo apt install gcc make libmosquitto-dev
cd rt_controller && make
```

**Python components**
```bash
pip install paho-mqtt firebase-admin
```

**Raspberry Pi**
```bash
sudo apt install python3-sense-hat
python3 -m venv --system-site-packages venv
venv/bin/pip install paho-mqtt
```
