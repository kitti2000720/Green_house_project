"""
Raspberry Pi Sensor Reader

Reads real sensors and publishes to MQTT.

Supported hardware
------------------
- DHT22  : temperature + humidity via GPIO
- ADS1115: 4-channel ADC over I2C for capacitive soil moisture sensors

Install hardware libraries on the Raspberry Pi:
    pip install Adafruit-DHT adafruit-circuitpython-ads1x15 RPi.GPIO
"""

import os
import sys
import time
import argparse
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

# Optional hardware libraries - warn but do not abort if missing
try:
    import Adafruit_DHT
    _DHT_AVAILABLE = True
except ImportError:
    _DHT_AVAILABLE = False
    print("[RPi] Warning: Adafruit_DHT not available. Install: pip install Adafruit-DHT")

try:
    import board
    import busio
    from adafruit_ads1x15.ads1115 import ADS1115
    from adafruit_ads1x15.analog_in import AnalogIn
    _ADS_AVAILABLE = True
except ImportError:
    _ADS_AVAILABLE = False
    print("[RPi] Warning: ADS1115 libraries not available. Install: pip install adafruit-circuitpython-ads1x15")

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except ImportError:
    _GPIO_AVAILABLE = False

from config import (
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_GREENHOUSE_ID,
    DEFAULT_PUBLISH_INTERVAL,
)

# Soil moisture sensor voltage calibration points
SOIL_VOLTAGE_DRY = 1.0   # volts at 0% moisture
SOIL_VOLTAGE_WET = 2.5   # volts at 100% moisture

DHT_DEFAULT_PIN     = 17    # GPIO pin number
ADS_DEFAULT_ADDRESS = 0x48  # I2C address


class DHT22Reader:
    """Reads temperature and humidity from a DHT22 sensor."""

    def __init__(self, gpio_pin: int):
        self._pin       = gpio_pin
        self._available = _DHT_AVAILABLE

    def read(self) -> dict:
        """Return {"temp": float, "humidity": float} or {} on failure."""
        if not self._available:
            return {}
        try:
            humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, self._pin)
            if humidity is not None and temperature is not None:
                return {"temp": temperature, "humidity": humidity}
        except Exception as exc:
            print(f"[DHT22] Read error: {exc}")
        return {}


class SoilMoistureReader:
    """Reads soil moisture percentage from capacitive sensors via ADS1115 ADC."""

    _CHANNEL_PINS = [ADS1115.P0, ADS1115.P1, ADS1115.P2, ADS1115.P3] if _ADS_AVAILABLE else []

    def __init__(self, i2c_address: int = ADS_DEFAULT_ADDRESS):
        self._ads = None
        if not _ADS_AVAILABLE:
            return
        try:
            i2c      = busio.I2C(board.SCL, board.SDA)
            self._ads = ADS1115(i2c, address=i2c_address)
            print(f"[ADS1115] Configured at I2C address 0x{i2c_address:02x}")
        except Exception as exc:
            print(f"[ADS1115] Init error: {exc}")

    def read_channel(self, channel: int) -> Optional[float]:
        """
        Read moisture as a percentage (0-100) from ADC channel 0-3.
        Returns None when the ADC is unavailable or an error occurs.
        """
        if self._ads is None or channel not in range(4):
            return None
        try:
            voltage = AnalogIn(self._ads, self._CHANNEL_PINS[channel]).voltage
            pct     = (voltage - SOIL_VOLTAGE_DRY) / (SOIL_VOLTAGE_WET - SOIL_VOLTAGE_DRY) * 100.0
            return max(0.0, min(100.0, pct))
        except Exception as exc:
            print(f"[ADS1115] Read error (ch{channel}): {exc}")
            return None


