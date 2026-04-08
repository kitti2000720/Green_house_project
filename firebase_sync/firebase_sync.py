"""
Firebase Cloud Sync Service - Full Integration
Subscribes to MQTT topics and syncs all events to Firebase Realtime Database
"""

import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Install with: pip install paho-mqtt")
    sys.exit(1)

try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
except ImportError:
    print("WARNING: firebase-admin not installed. Running in DEMO mode.")
    print("Install with: pip install firebase-admin")
    FIREBASE_AVAILABLE = False


class FirebaseSyncService:
    """Syncs MQTT data to Firebase Realtime Database"""
    
    def __init__(self, mqtt_host="localhost", mqtt_port=1883, 
                 greenhouse_id=1, firebase_credentials=None,
                 firebase_url="https://greenhouse-project.firebaseio.com"):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.greenhouse_id = greenhouse_id
        self.firebase_credentials_path = firebase_credentials
        self.firebase_url = firebase_url
        
        # MQTT setup
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_connected = False
        
        # Firebase setup
        self.firebase_ready = False
        self.firebase_app = None
        self.initialize_firebase()
        
        # Data cache
        self.data_cache: Dict[str, Any] = {}
        self.event_buffer = []
        self.buffer_size = 10
    
    def initialize_firebase(self):
        """Initialize Firebase connection"""
        if not FIREBASE_AVAILABLE:
            print("[Firebase] Firebase SDK not available. Running in DEMO MODE.")
            print("[Firebase] Install: pip install firebase-admin")
            self.firebase_ready = False
            return
        
        if not self.firebase_credentials_path:
            print("[Firebase] No credentials provided. Running in DEMO MODE.")
            print("[Firebase] To enable Firebase sync:")
            print("[Firebase]   python firebase_sync.py --credentials config/firebase-credentials.json")
            self.firebase_ready = False
            return
        
        try:
            if not os.path.exists(self.firebase_credentials_path):
                print(f"[Firebase] ERROR: File not found: {self.firebase_credentials_path}")
                print("[Firebase] Running in DEMO MODE")
                self.firebase_ready = False
                return
            
            cred = credentials.Certificate(self.firebase_credentials_path)
            self.firebase_app = firebase_admin.initialize_app(cred, {
                'databaseURL': self.firebase_url
            })
            
            print("[Firebase] ✅ Connected to Firebase")
            print(f"[Firebase] Database: {self.firebase_url}")
            self.firebase_ready = True
            
        except Exception as e:
            print(f"[Firebase] ERROR: {e}")
            print("[Firebase] Running in DEMO MODE")
            self.firebase_ready = False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connect callback"""
        if rc == 0:
            self.mqtt_connected = True
            print(f"[Firebase/MQTT] ✅ Connected to {self.mqtt_host}:{self.mqtt_port}")
            
            topics = [
                f"greenhouse/{self.greenhouse_id}/plant/+/soil",
                f"greenhouse/{self.greenhouse_id}/plant/+/pump",
                f"greenhouse/{self.greenhouse_id}/env/+",
                f"greenhouse/{self.greenhouse_id}/actuators/+",
                f"greenhouse/{self.greenhouse_id}/status/+",
            ]
            
            for topic in topics:
                client.subscribe(topic)
                print(f"[Firebase/MQTT] 📡 Subscribed to: {topic}")
        else:
            print(f"[Firebase/MQTT] ❌ Connection failed: {rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self.mqtt_connected = False
        if rc != 0:
            print(f"[Firebase/MQTT] ⚠ Unexpected disconnect: {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback - sync to Firebase"""
        topic = msg.topic
        payload = msg.payload.decode()
        timestamp = datetime.now().isoformat()
        
        record = {
            "timestamp": timestamp,
            "value": payload,
            "topic": topic
        }
        
        self.sync_to_firebase(topic, record)
        self.update_data_cache(topic, payload, timestamp)
        self.event_buffer.append(record)
        
        if len(self.event_buffer) >= self.buffer_size:
            self.flush_event_buffer()
        
        mode = "LIVE ✅" if self.firebase_ready else "DEMO 🔄"
        print(f"[{timestamp}] [{mode}] {topic} = {payload}")
    
    def sync_to_firebase(self, topic: str, data: Dict[str, Any]):
        """Sync data to Firebase"""
        if not self.firebase_ready:
            return
        
        try:
            latest_path = f"greenhouse/{self.greenhouse_id}/latest"
            db.reference(latest_path).update({
                topic: {
                    "value": data["value"],
                    "timestamp": data["timestamp"]
                }
            })
            
            events_path = f"greenhouse/{self.greenhouse_id}/events/{int(time.time() * 1000)}"
            db.reference(events_path).set(data)
            
        except Exception as e:
            print(f"[Firebase] ❌ Sync error: {e}")
    
    def flush_event_buffer(self):
        """Flush event buffer"""
        if not self.firebase_ready or not self.event_buffer:
            return
        
        try:
            batch_path = f"greenhouse/{self.greenhouse_id}/event_batches"
            db.reference(batch_path).child(str(int(time.time()))).set({
                "count": len(self.event_buffer),
                "timestamp": datetime.now().isoformat(),
                "events": self.event_buffer[-10:]
            })
            print(f"[Firebase] 📦 Event buffer synced ({len(self.event_buffer)} events)")
            
        except Exception as e:
            print(f"[Firebase] ❌ Buffer flush error: {e}")
    
    def update_data_cache(self, topic: str, value: str, timestamp: str):
        """Update local data cache"""
        self.data_cache[topic] = {
            "value": value,
            "timestamp": timestamp
        }
    
    def generate_dashboard_snapshot(self) -> Dict[str, Any]:
        """Generate system state"""
        snapshot = {
            "greenhouse_id": self.greenhouse_id,
            "timestamp": datetime.now().isoformat(),
            "firebase_mode": "LIVE ✅" if self.firebase_ready else "DEMO 🔄",
            "environment": {},
            "plants": {},
            "actuators": {},
            "alerts": []
        }
        
        for topic, data in self.data_cache.items():
            value = data["value"]
            
            if "temp" in topic:
                snapshot["environment"]["temperature"] = {"value": value, "unit": "°C"}
                try:
                    if int(value) > 30:
                        snapshot["alerts"].append({
                            "type": "HIGH_TEMP",
                            "message": f"Temperature too high: {value}°C",
                            "severity": "critical"
                        })
                except ValueError:
                    pass
            
            elif "humidity" in topic:
                snapshot["environment"]["humidity"] = {"value": value, "unit": "%"}
            
            elif "co2" in topic:
                snapshot["environment"]["co2"] = {"value": value, "unit": "ppm"}
                try:
                    if int(value) > 1500:
                        snapshot["alerts"].append({
                            "type": "HIGH_CO2",
                            "message": f"CO2 critical: {value} ppm",
                            "severity": "critical"
                        })
                except ValueError:
                    pass
            
            elif "soil" in topic:
                plant_id = topic.split("/")[-2]
                if plant_id not in snapshot["plants"]:
                    snapshot["plants"][plant_id] = {}
                snapshot["plants"][plant_id]["moisture"] = {"value": value, "unit": "%"}
                
                try:
                    if int(value) < 30:
                        snapshot["alerts"].append({
                            "type": "LOW_MOISTURE",
                            "plant_id": plant_id,
                            "message": f"Plant {plant_id} needs watering",
                            "severity": "warning"
                        })
                except ValueError:
                    pass
            
            elif "pump" in topic:
                plant_id = topic.split("/")[-2]
                if plant_id not in snapshot["plants"]:
                    snapshot["plants"][plant_id] = {}
                snapshot["plants"][plant_id]["pump_state"] = value
            
            elif "window" in topic:
                snapshot["actuators"]["window"] = value
        
        return snapshot
    
    def run(self):
        """Main sync loop"""
        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
            
            timeout = time.time() + 10
            while not self.mqtt_connected and time.time() < timeout:
                time.sleep(0.1)
            
            if not self.mqtt_connected:
                print("[Firebase] ❌ Could not connect to MQTT broker")
                return
            
            mode = "LIVE ✅" if self.firebase_ready else "DEMO 🔄"
            print(f"\n[Firebase] Sync service running [{mode}]")
            print("[Firebase] Listening for MQTT events...\n")
            
            while True:
                time.sleep(5)
                
                if self.mqtt_connected:
                    snapshot = self.generate_dashboard_snapshot()
                    alerts = len(snapshot.get("alerts", []))
                    topics = len(self.data_cache)
                    print(f"[Firebase] 📊 Status: {topics} topics, {alerts} alerts")
        
        except KeyboardInterrupt:
            print("\n[Firebase] Shutting down...")
        except Exception as e:
            print(f"[Firebase] ❌ Error: {e}")
        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
            if self.event_buffer and self.firebase_ready:
                print("[Firebase] 📦 Flushing buffer before shutdown...")
                self.flush_event_buffer()
            
            if self.firebase_app:
                firebase_admin.delete_app(self.firebase_app)
            
            print("[Firebase] ✅ Disconnected")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Firebase Cloud Sync Service"
    )
    parser.add_argument("--mqtt-host", default="localhost", 
                       help="MQTT broker host (default: localhost)")
    parser.add_argument("--mqtt-port", type=int, default=1883, 
                       help="MQTT broker port (default: 1883)")
    parser.add_argument("--greenhouse-id", type=int, default=1, 
                       help="Greenhouse ID (default: 1)")
    parser.add_argument("--credentials", 
                       help="Path to Firebase credentials JSON")
    parser.add_argument("--firebase-url",
                       default="https://greenhouse-project.firebaseio.com",
                       help="Firebase Realtime Database URL")
    
    args = parser.parse_args()
    
    service = FirebaseSyncService(
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        greenhouse_id=args.greenhouse_id,
        firebase_credentials=args.credentials,
        firebase_url=args.firebase_url
    )
    
    service.run()


if __name__ == "__main__":
    main()
