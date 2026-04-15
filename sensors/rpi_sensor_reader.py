"""
Raspberry Pi Plant Node - Sensor Reader

One instance of this script runs on each Raspberry Pi.
Each RPi belongs to exactly one greenhouse and one plant:

    --greenhouse-id <id>   --plant-id <id>

Sensors read
------------
- DHT22    : temperature + humidity  (GPIO)
- ADS1115  : soil moisture           (I2C ADC, channel 0)
- MH-Z19B  : CO2 concentration       (UART)

Error handling
--------------
Every sensor read is validated against physical bounds defined in config.py.
A reading that falls outside the valid range is discarded and logged.
If a sensor fails MAX_CONSECUTIVE_ERRORS times in a row, a warning is
emitted to alert the operator.

Install hardware libraries on the Raspberry Pi:
    pip install Adafruit-DHT adafruit-circuitpython-ads1x15 RPi.GPIO mh-z19
"""

import os
import sys
import signal
import logging
import argparse
import threading


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

try:
    import Adafruit_DHT
    _DHT_AVAILABLE = True
except ImportError:
    _DHT_AVAILABLE = False

try:
    import board
    import busio
    from adafruit_ads1x15.ads1115 import ADS1115
    from adafruit_ads1x15.analog_in import AnalogIn
    _ADS_AVAILABLE = True
except ImportError:
    _ADS_AVAILABLE = False

try:
    import mh_z19
    _MHZ19_AVAILABLE = True
except ImportError:
    _MHZ19_AVAILABLE = False

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except ImportError:
    _GPIO_AVAILABLE = False

from sensors import (
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_GREENHOUSE_ID,
    DEFAULT_PLANT_ID,
    DEFAULT_PUBLISH_INTERVAL,
    DHT22_GPIO_PIN,
    ADS1115_I2C_ADDR,
    ADS1115_CHANNEL,
    MHZ19_SERIAL_PORT,
    SOIL_VOLTAGE_DRY,
    SOIL_VOLTAGE_WET,
    VALID_TEMP_RANGE,
    VALID_HUMIDITY_RANGE,
    VALID_CO2_RANGE,
    VALID_SOIL_RANGE,
)

logger = logging.getLogger("rpi_sensor_reader")

# How many consecutive sensor failures trigger a warning log
MAX_CONSECUTIVE_ERRORS = 5


# ------------------------------------------------------------------
# Sensor validation helper
# ------------------------------------------------------------------

def _validate(value: float, valid_range: tuple, name: str) -> float | None:
    """
    Return value if it is within valid_range, otherwise log and return None.
    valid_range is (min, max) inclusive.
    """
    lo, hi = valid_range
    if lo <= value <= hi:
        return value
    logger.warning("%s=%.2f is outside valid range [%.1f, %.1f] - discarding", name, value, lo, hi)
    return None


# ------------------------------------------------------------------
# Sensor driver classes
# ------------------------------------------------------------------

class DHT22Reader:
    """Reads temperature and humidity from a DHT22 sensor via GPIO."""

    def __init__(self, gpio_pin: int):
        self._pin          = gpio_pin
        self._available    = _DHT_AVAILABLE
        self._error_count  = 0
        if self._available:
            logger.info("[DHT22] Configured on GPIO %d", gpio_pin)
        else:
            logger.warning("[DHT22] Adafruit_DHT not available.")

    def read(self) -> dict:
        """
        Return validated {temp, humidity} or {} on failure.
        Logs a warning after MAX_CONSECUTIVE_ERRORS consecutive failures.
        """
        if not self._available:
            return {}
        try:
            humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, self._pin)
            if humidity is None or temperature is None:
                raise ValueError("DHT22 returned None")

            temp = _validate(temperature, VALID_TEMP_RANGE,     "temp")
            hum  = _validate(humidity,    VALID_HUMIDITY_RANGE, "humidity")

            if temp is None or hum is None:
                raise ValueError("Validation failed")

            self._error_count = 0
            return {"temp": temp, "humidity": hum}

        except Exception as exc:
            self._error_count += 1
            logger.error("[DHT22] Read error (attempt %d): %s", self._error_count, exc)
            if self._error_count >= MAX_CONSECUTIVE_ERRORS:
                logger.warning(
                    "[DHT22] %d consecutive failures. Check sensor wiring on GPIO %d.",
                    self._error_count, self._pin,
                )
        return {}


