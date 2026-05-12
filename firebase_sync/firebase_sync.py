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
import signal
import logging
import argparse
import threading
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

logger = logging.getLogger("firebase_sync")


class FirebaseSyncService:
    """
    Bridges MQTT events to Firebase Realtime Database.

    Responsibilities
    ----------------
    - Subscribe to all sensor and actuator topics.
    - On each message: write the latest value and append event to Firebase.
    - Buffer events and flush as a batch every EVENT_BUFFER_SIZE messages.
    - Log alerts when thresholds are breached.

    Attributes:
        SUBSCRIPTIONS: list
            Topic patterns to subscribe to per greenhouse.
            Use ``{id}`` as a placeholder for the greenhouse ID.
            Add new patterns here to capture additional topics without changing
            any other part of the code.
    """

    SUBSCRIPTIONS = [
        "greenhouse/{id}/plant/+/soil",
        "greenhouse/{id}/plant/+/temp",
        "greenhouse/{id}/plant/+/humidity",
        "greenhouse/{id}/plant/+/co2",
        "greenhouse/{id}/plant/+/pump",
        "greenhouse/{id}/actuators/+",
        "greenhouse/{id}/status/+",
    ]

    def __init__(
        self,
        mqtt_host: str        = MQTT_HOST,
        mqtt_port: int        = MQTT_PORT,
        greenhouse_ids: list  = None,
        credentials_path: str = None,
        firebase_url: str     = FIREBASE_URL,
    ):
        self.mqtt_host      = mqtt_host
        self.mqtt_port      = mqtt_port
        self.greenhouse_ids = greenhouse_ids or [GREENHOUSE_ID]

        self._firebase      = FirebaseClient(credentials_path, firebase_url)
        self._event_buffer  = []
        self._connected     = threading.Event()
        self._shutdown      = threading.Event()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

    # region ===== Protected methods  =====
    # region MQTT callbacks
    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            logger.error("MQTT connection failed: rc=%d", rc)
            return

        self._connected.set()
        logger.info("MQTT connected to %s:%d", self.mqtt_host, self.mqtt_port)

        for gh_id in self.greenhouse_ids:
            for pattern in self.SUBSCRIPTIONS:
                topic = pattern.format(id=gh_id)
                client.subscribe(topic)
                logger.info("Subscribed: %s", topic)

    def _on_disconnect(self, client, userdata, rc):
        self._connected.clear()
        if rc != 0:
            logger.warning("MQTT unexpected disconnect (rc=%d). Auto-reconnect enabled.", rc)

    def _on_message(self, client, userdata, msg):
        topic     = msg.topic
        payload   = msg.payload.decode()
        timestamp = datetime.now().isoformat()
        mode      = "LIVE" if self._firebase.ready else "DEMO"

        logger.info("[%s] %s = %s", mode, topic, payload)

        record = {"timestamp": timestamp, "topic": topic, "value": payload}

        # Extract greenhouse_id from topic: greenhouse/{id}/...
        parts = topic.split("/")
        gh_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else self.greenhouse_ids[0]

        self._firebase.write_latest(gh_id, topic, payload, timestamp)
        self._firebase.write_event(gh_id, record)

        self._event_buffer.append(record)
        if len(self._event_buffer) >= EVENT_BUFFER_SIZE:
            self._flush_buffer(gh_id)

        parsed = parse_topic(topic, payload, gh_id)
        for alert in check_alerts(parsed):
            logger.warning("ALERT [%s]: %s", alert['severity'].upper(), alert['message'])
    # endregion

    def _flush_buffer(self, greenhouse_id: int = None) -> None:
        gh_id = greenhouse_id if greenhouse_id is not None else self.greenhouse_ids[0]
        self._firebase.write_batch(gh_id, self._event_buffer)
        self._event_buffer.clear()

    # endregion

    # region ===== Public methods =====
    def request_shutdown(self):
        """Signal the main loop to stop."""
        self._shutdown.set()

    def run(self) -> None:
        try:
            self._client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self._client.loop_start()

            if not self._connected.wait(timeout=10):
                logger.error("Could not connect to MQTT broker within 10 s")
                return

            mode = "LIVE" if self._firebase.ready else "DEMO"
            logger.info("Running [%s] - listening for events...", mode)

            while not self._shutdown.is_set():
                self._shutdown.wait(timeout=5)

        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            self._client.loop_stop()
            self._client.disconnect()
            if self._event_buffer:
                self._flush_buffer()
            self._firebase.cleanup()
            logger.info("Disconnected")

    # endregion


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Greenhouse Firebase Sync Service")
    parser.add_argument("--mqtt-host",      default=MQTT_HOST,
                        help="MQTT broker host (default: %(default)s)")
    parser.add_argument("--mqtt-port",      type=int, default=MQTT_PORT,
                        help="MQTT broker port (default: %(default)s)")
    parser.add_argument("--greenhouse-ids",
                        default=str(GREENHOUSE_ID),
                        metavar="1,2,3",
                        help="Comma-separated list of greenhouse IDs to monitor (default: %(default)s)")
    parser.add_argument("--credentials",
                        help="Path to Firebase service-account JSON file")
    parser.add_argument("--firebase-url",   default=FIREBASE_URL,
                        help="Firebase Realtime Database URL (default: %(default)s)")
    args = parser.parse_args()

    try:
        greenhouse_ids = [int(x.strip()) for x in args.greenhouse_ids.split(",") if x.strip()]
    except ValueError:
        logger.error("Invalid --greenhouse-ids value: '%s'", args.greenhouse_ids)
        sys.exit(1)

    service = FirebaseSyncService(
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        greenhouse_ids=greenhouse_ids,
        credentials_path=args.credentials,
        firebase_url=args.firebase_url,
    )

    # Graceful shutdown on SIGINT / SIGTERM
    def _signal_handler(sig, frame):
        logger.info("Received signal %d, shutting down...", sig)
        service.request_shutdown()

    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    service.run()


if __name__ == "__main__":
    main()
