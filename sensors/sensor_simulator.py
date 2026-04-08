"""
Greenhouse Sensor Simulator
Simulates temperature, air humidity, and soil moisture sensors
Publishes data to MQTT in real-time
"""

import json
import time
import random
import argparse
import sys
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Install with: pip install paho-mqtt")
    sys.exit(1)


class GreenhouseSensorSimulator:
    """Simulates multiple sensors in a greenhouse"""
    
    def __init__(self, broker_host="localhost", broker_port=1883, 
                 greenhouse_id=1, num_plants=3):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.greenhouse_id = greenhouse_id
        self.num_plants = num_plants
        
        # Sensor state - with realistic greenhouse dynamics
        self.env_temp = 22.0  # °C
        self.env_humidity = 65.0  # %
        self.env_co2 = 800.0  # ppm
        
        self.plant_moisture = {}
        for i in range(1, num_plants + 1):
            self.plant_moisture[i] = random.uniform(40, 70)  # Start with adequate moisture
        
        self.pump_state = {}  # Track pump state for dynamics
        for i in range(1, num_plants + 1):
            self.pump_state[i] = False
        
        self.window_open = False
        
        # MQTT setup
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        
        self.connected = False
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback when client connects to broker"""
        if rc == 0:
            self.connected = True
            print(f"[Sensors] Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            
            # Subscribe to actuator topics to track state
            client.subscribe(f"greenhouse/{self.greenhouse_id}/plant/+/pump")
            client.subscribe(f"greenhouse/{self.greenhouse_id}/actuators/window")
        else:
            print(f"[Sensors] Connection failed with code {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        """Callback when client disconnects"""
        self.connected = False
        if rc != 0:
            print(f"[Sensors] Unexpected disconnection: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        topic = msg.topic
        payload = msg.payload.decode()
        
        print(f"[Sensors] Received actuator command: {topic} = {payload}")
        
        # Update pump state
        if "/pump" in topic:
            pump_id = int(topic.split("/")[-2])
            self.pump_state[pump_id] = (payload.upper() == "ON")
            if self.pump_state[pump_id]:
                print(f"  -> Pump {pump_id} activated")
            else:
                print(f"  -> Pump {pump_id} deactivated")
        
        # Update window state
        elif "window" in topic:
            self.window_open = (payload.upper() == "OPEN")
            status = "OPENED" if self.window_open else "CLOSED"
            print(f"  -> Ventilation window {status}")
    
    def simulate_environment_dynamics(self):
        """Simulate realistic environmental changes"""
        # Temperature changes down when window is open
        if self.window_open:
            self.env_temp -= random.uniform(0.1, 0.3)
        else:
            # Temperature increases gradually (simulating sun heating)
            self.env_temp += random.uniform(0.0, 0.2)
        
        # Constrain temperature
        self.env_temp = max(15, min(40, self.env_temp))
        
        # Humidity inversely related to temperature
        if self.window_open:
            self.env_humidity -= random.uniform(0.5, 1.5)
        else:
            self.env_humidity += random.uniform(0.0, 0.5)
        self.env_humidity = max(30, min(95, self.env_humidity))
        
        # CO2 increases naturally, decreases when window opens
        if self.window_open:
            self.env_co2 -= random.uniform(10, 30)
        else:
            self.env_co2 += random.uniform(5, 20)
        self.env_co2 = max(400, min(2000, self.env_co2))
        
        # Soil moisture changes based on pump state and time
        for plant_id in range(1, self.num_plants + 1):
            if self.pump_state.get(plant_id, False):
                # Increase moisture when pump is on
                self.plant_moisture[plant_id] += random.uniform(1, 3)
            else:
                # Decrease moisture gradually (plants drink and evaporation)
                self.plant_moisture[plant_id] -= random.uniform(0.3, 1)
            
            # Constrain moisture
            self.plant_moisture[plant_id] = max(0, min(100, self.plant_moisture[plant_id]))
    
    def publish_sensor_data(self):
        """Publish all sensor readings to MQTT"""
        if not self.connected:
            return
        
        try:
            # Publish environment data
            temp_topic = f"greenhouse/{self.greenhouse_id}/env/temp"
            self.client.publish(temp_topic, int(self.env_temp), qos=1)
            
            humidity_topic = f"greenhouse/{self.greenhouse_id}/env/humidity"
            self.client.publish(humidity_topic, int(self.env_humidity), qos=1)
            
            co2_topic = f"greenhouse/{self.greenhouse_id}/env/co2"
            self.client.publish(co2_topic, int(self.env_co2), qos=1)
            
            # Publish plant soil moisture
            for plant_id in range(1, self.num_plants + 1):
                soil_topic = f"greenhouse/{self.greenhouse_id}/plant/{plant_id}/soil"
                self.client.publish(soil_topic, int(self.plant_moisture[plant_id]), qos=1)
            
            # Log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [Sensors] Published sensor data:")
            print(f"  - Temperature: {self.env_temp:.1f}°C")
            print(f"  - Humidity: {self.env_humidity:.1f}%")
            print(f"  - CO2: {self.env_co2:.0f} ppm")
            for i in range(1, self.num_plants + 1):
                print(f"  - Plant {i} Moisture: {self.plant_moisture[i]:.1f}%")
            print()
            
        except Exception as e:
            print(f"[Sensors] Error publishing data: {e}")
    
    def run(self, publish_interval=5):
        """Main sensor simulator loop"""
        try:
            # Connect to broker
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = time.time() + 10
            while not self.connected and time.time() < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                print("[Sensors] ERROR: Could not connect to MQTT broker")
                return
            
            print(f"\n[Sensors] Simulator running. Publishing every {publish_interval}s")
            print(f"[Sensors] Greenhouse ID: {self.greenhouse_id}")
            print(f"[Sensors] Number of plants: {self.num_plants}")
            print("\nPress Ctrl+C to stop.\n")
            
            # Main loop
            while True:
                time.sleep(publish_interval)
                self.simulate_environment_dynamics()
                self.publish_sensor_data()
        
        except KeyboardInterrupt:
            print("\n[Sensors] Shutting down gracefully...")
        except Exception as e:
            print(f"[Sensors] Error: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            print("[Sensors] Disconnected")


def main():
    parser = argparse.ArgumentParser(
        description="Greenhouse Sensor Simulator - Publishes simulated sensor data to MQTT"
    )
    parser.add_argument("--host", default="localhost", 
                       help="MQTT broker host (default: localhost)")
    parser.add_argument("--port", type=int, default=1883, 
                       help="MQTT broker port (default: 1883)")
    parser.add_argument("--greenhouse-id", type=int, default=1, 
                       help="Greenhouse ID (default: 1)")
    parser.add_argument("--plants", type=int, default=3, 
                       help="Number of plants to simulate (default: 3)")
    parser.add_argument("--interval", type=int, default=5, 
                       help="Publishing interval in seconds (default: 5)")
    
    args = parser.parse_args()
    
    simulator = GreenhouseSensorSimulator(
        broker_host=args.host,
        broker_port=args.port,
        greenhouse_id=args.greenhouse_id,
        num_plants=args.plants
    )
    
    simulator.run(publish_interval=args.interval)


if __name__ == "__main__":
    main()
