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

from dynamics import PlantNodeDynamics

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

try:
    from sense_hat import SenseHat as _SenseHat
    _SENSEHAT_AVAILABLE = True
except ImportError:
    _SENSEHAT_AVAILABLE = False

try:
    import adafruit_dht
    import board as _dht_board
    _DHT_AVAILABLE = True
    _DHT_LEGACY    = False
except ImportError:
    try:
        import Adafruit_DHT
        _DHT_AVAILABLE = True
        _DHT_LEGACY    = True
    except ImportError:
        _DHT_AVAILABLE = False
        _DHT_LEGACY    = False

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as _ADS_MOD
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

from config import (
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

class SenseHatReader:
    """Reads temperature and humidity from a Raspberry Pi Sense HAT."""

    def __init__(self):
        self._available = _SENSEHAT_AVAILABLE
        self._sense     = None
        if self._available:
            try:
                self._sense = _SenseHat()
                self._sense.clear()
                logger.info("[SenseHAT] Initialised")
            except Exception as exc:
                logger.warning("[SenseHAT] Init failed: %s", exc)
                self._available = False
        else:
            logger.warning("[SenseHAT] sense-hat not available. Install: pip install sense-hat")

    def read(self) -> dict:
        """Return {temp, humidity} from Sense HAT sensors, or {} on failure."""
        if not self._available:
            return {}
        try:
            temp     = self._sense.get_temperature()
            humidity = self._sense.get_humidity()

            t = _validate(temp,     VALID_TEMP_RANGE,     "temp")
            h = _validate(humidity, VALID_HUMIDITY_RANGE, "humidity")
            if t is None or h is None:
                return {}
            return {"temp": round(t, 1), "humidity": round(h, 1)}
        except Exception as exc:
            logger.error("[SenseHAT] Read error: %s", exc)
            return {}


class DHT22Reader:
    """Reads temperature and humidity from a DHT22 sensor via GPIO."""

    def __init__(self, gpio_pin: int):
        self._pin          = gpio_pin
        self._available    = _DHT_AVAILABLE
        self._error_count  = 0
        self._sensor       = None
        if self._available:
            if not _DHT_LEGACY:
                try:
                    pin = getattr(_dht_board, f"D{gpio_pin}")
                    self._sensor = adafruit_dht.DHT22(pin)
                except Exception as exc:
                    logger.warning("[DHT22] Init failed: %s", exc)
                    self._available = False
                    return
            logger.info("[DHT22] Configured on GPIO %d (legacy=%s)", gpio_pin, _DHT_LEGACY)
        else:
            logger.warning("[DHT22] DHT library not available.")

    def read(self) -> dict:
        """Return validated {temp, humidity} or {} on failure."""
        if not self._available:
            return {}
        try:
            if _DHT_LEGACY:
                humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, self._pin)
            else:
                temperature = self._sensor.temperature
                humidity    = self._sensor.humidity

            if humidity is None or temperature is None:
                raise ValueError("DHT22 returned None")

            temp = _validate(temperature, VALID_TEMP_RANGE,     "temp")
            hum  = _validate(humidity,    VALID_HUMIDITY_RANGE, "humidity")

            if temp is None or hum is None:
                raise ValueError("Validation failed")

            self._error_count = 0
            return {"temp": temp, "humidity": hum}

        except Exception:
            self._error_count += 1
            if self._error_count == MAX_CONSECUTIVE_ERRORS:
                logger.warning("[DHT22] No sensor found on GPIO %d — using simulation fallback.",
                               self._pin)
                self._available = False   # stop retrying
        return {}


class SoilMoistureReader:
    """Reads soil moisture from a capacitive sensor via ADS1115 ADC."""

    _CHANNEL_PINS = [0, 1, 2, 3]

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
        """Return CO2 in ppm, or None on failure. Disables itself after too many errors."""
        if not self._available:
            return None
        import os, io
        try:
            # Redirect stderr to suppress mh_z19's internal traceback output
            devnull = open(os.devnull, 'w')
            old_stderr = os.dup(2)
            os.dup2(devnull.fileno(), 2)
            try:
                result = mh_z19.read(serial_console_untouched=True)
            finally:
                os.dup2(old_stderr, 2)
                os.close(old_stderr)
                devnull.close()

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
            if self._error_count == MAX_CONSECUTIVE_ERRORS:
                logger.warning("[MH-Z19] No sensor found on %s — using simulation fallback.",
                               self._port)
                self._available = False   # stop retrying
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

        self._sense = SenseHatReader()
        self._dht   = DHT22Reader(dht_pin)    # fallback if no Sense HAT
        self._soil  = SoilMoistureReader(ads_address, ads_channel)
        self._co2  = CO2SensorReader(co2_port)

        self._dynamics = PlantNodeDynamics()

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
            client.subscribe(f"greenhouse/{self.greenhouse_id}/window")
            client.subscribe(f"greenhouse/{self.greenhouse_id}/co2_enricher")
        else:
            logger.error("Connection failed: rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected.clear()
        if rc != 0:
            logger.warning("Unexpected disconnect (rc=%d). Auto-reconnect enabled.", rc)

    def _on_message(self, client, userdata, msg):
        parts    = msg.topic.split("/")
        actuator = parts[-1]
        payload  = msg.payload.decode()
        logger.info("Command: %s = %s", actuator, payload)
        if actuator == "pump":
            self._dynamics.set_pump(payload.upper() == "ON")
        elif actuator == "window":
            self._dynamics.set_window(payload.upper() == "OPEN")
        elif actuator == "co2_enricher":
            self._dynamics.set_co2_enricher(payload.upper() == "ON")

    # ------------------------------------------------------------------

    def _publish(self, metric: str, value: float) -> None:
        topic = f"{self._topic_base}/{metric}"
        self._client.publish(topic, int(value), qos=1)
        logger.info("%s = %.1f", topic, value)

    def publish_readings(self) -> None:
        if not self._connected.is_set():
            return

        self._dynamics.step()
        sim = self._dynamics.readings

        # Sense HAT is primary; DHT22 is fallback; simulation is last resort
        sense = self._sense.read()
        dht   = self._dht.read() if not sense else {}
        temp  = sense.get("temp")     or dht.get("temp")
        hum   = sense.get("humidity") or dht.get("humidity")
        self._publish("temp",     temp if temp is not None else sim["temp"])
        self._publish("humidity", hum  if hum  is not None else sim["humidity"])

        soil = self._soil.read()
        self._publish("soil", soil if soil is not None else sim["soil"])

        co2 = self._co2.read()
        self._publish("co2",  co2  if co2  is not None else sim["co2"])

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