class RaspberryPiSensorReader:
    """
    Reads real RPi sensors and publishes readings to MQTT.

    Sensors are mapped as:
      - Plant N -> ADS1115 channel N-1  (plant 1 = ch 0, plant 2 = ch 1, ...)
      - Env     -> DHT22 on gpio_pin
    """

    def __init__(
        self,
        broker_host: str  = DEFAULT_MQTT_HOST,
        broker_port: int  = DEFAULT_MQTT_PORT,
        greenhouse_id: int = DEFAULT_GREENHOUSE_ID,
        dht_pin: int       = DHT_DEFAULT_PIN,
        ads_address: int   = ADS_DEFAULT_ADDRESS,
        num_plants: int    = 3,
    ):
        self.broker_host   = broker_host
        self.broker_port   = broker_port
        self.greenhouse_id = greenhouse_id
        self.num_plants    = num_plants

        self._dht  = DHT22Reader(dht_pin)
        self._soil = SoilMoistureReader(ads_address)

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._connected = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            print(f"[RPi] Connected to {self.broker_host}:{self.broker_port}")
        else:
            print(f"[RPi] Connection failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            print(f"[RPi] Unexpected disconnect: rc={rc}")

    def _publish(self, topic: str, value: float) -> None:
        self._client.publish(topic, int(value), qos=1)
        print(f"[RPi] {topic} = {value:.1f}")

    def publish_readings(self) -> None:
        if not self._connected:
            return

        gh = self.greenhouse_id

        dht = self._dht.read()
        if "temp" in dht:
            self._publish(f"greenhouse/{gh}/env/temp",     dht["temp"])
        if "humidity" in dht:
            self._publish(f"greenhouse/{gh}/env/humidity", dht["humidity"])

        for plant_id in range(1, self.num_plants + 1):
            moisture = self._soil.read_channel(plant_id - 1)
            if moisture is not None:
                self._publish(f"greenhouse/{gh}/plant/{plant_id}/soil", moisture)

    def run(self, interval: int = DEFAULT_PUBLISH_INTERVAL) -> None:
        try:
            self._client.connect(self.broker_host, self.broker_port, keepalive=60)
            self._client.loop_start()

            deadline = time.time() + 10
            while not self._connected and time.time() < deadline:
                time.sleep(0.1)

            if not self._connected:
                print("[RPi] ERROR: Could not connect to MQTT broker")
                return

            print(
                f"[RPi] Running  "
                f"greenhouse={self.greenhouse_id}  "
                f"plants={self.num_plants}  "
                f"interval={interval}s"
            )
            print("Press Ctrl+C to stop.\n")

            while True:
                self.publish_readings()
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[RPi] Stopping...")
        finally:
            self._client.loop_stop()
            self._client.disconnect()
            if _GPIO_AVAILABLE:
                try:
                    GPIO.cleanup()
                except Exception:
                    pass
            print("[RPi] Disconnected")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Greenhouse Sensor Reader")
    parser.add_argument("--host",          default=DEFAULT_MQTT_HOST,
                        help="MQTT broker host (default: %(default)s)")
    parser.add_argument("--port",          type=int, default=DEFAULT_MQTT_PORT,
                        help="MQTT broker port (default: %(default)s)")
    parser.add_argument("--greenhouse-id", type=int, default=DEFAULT_GREENHOUSE_ID)
    parser.add_argument("--dht-pin",       type=int, default=DHT_DEFAULT_PIN,
                        help="GPIO pin for DHT22 (default: %(default)s)")
    parser.add_argument("--ads-address",   type=lambda x: int(x, 0), default=ADS_DEFAULT_ADDRESS,
                        help="I2C address for ADS1115, e.g. 0x48 (default: 0x%(default)02x)")
    parser.add_argument("--plants",        type=int, default=3,
                        help="Number of plants (default: %(default)s)")
    parser.add_argument("--interval",      type=int, default=DEFAULT_PUBLISH_INTERVAL,
                        help="Publish interval in seconds (default: %(default)s)")
    args = parser.parse_args()

    reader = RaspberryPiSensorReader(
        broker_host=args.host,
        broker_port=args.port,
        greenhouse_id=args.greenhouse_id,
        dht_pin=args.dht_pin,
        ads_address=args.ads_address,
        num_plants=args.plants,
    )
    reader.run(interval=args.interval)


if __name__ == "__main__":
    main()
