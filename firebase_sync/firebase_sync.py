"""
Greenhouse Firebase Sync Service

Subscribes to all MQTT topics for a greenhouse and forwards
every event to Firebase Realtime Database.

Demo mode
---------
If no --credentials are provided (or firebase-admin is not installed),
the service runs in demo mode: MQTT events are printed to stdout but
nothing is written to Firebase.
"""

import os
import sys
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

from config import MQTT_HOST, MQTT_PORT, GREENHOUSE_ID, FIREBASE_URL, EVENT_BUFFER_SIZE
from firebase_client import FirebaseClient
from topic_parser import parse_topic, check_alerts


class FirebaseSyncService:
    """
    Bridges MQTT events to Firebase Realtime Database.

    Responsibilities
    ----------------
    - Subscribe to all sensor and actuator topics.
    - On each message: write latest value + append event to Firebase.
    - Buffer events and flush as a batch every EVENT_BUFFER_SIZE messages.
    - Log alerts when thresholds are breached.
    """

    # Topic patterns to subscribe to.
    # Use {id} as a placeholder for the greenhouse ID.
    SUBSCRIPTIONS = [
        "greenhouse/{id}/plant/+/soil",
        "greenhouse/{id}/plant/+/pump",
        "greenhouse/{id}/env/+",
        "greenhouse/{id}/actuators/+",
        "greenhouse/{id}/status/+",
    ]

    def __init__(
        self,
        mqtt_host: str       = MQTT_HOST,
        mqtt_port: int       = MQTT_PORT,
        greenhouse_id: int   = GREENHOUSE_ID,
        credentials_path: str = None,
        firebase_url: str    = FIREBASE_URL,
    ):
        self.mqtt_host     = mqtt_host
        self.mqtt_port     = mqtt_port
        self.greenhouse_id = greenhouse_id

        self._firebase      = FirebaseClient(credentials_path, firebase_url)
        self._event_buffer  = []
        self._connected     = False

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print(f"[Sync] MQTT connection failed: rc={rc}")
            return

        self._connected = True
        print(f"[Sync] MQTT connected to {self.mqtt_host}:{self.mqtt_port}")

        for pattern in self.SUBSCRIPTIONS:
            topic = pattern.format(id=self.greenhouse_id)
            client.subscribe(topic)
            print(f"[Sync] Subscribed: {topic}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            print(f"[Sync] MQTT unexpected disconnect: rc={rc}")

    def _on_message(self, client, userdata, msg):
        topic     = msg.topic
        payload   = msg.payload.decode()
        timestamp = datetime.now().isoformat()
        mode      = "LIVE" if self._firebase.ready else "DEMO"

        print(f"[{timestamp}] [{mode}] {topic} = {payload}")

        record = {"timestamp": timestamp, "topic": topic, "value": payload}

        self._firebase.write_latest(self.greenhouse_id, topic, payload, timestamp)
        self._firebase.write_event(self.greenhouse_id, record)

        self._event_buffer.append(record)
        if len(self._event_buffer) >= EVENT_BUFFER_SIZE:
            self._flush_buffer()

        parsed = parse_topic(topic, payload, self.greenhouse_id)
        for alert in check_alerts(parsed):
            print(f"[Sync] ALERT [{alert['severity'].upper()}]: {alert['message']}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _flush_buffer(self) -> None:
        self._firebase.write_batch(self.greenhouse_id, self._event_buffer)
        self._event_buffer.clear()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            self._client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self._client.loop_start()

            deadline = time.time() + 10
            while not self._connected and time.time() < deadline:
                time.sleep(0.1)

            if not self._connected:
                print("[Sync] ERROR: Could not connect to MQTT broker")
                return

            mode = "LIVE" if self._firebase.ready else "DEMO"
            print(f"\n[Sync] Running [{mode}] - listening for events...\n")

            while True:
                time.sleep(5)

        except KeyboardInterrupt:
            print("\n[Sync] Stopping...")
        finally:
            self._client.loop_stop()
            self._client.disconnect()
            if self._event_buffer:
                self._flush_buffer()
            self._firebase.cleanup()
            print("[Sync] Disconnected")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Greenhouse Firebase Sync Service")
    parser.add_argument("--mqtt-host",      default=MQTT_HOST,
                        help="MQTT broker host (default: %(default)s)")
    parser.add_argument("--mqtt-port",      type=int, default=MQTT_PORT,
                        help="MQTT broker port (default: %(default)s)")
    parser.add_argument("--greenhouse-id",  type=int, default=GREENHOUSE_ID,
                        help="Greenhouse ID (default: %(default)s)")
    parser.add_argument("--credentials",
                        help="Path to Firebase service-account JSON file")
    parser.add_argument("--firebase-url",   default=FIREBASE_URL,
                        help="Firebase Realtime Database URL (default: %(default)s)")
    args = parser.parse_args()

    service = FirebaseSyncService(
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        greenhouse_id=args.greenhouse_id,
        credentials_path=args.credentials,
        firebase_url=args.firebase_url,
    )
    service.run()


if __name__ == "__main__":
    main()
