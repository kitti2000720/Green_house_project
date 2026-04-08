"""
Raspberry Pi Greenhouse Sensor Reader
Reads real sensors and publishes to MQTT broker

Supported Sensors:
- DHT22: Temperature + Humidity (GPIO 17)
- Analog soil moisture via ADC (I2C 0x48 or SPI)
- Optional: Light sensor (TSL2561 via I2C)
"""

import json
import time
import sys
import argparse
from datetime import datetime
from typing import Dict, Optional

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Install with: pip install paho-mqtt")
    sys.exit(1)

# Optional sensor libraries
try:
    import Adafruit_DHT
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    print("⚠ Warning: DHT library not available. Install: pip install Adafruit_DHT")

try:
    import board
    import busio
    import adafruit_ads1x15.analog_in as AnalogIn
    from adafruit_ads1x15.analog_in import AnalogIn
    from adafruit_ads1x15.ads1115 import ADS1115
    ADS_AVAILABLE = True
except ImportError:
    ADS_AVAILABLE = False
    print("⚠ Warning: ADS1115 libraries not available. Install: pip install adafruit-circuitpython-ads1x15")

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠ Warning: GPIO libraries not available. Install: pip install RPi.GPIO")


class RaspberryPiSensorReader:
    """Reads real sensors from Raspberry Pi and publishes via MQTT"""
    
    def __init__(self, mqtt_broker_host="localhost", mqtt_broker_port=1883,
                 greenhouse_id=1, dht_pin=17, ads_address=0x48):
        self.mqtt_host = mqtt_broker_host
        self.mqtt_port = mqtt_broker_port
        self.greenhouse_id = greenhouse_id
        self.dht_pin = dht_pin
        self.ads_address = ads_address
        
        # MQTT client setup
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_connected = False
        
        # Sensor setup
        self.dht_sensor = None
        self.ads = None
        self.sensors_configured = False
        self.configure_sensors()
    
    def configure_sensors(self):
        """Setup real sensors"""
        print("[RaspberryPi] Configuring sensors...")
        
        # DHT22 Setup
        if DHT_AVAILABLE:
            try:
                self.dht_sensor = Adafruit_DHT.DHT22
                print(f"[RaspberryPi] ✅ DHT22 configured on GPIO {self.dht_pin}")
            except Exception as e:
                print(f"[RaspberryPi] ⚠ DHT22 error: {e}")
        else:
            print("[RaspberryPi] ⚠ DHT22 library not available")
        
        # ADC Setup (for soil moisture)
        if ADS_AVAILABLE:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.ads = ADS1115(i2c, address=self.ads_address)
                print(f"[RaspberryPi] ✅ ADS1115 ADC configured (address: 0x{self.ads_address:x})")
            except Exception as e:
                print(f"[RaspberryPi] ⚠ ADS1115 error: {e}")
        else:
            print("[RaspberryPi] ⚠ ADS1115 library not available")
        
        self.sensors_configured = (self.dht_sensor is not None or self.ads is not None)
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connect callback"""
        if rc == 0:
            self.mqtt_connected = True
            print(f"[RaspberryPi/MQTT] ✅ Connected to {self.mqtt_host}:{self.mqtt_port}")
        else:
            print(f"[RaspberryPi/MQTT] ❌ Connection failed: {rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self.mqtt_connected = False
        if rc != 0:
            print(f"[RaspberryPi/MQTT] ⚠ Unexpected disconnect: {rc}")
    
    def read_dht22(self) -> Dict[str, Optional[float]]:
        """Read DHT22 temperature and humidity"""
        result = {"temp": None, "humidity": None}
        
        if not DHT_AVAILABLE or self.dht_sensor is None:
            return result
        
        try:
            humidity, temperature = Adafruit_DHT.read_retry(self.dht_sensor, self.dht_pin)
            
            if humidity is not None and temperature is not None:
                result["temp"] = temperature
                result["humidity"] = humidity
                return result
        except Exception as e:
            print(f"[RaspberryPi] ⚠ DHT22 read error: {e}")
        
        return result
    
    def read_soil_moisture(self, channel=0) -> Optional[float]:
        """Read analog soil moisture sensor via ADS1115 ADC"""
        if not ADS_AVAILABLE or self.ads is None:
            return None
        
        try:
            # ADS1115 has 4 analog channels (A0-A3)
            if channel == 0:
                channel_obj = AnalogIn(self.ads, ADS1115.P0)  # A0
            elif channel == 1:
                channel_obj = AnalogIn(self.ads, ADS1115.P1)  # A1
            elif channel == 2:
                channel_obj = AnalogIn(self.ads, ADS1115.P2)  # A2
            else:
                channel_obj = AnalogIn(self.ads, ADS1115.P3)  # A3
            
            # Read voltage (0-3.3V typically for soil moisture)
            voltage = channel_obj.voltage
            
            # Convert to percentage (0-100%)
            # Typical: Dry ~1.0V, Wet ~2.5V
            min_voltage = 1.0
            max_voltage = 2.5
            percentage = max(0, min(100, (voltage - min_voltage) / (max_voltage - min_voltage) * 100))
            
            return percentage
        except Exception as e:
            print(f"[RaspberryPi] ⚠ Soil moisture read error (ch{channel}): {e}")
            return None
    
    def publish_sensor_data(self):
        """Read all sensors and publish to MQTT"""
        if not self.mqtt_connected:
            print("[RaspberryPi] ⚠ Not connected to MQTT")
            return
        
        try:
            timestamp = datetime.now().isoformat()
            
            # Read DHT22
            dht_data = self.read_dht22()
            
            if dht_data["temp"] is not None:
                temp_topic = f"greenhouse/{self.greenhouse_id}/env/temp"
                self.mqtt_client.publish(temp_topic, int(dht_data["temp"]), qos=1)
                print(f"📡 {temp_topic} = {dht_data['temp']:.1f}°C")
            
            if dht_data["humidity"] is not None:
                humidity_topic = f"greenhouse/{self.greenhouse_id}/env/humidity"
                self.mqtt_client.publish(humidity_topic, int(dht_data["humidity"]), qos=1)
                print(f"📡 {humidity_topic} = {dht_data['humidity']:.1f}%")
            
            # Read soil moisture for 3 plants (channels 0-2)
            for plant_id in range(1, 4):
                channel = plant_id - 1
                moisture = self.read_soil_moisture(channel)
                
                if moisture is not None:
                    soil_topic = f"greenhouse/{self.greenhouse_id}/plant/{plant_id}/soil"
                    self.mqtt_client.publish(soil_topic, int(moisture), qos=1)
                    print(f"📡 {soil_topic} = {moisture:.1f}%")
            
            print()
        
        except Exception as e:
            print(f"[RaspberryPi] ❌ Error publishing data: {e}")
    
    def run(self, publish_interval=5):
        """Main sensor reading loop"""
        try:
            # Connect to MQTT
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            timeout = time.time() + 10
            while not self.mqtt_connected and time.time() < timeout:
                time.sleep(0.1)
            
            if not self.mqtt_connected:
                print("[RaspberryPi] ❌ Could not connect to MQTT broker")
                return
            
            print(f"\n[RaspberryPi] Sensor readings starting (interval: {publish_interval}s)")
            print(f"[RaspberryPi] Greenhouse ID: {self.greenhouse_id}")
            print(f"[RaspberryPi] DHT22 on GPIO {self.dht_pin}")
            print(f"[RaspberryPi] ADS1115 on I2C address 0x{self.ads_address:x}")
            print("\nPress Ctrl+C to stop.\n")
            
            # Main loop
            while True:
                self.publish_sensor_data()
                time.sleep(publish_interval)
        
        except KeyboardInterrupt:
            print("\n[RaspberryPi] Shutting down...")
        except Exception as e:
            print(f"[RaspberryPi] ❌ Error: {e}")
        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
            # Cleanup GPIO
            if GPIO_AVAILABLE:
                try:
                    GPIO.cleanup()
                except:
                    pass
            
            print("[RaspberryPi] ✅ Disconnected")


def main():
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Greenhouse Sensor Reader - Reads real sensors and publishes to MQTT"
    )
    parser.add_argument("--mqtt-host", default="localhost",
                       help="MQTT broker host (default: localhost)")
    parser.add_argument("--mqtt-port", type=int, default=1883,
                       help="MQTT broker port (default: 1883)")
    parser.add_argument("--greenhouse-id", type=int, default=1,
                       help="Greenhouse ID (default: 1)")
    parser.add_argument("--dht-pin", type=int, default=17,
                       help="GPIO pin for DHT22 sensor (default: GPIO 17)")
    parser.add_argument("--ads-address", type=int, default=0x48,
                       help="I2C address for ADS1115 ADC (default: 0x48)")
    parser.add_argument("--interval", type=int, default=5,
                       help="Publishing interval in seconds (default: 5)")
    
    args = parser.parse_args()
    
    reader = RaspberryPiSensorReader(
        mqtt_broker_host=args.mqtt_host,
        mqtt_broker_port=args.mqtt_port,
        greenhouse_id=args.greenhouse_id,
        dht_pin=args.dht_pin,
        ads_address=args.ads_address
    )
    
    reader.run(publish_interval=args.interval)


if __name__ == "__main__":
    main()