class SoilMoistureReader:
    """Reads soil moisture from a capacitive sensor via ADS1115 ADC."""

    _CHANNEL_PINS = [ADS1115.P0, ADS1115.P1, ADS1115.P2, ADS1115.P3] if _ADS_AVAILABLE else []

    def __init__(self, i2c_address: int, channel: int):
        self._channel     = channel
        self._ads         = None
        self._error_count = 0
        if not _ADS_AVAILABLE:
            logger.warning("[ADS1115] Libraries not available.")
            return
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._ads = ADS1115(i2c, address=i2c_address)
            logger.info("[ADS1115] Configured at I2C 0x%02x, channel %d", i2c_address, channel)
        except Exception as exc:
            logger.error("[ADS1115] Init error: %s", exc)

    def read(self) -> float | None:
        """Return moisture percentage (0-100) or None on failure."""
        if self._ads is None or self._channel not in range(4):
            return None
        try:
            voltage = AnalogIn(self._ads, self._CHANNEL_PINS[self._channel]).voltage
            pct     = (voltage - SOIL_VOLTAGE_DRY) / (SOIL_VOLTAGE_WET - SOIL_VOLTAGE_DRY) * 100.0
            result  = _validate(pct, VALID_SOIL_RANGE, "soil")
            if result is None:
                raise ValueError("Out of range")
            self._error_count = 0
            return result
        except Exception as exc:
            self._error_count += 1
            logger.error("[ADS1115] Read error (attempt %d): %s", self._error_count, exc)
            if self._error_count >= MAX_CONSECUTIVE_ERRORS:
                logger.warning("[ADS1115] %d consecutive failures.", self._error_count)
        return None


class CO2SensorReader:
    """Reads CO2 concentration from an MH-Z19B sensor via UART."""

    def __init__(self, serial_port: str):
        self._port        = serial_port
        self._available   = _MHZ19_AVAILABLE
        self._error_count = 0
        if self._available:
            logger.info("[MH-Z19] Configured on %s", serial_port)
        else:
            logger.warning("[MH-Z19] mh_z19 not available. Install: pip install mh-z19")

    def read(self) -> int | None:
        """Return CO2 in ppm, or None on failure."""
        if not self._available:
            return None
        try:
            result = mh_z19.read(serial_console_untouched=True)
            if not result or "co2" not in result:
                raise ValueError("Empty response from MH-Z19")
            co2 = int(result["co2"])
            validated = _validate(co2, VALID_CO2_RANGE, "co2")
            if validated is None:
                raise ValueError("Validation failed")
            self._error_count = 0
            return int(validated)
        except Exception as exc:
            self._error_count += 1
            logger.error("[MH-Z19] Read error (attempt %d): %s", self._error_count, exc)
            if self._error_count >= MAX_CONSECUTIVE_ERRORS:
                logger.warning(
                    "[MH-Z19] %d consecutive failures. Check serial port %s.",
                    self._error_count, self._port,
                )
        return None


# ------------------------------------------------------------------
# Main node class
# ------------------------------------------------------------------

