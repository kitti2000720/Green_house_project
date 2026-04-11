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
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

from config import (
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_NUM_GREENHOUSES,
    DEFAULT_NUM_PLANTS,
    DEFAULT_PUBLISH_INTERVAL,
)
from dynamics import PlantNodeDynamics


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

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message
        self._connected = False

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print(f"[Simulator] Connection failed: rc={rc}")
            return
        self._connected = True
        print(f"[Simulator] Connected to {self.broker_host}:{self.broker_port}")

        for (gh_id, plant_id) in self.nodes:
            client.subscribe(f"greenhouse/{gh_id}/plant/{plant_id}/pump")
            client.subscribe(f"greenhouse/{gh_id}/plant/{plant_id}/window")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            print(f"[Simulator] Unexpected disconnect: rc={rc}")

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
            print(f"[Simulator] gh[{gh_id}]/plant[{plant_id}] pump -> {payload.upper()}")
        elif actuator == "window":
            node.set_window(payload.upper() == "OPEN")
            print(f"[Simulator] gh[{gh_id}]/plant[{plant_id}] window -> {payload.upper()}")

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def _publish(self, topic: str, value: float) -> None:
        self._client.publish(topic, int(value), qos=1)

    def _publish_all(self) -> None:
        if not self._connected:
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}]")

        for (gh_id, plant_id), node in sorted(self.nodes.items()):
            r    = node.readings
            base = f"greenhouse/{gh_id}/plant/{plant_id}"

            self._publish(f"{base}/temp",     r["temp"])
            self._publish(f"{base}/humidity", r["humidity"])
            self._publish(f"{base}/co2",      r["co2"])
            self._publish(f"{base}/soil",     r["soil"])

            print(
                f"  gh[{gh_id}]/plant[{plant_id}]  "
                f"temp={r['temp']:.1f}C  "
                f"humidity={r['humidity']:.1f}%  "
                f"co2={r['co2']:.0f}ppm  "
                f"soil={r['soil']:.1f}%"
            )
        print()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, interval: int = DEFAULT_PUBLISH_INTERVAL) -> None:
        try:
            self._client.connect(self.broker_host, self.broker_port, keepalive=60)
            self._client.loop_start()

            deadline = time.time() + 10
            while not self._connected and time.time() < deadline:
                time.sleep(0.1)

            if not self._connected:
                print("[Simulator] ERROR: Could not connect to MQTT broker")
                return

            total_nodes = len(self.nodes)
            print(
                f"[Simulator] Running  "
                f"greenhouses={self.greenhouse_ids}  "
                f"plants_per_greenhouse={self.num_plants}  "
                f"total_nodes={total_nodes}  "
                f"interval={interval}s"
            )
            print("Press Ctrl+C to stop.\n")

            while True:
                time.sleep(interval)
                for node in self.nodes.values():
                    node.step()
                self._publish_all()

        except KeyboardInterrupt:
            print("\n[Simulator] Stopping...")
        finally:
            self._client.loop_stop()
            self._client.disconnect()
            print("[Simulator] Disconnected")


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
    simulator.run(interval=args.interval)


if __name__ == "__main__":
    main()
