"""
Greenhouse Sensor Simulator

Simulates DHT22 (temp/humidity), CO2 and soil moisture sensors.
Publishes readings to an MQTT broker and reacts to actuator commands.
"""

import os
import sys
import time
import argparse
from datetime import datetime

# Allow running directly from the project root or the sensors/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

from config import (
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_GREENHOUSE_ID,
    DEFAULT_NUM_PLANTS,
    DEFAULT_PUBLISH_INTERVAL,
)
from dynamics import EnvironmentDynamics, PlantDynamics


class SensorSimulator:
    """
    Orchestrates sensor simulation and MQTT publishing.

    - EnvironmentDynamics models temp/humidity/CO2.
    - PlantDynamics models per-plant soil moisture.
    - Actuator commands (pump, window) are consumed from MQTT
      and fed back into the dynamics so the simulation is reactive.
    """

    def __init__(
        self,
        broker_host: str = DEFAULT_MQTT_HOST,
        broker_port: int = DEFAULT_MQTT_PORT,
        greenhouse_id: int = DEFAULT_GREENHOUSE_ID,
        num_plants: int = DEFAULT_NUM_PLANTS,
    ):
        self.broker_host   = broker_host
        self.broker_port   = broker_port
        self.greenhouse_id = greenhouse_id
        self.num_plants    = num_plants

        self.environment = EnvironmentDynamics()
        self.plants = {i: PlantDynamics() for i in range(1, num_plants + 1)}

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
        gh = self.greenhouse_id
        client.subscribe(f"greenhouse/{gh}/plant/+/pump")
        client.subscribe(f"greenhouse/{gh}/actuators/window")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            print(f"[Simulator] Unexpected disconnect: rc={rc}")

    def _on_message(self, client, userdata, msg):
        topic   = msg.topic
        payload = msg.payload.decode()
        print(f"[Simulator] Command: {topic} = {payload}")

        if "/pump" in topic:
            parts = topic.split("/")
            try:
                plant_id = int(parts[-2])
                self.plants[plant_id].set_pump(payload.upper() == "ON")
            except (ValueError, KeyError):
                pass

        elif "window" in topic:
            self.environment.set_window(payload.upper() == "OPEN")

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def _publish(self, topic: str, value: float) -> None:
        self._client.publish(topic, int(value), qos=1)

    def _publish_all(self) -> None:
        if not self._connected:
            return

        gh  = self.greenhouse_id
        env = self.environment.readings
        ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._publish(f"greenhouse/{gh}/env/temp",     env["temp"])
        self._publish(f"greenhouse/{gh}/env/humidity", env["humidity"])
        self._publish(f"greenhouse/{gh}/env/co2",      env["co2"])

        print(
            f"[{ts}] temp={env['temp']:.1f}C  "
            f"humidity={env['humidity']:.1f}%  "
            f"co2={env['co2']:.0f}ppm"
        )

        for plant_id, plant in self.plants.items():
            self._publish(f"greenhouse/{gh}/plant/{plant_id}/soil", plant.moisture)
            pump_str = "ON" if plant.pump_on else "OFF"
            print(f"         plant[{plant_id}] moisture={plant.moisture:.1f}%  pump={pump_str}")

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

            print(
                f"[Simulator] Running  "
                f"greenhouse={self.greenhouse_id}  "
                f"plants={self.num_plants}  "
                f"interval={interval}s"
            )
            print("Press Ctrl+C to stop.\n")

            while True:
                time.sleep(interval)
                self.environment.step()
                for plant in self.plants.values():
                    plant.step()
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

def main():
    parser = argparse.ArgumentParser(description="Greenhouse Sensor Simulator")
    parser.add_argument("--host",          default=DEFAULT_MQTT_HOST,
                        help="MQTT broker host (default: %(default)s)")
    parser.add_argument("--port",          type=int, default=DEFAULT_MQTT_PORT,
                        help="MQTT broker port (default: %(default)s)")
    parser.add_argument("--greenhouse-id", type=int, default=DEFAULT_GREENHOUSE_ID,
                        help="Greenhouse ID (default: %(default)s)")
    parser.add_argument("--plants",        type=int, default=DEFAULT_NUM_PLANTS,
                        help="Number of plants to simulate (default: %(default)s)")
    parser.add_argument("--interval",      type=int, default=DEFAULT_PUBLISH_INTERVAL,
                        help="Publish interval in seconds (default: %(default)s)")
    args = parser.parse_args()

    simulator = SensorSimulator(
        broker_host=args.host,
        broker_port=args.port,
        greenhouse_id=args.greenhouse_id,
        num_plants=args.plants,
    )
    simulator.run(interval=args.interval)


if __name__ == "__main__":
    main()
