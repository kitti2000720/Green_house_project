.PHONY: all install setup build run clean help test lint \
        mosquitto-start mosquitto-stop sensor-start rpi-node controller-start \
        firebase-sync dashboard

help:
	@echo "Greenhouse Automation System - Build and Run Commands"
	@echo ""
	@echo "Setup and Installation:"
	@echo "  make install              Install system dependencies (requires sudo)"
	@echo "  make setup                Setup Python virtual environment"
	@echo ""
	@echo "Building:"
	@echo "  make build                Compile the RT controller"
	@echo "  make clean                Remove build artifacts"
	@echo ""
	@echo "Running individual components:"
	@echo "  make mosquitto-start      Start MQTT broker"
	@echo "  make sensor-start         Start sensor simulator (simulates all plant nodes)"
	@echo "  make rpi-node             Start a single real RPi plant node (run on each RPi)"
	@echo "  make controller-start     Start RT controller (requires sudo)"
	@echo "  make firebase-sync        Start Firebase sync (requires credentials file)"
	@echo "  make dashboard            Start web dashboard HTTP server"
	@echo ""
	@echo "Running everything:"
	@echo "  make run                  Start all components via quickstart.sh"
	@echo ""
	@echo "Development:"
	@echo "  make test                 Run tests"
	@echo "  make lint                 Run code linters"
	@echo ""

all: build run

# ------------------------------------------------------------------

install:
	@echo "Installing system dependencies..."
	sudo apt update
	sudo apt install -y mosquitto mosquitto-clients
	sudo apt install -y build-essential gcc make
	sudo apt install -y libmosquitto-dev
	sudo apt install -y python3 python3-pip python3-venv
	@echo "Done."

setup: install
	@echo "Setting up Python virtual environment..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	@echo "Virtual environment ready."
	@echo "Activate with: source venv/bin/activate"

# ------------------------------------------------------------------

build:
	@echo "Building RT Controller..."
	$(MAKE) -C rt_controller clean
	$(MAKE) -C rt_controller
	@echo "Build complete."

clean:
	@echo "Cleaning build artifacts..."
	$(MAKE) -C rt_controller clean
	@echo "Done."

# ------------------------------------------------------------------

mosquitto-start:
	@echo "Starting MQTT Broker..."
	mosquitto -c config/mosquitto.conf -v

mosquitto-stop:
	@echo "Stopping MQTT Broker..."
	pkill mosquitto || true

sensor-start:
	@echo "Starting Sensor Simulator (2 greenhouses x 3 plants)..."
	. venv/bin/activate && python3 sensors/sensor_simulator.py \
		--num-greenhouses 2 --plants 3 --interval 5

# Start a single real RPi node (run this on each physical Raspberry Pi)
rpi-node:
	@echo "Starting RPi Plant Node..."
	. venv/bin/activate && python3 sensors/rpi_sensor_reader.py \
		--greenhouse-id 1 --plant-id 1 --interval 5

controller-start:
	@echo "Starting RT Controller (requires sudo for real-time scheduling)..."
	cd rt_controller && sudo ./greenhouse_controller

firebase-sync:
	@echo "Starting Firebase Sync Service (greenhouses 1,2)..."
	. venv/bin/activate && python3 firebase_sync/firebase_sync.py \
		--credentials green-house-d7b7f-firebase-adminsdk-fbsvc-bf0cb07c7c.json \
		--firebase-url https://green-house-d7b7f-default-rtdb.europe-west1.firebasedatabase.app \
		--greenhouse-ids 1,2

dashboard:
	@echo "Starting web dashboard server..."
	@echo "Dashboard URL: http://localhost:8000/dashboard/index.html"
	python3 -m http.server 8000

run:
	@echo "Starting all components..."
	@./quickstart.sh

# ------------------------------------------------------------------

test:
	@echo "Running tests..."
	@echo "TODO: Add test suite"

lint:
	@echo "Linting Python..."
	python3 -m pylint sensors/sensor_simulator.py \
	                  firebase_sync/firebase_sync.py \
	                  firebase_sync/firebase_client.py \
	                  firebase_sync/topic_parser.py || true
	@echo "Linting C..."
	clang --analyze rt_controller/greenhouse_controller.c \
	                rt_controller/mqtt_handler.c \
	                rt_controller/rules.c \
	                rt_controller/rt_scheduler.c || true