class RaspberryPiPlantNode:
    """
    Reads all sensors on a single Raspberry Pi and publishes to MQTT.

    Each instance represents one plant in one greenhouse.

    Topic structure
    ---------------
    Published:
        greenhouse/{greenhouse_id}/plant/{plant_id}/temp
        greenhouse/{greenhouse_id}/plant/{plant_id}/humidity
        greenhouse/{greenhouse_id}/plant/{plant_id}/co2
        greenhouse/{greenhouse_id}/plant/{plant_id}/soil

    Subscribed (actuator commands):
        greenhouse/{greenhouse_id}/plant/{plant_id}/pump    -> ON / OFF
        greenhouse/{greenhouse_id}/plant/{plant_id}/window  -> OPEN / CLOSED
    """

    def __init__(
        self,
        broker_host: str   = DEFAULT_MQTT_HOST,
        broker_port: int   = DEFAULT_MQTT_PORT,
        greenhouse_id: int = DEFAULT_GREENHOUSE_ID,
        plant_id: int      = DEFAULT_PLANT_ID,
        dht_pin: int       = DHT22_GPIO_PIN,
        ads_address: int   = ADS1115_I2C_ADDR,
        ads_channel: int   = ADS1115_CHANNEL,
        co2_port: str      = MHZ19_SERIAL_PORT,
    ):
        self.broker_host   = broker_host
        self.broker_port   = broker_port
        self.greenhouse_id = greenhouse_id
        self.plant_id      = plant_id

        self._topic_base = f"greenhouse/{greenhouse_id}/plant/{plant_id}"

        self._dht  = DHT22Reader(dht_pin)
        self._soil = SoilMoistureReader(ads_address, ads_channel)
        self._co2  = CO2SensorReader(co2_port)

        self._connected = threading.Event()
        self._shutdown  = threading.Event()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected.set()
            logger.info("Connected to %s:%d", self.broker_host, self.broker_port)
            client.subscribe(f"{self._topic_base}/pump")
            client.subscribe(f"{self._topic_base}/window")
        else:
            logger.error("Connection failed: rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected.clear()
        if rc != 0:
            logger.warning("Unexpected disconnect (rc=%d). Auto-reconnect enabled.", rc)

    def _on_message(self, client, userdata, msg):
        actuator = msg.topic.split("/")[-1]
        payload  = msg.payload.decode()
        logger.info("Command: %s = %s", actuator, payload)

    # ------------------------------------------------------------------

    def _publish(self, metric: str, value: float) -> None:
        topic = f"{self._topic_base}/{metric}"
        self._client.publish(topic, int(value), qos=1)
        logger.info("%s = %.1f", topic, value)

    def publish_readings(self) -> None:
        if not self._connected.is_set():
            return

        dht = self._dht.read()
        if "temp" in dht:
            self._publish("temp",     dht["temp"])
        if "humidity" in dht:
            self._publish("humidity", dht["humidity"])

        soil = self._soil.read()
        if soil is not None:
            self._publish("soil", soil)

        co2 = self._co2.read()
        if co2 is not None:
            self._publish("co2", co2)

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

            logger.info(
                "Running  greenhouse=%d  plant=%d  interval=%ds",
                self.greenhouse_id, self.plant_id, interval,
            )
            logger.info("Press Ctrl+C to stop.")

            while not self._shutdown.is_set():
                self.publish_readings()
                self._shutdown.wait(timeout=interval)

        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            self._client.loop_stop()
            self._client.disconnect()
            if _GPIO_AVAILABLE:
                try:
                    GPIO.cleanup()
                except Exception:
                    pass
            logger.info("Disconnected")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Raspberry Pi Plant Node - reads sensors for one plant and publishes to MQTT",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host",          default=DEFAULT_MQTT_HOST)
    parser.add_argument("--port",          type=int, default=DEFAULT_MQTT_PORT)
    parser.add_argument("--greenhouse-id", type=int, default=DEFAULT_GREENHOUSE_ID,
                        help="Greenhouse this RPi belongs to")
    parser.add_argument("--plant-id",      type=int, default=DEFAULT_PLANT_ID,
                        help="Plant ID for this RPi node")
    parser.add_argument("--dht-pin",       type=int, default=DHT22_GPIO_PIN,
                        help="GPIO pin for DHT22")
    parser.add_argument("--ads-address",   type=lambda x: int(x, 0), default=ADS1115_I2C_ADDR,
                        help="I2C address for ADS1115 (e.g. 0x48)")
    parser.add_argument("--ads-channel",   type=int, default=ADS1115_CHANNEL,
                        help="ADS1115 channel for soil moisture")
    parser.add_argument("--co2-port",      default=MHZ19_SERIAL_PORT,
                        help="Serial port for MH-Z19 CO2 sensor")
    parser.add_argument("--interval",      type=int, default=DEFAULT_PUBLISH_INTERVAL)
    args = parser.parse_args()

    node = RaspberryPiPlantNode(
        broker_host=args.host,
        broker_port=args.port,
        greenhouse_id=args.greenhouse_id,
        plant_id=args.plant_id,
        dht_pin=args.dht_pin,
        ads_address=args.ads_address,
        ads_channel=args.ads_channel,
        co2_port=args.co2_port,
    )

    # Graceful shutdown on SIGINT / SIGTERM
    def _signal_handler(sig, frame):
        logger.info("Received signal %d, shutting down...", sig)
        node.request_shutdown()

    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    node.run(interval=args.interval)


if __name__ == "__main__":
    main()
