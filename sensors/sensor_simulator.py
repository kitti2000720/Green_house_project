"""
Greenhouse Sensor Simulator

Simulates one or more independent greenhouses, each containing N plant nodes.
Every node publishes its own temperature, humidity, CO2 and soil moisture
readings under:

    greenhouse/{greenhouse_id}/plant/{plant_id}/{metric}

This mirrors the production deployment where one physical Raspberry Pi
is attached to exactly one plant in exactly one greenhouse.

Usage examples
--------------
# One greenhouse, three plants (default)
python3 sensor_simulator.py

# Two greenhouses, four plants each
python3 sensor_simulator.py --num-greenhouses 2 --plants 4

# Specific greenhouse IDs
python3 sensor_simulator.py --greenhouse-ids 1,3,5 --plants 2
"""

import os
import sys
import signal
import logging
import argparse
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paho.mqtt.client as mqtt

from config import (
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_NUM_GREENHOUSES,
    DEFAULT_NUM_PLANTS,
    DEFAULT_PUBLISH_INTERVAL,
)
from dynamics import PlantNodeDynamics, METRIC_NAMES

logger = logging.getLogger("sensor_simulator")


class SensorSimulator:
    """
    Simulates multiple greenhouses, each with multiple Raspberry Pi plant nodes.

    Data model
    ----------
    self.nodes  :  {(greenhouse_id, plant_id): PlantNodeDynamics}

    Topic structure published
    -------------------------
    greenhouse/{gh}/plant/{plant}/temp
    greenhouse/{gh}/plant/{plant}/humidity
    greenhouse/{gh}/plant/{plant}/co2
    greenhouse/{gh}/plant/{plant}/soil

    Actuator commands consumed
    --------------------------
    greenhouse/{gh}/plant/{plant}/pump    -> ON / OFF
    greenhouse/{gh}/plant/{plant}/window  -> OPEN / CLOSED
    """

    def __init__(
        self,
        broker_host: str      = DEFAULT_MQTT_HOST,
        broker_port: int      = DEFAULT_MQTT_PORT,
        greenhouse_ids: list  = None,
        num_plants: int       = DEFAULT_NUM_PLANTS,
    ):
        self.broker_host    = broker_host
        self.broker_port    = broker_port
        self.greenhouse_ids = greenhouse_ids or [1]
        self.num_plants     = num_plants

        # Keyed by (greenhouse_id, plant_id) so every node is independent
        self.nodes: dict = {
            (gh_id, plant_id): PlantNodeDynamics()
            for gh_id    in self.greenhouse_ids
            for plant_id in range(1, num_plants + 1)
        }

        self._connected = threading.Event()
        self._shutdown  = threading.Event()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            logger.error("Connection failed: rc=%d", rc)
            return
        self._connected.set()
        logger.info("Connected to %s:%d", self.broker_host, self.broker_port)

        for (gh_id, plant_id) in self.nodes:
            client.subscribe(f"greenhouse/{gh_id}/plant/{plant_id}/pump")
            client.subscribe(f"greenhouse/{gh_id}/plant/{plant_id}/window")

    def _on_disconnect(self, client, userdata, rc):
        self._connected.clear()
        if rc != 0:
            logger.warning("Unexpected disconnect (rc=%d). Auto-reconnect enabled.", rc)

    def _on_message(self, client, userdata, msg):
        """
        Handle actuator commands and forward them to the correct node.
        Expected topic: greenhouse/{gh_id}/plant/{plant_id}/{actuator}
        """
        parts = msg.topic.split("/")
        # greenhouse / {gh_id} / plant / {plant_id} / {actuator}
        if len(parts) != 5:
            return
        try:
            gh_id    = int(parts[1])
            plant_id = int(parts[3])
        except ValueError:
            return

        node = self.nodes.get((gh_id, plant_id))
        if node is None:
            return

        payload  = msg.payload.decode()
        actuator = parts[4]

        if actuator == "pump":
            node.set_pump(payload.upper() == "ON")
            logger.info("gh[%d]/plant[%d] pump -> %s", gh_id, plant_id, payload.upper())
        elif actuator == "window":
            node.set_window(payload.upper() == "OPEN")
            logger.info("gh[%d]/plant[%d] window -> %s", gh_id, plant_id, payload.upper())

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def _publish(self, topic: str, value: float) -> None:
        self._client.publish(topic, int(value), qos=1)

    def _publish_all(self) -> None:
        if not self._connected.is_set():
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("[%s]", ts)

        for (gh_id, plant_id), node in sorted(self.nodes.items()):
            r    = node.readings
            base = f"greenhouse/{gh_id}/plant/{plant_id}"

            for metric in METRIC_NAMES:
                self._publish(f"{base}/{metric}", r[metric])

            parts = "  ".join(f"{m}={r[m]:.1f}" for m in METRIC_NAMES)
            logger.info("  gh[%d]/plant[%d]  %s", gh_id, plant_id, parts)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def request_shutdown(self):
        """Signal the main loop to stop."""
        self._shutdown.set()

    def run(self, interval: int = DEFAULT_PUBLISH_INTERVAL) -> None:
        try:
            self._client.connect(self.broker_host, self.broker_port, keepalive=60)
            self._client.loop_start()

            if not self._connected.wait(timeout=10):
                logger.error("Could not connect to MQTT broker within 10 s")
                return

            total_nodes = len(self.nodes)
            logger.info(
                "Running  greenhouses=%s  plants_per_greenhouse=%d  "
                "total_nodes=%d  interval=%ds",
                self.greenhouse_ids, self.num_plants, total_nodes, interval,
            )
            logger.info("Press Ctrl+C to stop.")

            while not self._shutdown.is_set():
                self._shutdown.wait(timeout=interval)
                if self._shutdown.is_set():
                    break
                for node in self.nodes.values():
                    node.step()
                self._publish_all()

        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            self._client.loop_stop()
            self._client.disconnect()
            logger.info("Disconnected")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def _parse_greenhouse_ids(value: str) -> list:
    """Parse '1,2,3' into [1, 2, 3]."""
    try:
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid greenhouse IDs: '{value}'. Expected comma-separated integers, e.g. 1,2,3"
        )


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Greenhouse Sensor Simulator - simulates independent RPi plant nodes",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host",             default=DEFAULT_MQTT_HOST,
                        help="MQTT broker host")
    parser.add_argument("--port",             type=int, default=DEFAULT_MQTT_PORT,
                        help="MQTT broker port")
    parser.add_argument("--plants",           type=int, default=DEFAULT_NUM_PLANTS,
                        help="Number of plant nodes per greenhouse")
    parser.add_argument("--interval",         type=int, default=DEFAULT_PUBLISH_INTERVAL,
                        help="Publish interval in seconds")

    # Mutually exclusive: either --num-greenhouses or --greenhouse-ids
    gh_group = parser.add_mutually_exclusive_group()
    gh_group.add_argument(
        "--num-greenhouses", type=int, default=DEFAULT_NUM_GREENHOUSES,
        metavar="N",
        help="Number of greenhouses to simulate (IDs will be 1..N)",
    )
    gh_group.add_argument(
        "--greenhouse-ids", type=_parse_greenhouse_ids, default=None,
        metavar="1,2,3",
        help="Explicit list of greenhouse IDs to simulate",
    )

    args = parser.parse_args()

    if args.greenhouse_ids is not None:
        greenhouse_ids = args.greenhouse_ids
    else:
        greenhouse_ids = list(range(1, args.num_greenhouses + 1))

    simulator = SensorSimulator(
        broker_host=args.host,
        broker_port=args.port,
        greenhouse_ids=greenhouse_ids,
        num_plants=args.plants,
    )

    # Graceful shutdown on SIGINT / SIGTERM
    def _signal_handler(sig, frame):
        logger.info("Received signal %d, shutting down...", sig)
        simulator.request_shutdown()

    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    simulator.run(interval=args.interval)


if __name__ == "__main__":
    main()
