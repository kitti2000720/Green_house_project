"""
Sensor module default configuration.
Override values by passing arguments to the entry-point scripts.

Multi-greenhouse support
------------------------
The simulator can manage several independent greenhouses in one process.
Each greenhouse has its own set of plant nodes.
Use --num-greenhouses N (or --greenhouse-ids 1,2,3) on the CLI.

Single RPi deployment
---------------------
Each physical Raspberry Pi runs rpi_sensor_reader.py with
  --greenhouse-id <id> --plant-id <id>
so it belongs to exactly one greenhouse / one plant.
"""

# --- MQTT broker ---
DEFAULT_MQTT_HOST         = "localhost"
DEFAULT_MQTT_PORT         = 1883

DEFAULT_GREENHOUSE_ID     = 1
DEFAULT_NUM_GREENHOUSES   = 1
DEFAULT_PLANT_ID          = 1
DEFAULT_NUM_PLANTS        = 3
DEFAULT_PUBLISH_INTERVAL  = 5   # seconds

# --- Raspberry Pi hardware pin / bus defaults ---
DHT22_GPIO_PIN     = 17
ADS1115_I2C_ADDR   = 0x48
ADS1115_CHANNEL    = 0
MHZ19_SERIAL_PORT  = "/dev/ttyS0"

# --- Soil moisture voltage calibration ---
SOIL_VOLTAGE_DRY   = 1.0    # volts at 0% moisture
SOIL_VOLTAGE_WET   = 2.5    # volts at 100% moisture

# --- Sensor sanity-check bounds (values outside these are rejected) ---
VALID_TEMP_RANGE     = (-10.0, 60.0)    # °C
VALID_HUMIDITY_RANGE = (  0.0, 100.0)   # %
VALID_CO2_RANGE      = (300,   5000)    # ppm
VALID_SOIL_RANGE     = (  0.0, 100.0)   # %
