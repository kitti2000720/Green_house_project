# Master Makefile for Greenhouse Project

.PHONY: all install setup build run clean help test mosquitto-start mosquitto-stop sensor-start controller-start dashboard

help:
	@echo "🌱 Greenhouse Automation System - Build & Run Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install              Install system dependencies"
	@echo "  make setup                Setup Python virtual environment"
	@echo ""
	@echo "Building:"
	@echo "  make build                Compile all components"
	@echo "  make clean                Clean build artifacts"
	@echo ""
	@echo "Running:"
	@echo "  make run                  Start all services (requires WSL/Linux)"
	@echo "  make mosquitto-start      Start MQTT broker only"
	@echo "  make sensor-start         Start sensor simulator only"
	@echo "  make controller-start     Start RT controller only (requires sudo)"
	@echo "  make dashboard            Start web dashboard server"
	@echo ""
	@echo "Development:"
	@echo "  make test                 Run tests"
	@echo "  make lint                 Run code linters"
	@echo ""

all: build run

install:
	@echo "Installing system dependencies..."
	sudo apt update
	sudo apt install -y mosquitto mosquitto-clients
	sudo apt install -y build-essential gcc make cmake
	sudo apt install -y libmosquitto-dev libmosquitto0
	sudo apt install -y python3 python3-pip python3-venv
	@echo "✓ Dependencies installed"

setup: install
	@echo "Setting up Python virtual environment..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	@echo "✓ Virtual environment ready"
	@echo "  Activate with: source venv/bin/activate"

build: 
	@echo "Building RT Controller..."
	$(MAKE) -C rt_controller clean
	$(MAKE) -C rt_controller
	@echo "✓ RT Controller built"

clean:
	@echo "Cleaning build artifacts..."
	$(MAKE) -C rt_controller clean
	@echo "✓ Clean complete"

mosquitto-start:
	@echo "Starting MQTT Broker..."
	mosquitto -c config/mosquitto.conf -v

mosquitto-stop:
	@echo "Stopping MQTT Broker..."
	pkill mosquitto || true

sensor-start:
	@echo "Starting Sensor Simulator..."
	. venv/bin/activate && python3 sensors/sensor_simulator.py \
		--greenhouse-id 1 --plants 3 --interval 5

controller-start:
	@echo "Starting RT Controller (requires sudo for real-time scheduling)..."
	cd rt_controller && sudo ./greenhouse_controller

dashboard:
	@echo "Starting web dashboard server..."
	@echo "Dashboard URL: http://localhost:8000/dashboard/index.html"
	python3 -m http.server 8000

run:
	@echo "Starting all components..."
	@echo "This will run in foreground. Use Ctrl+C to stop all."
	@echo ""
	@./quickstart.sh

test:
	@echo "Running tests..."
	@echo "TODO: Add test suite"

lint:
	@echo "Running code linters..."
	@echo "  Python:"
	python3 -m pylint sensors/sensor_simulator.py firebase_sync/firebase_sync.py || true
	@echo "  C:"
	clang --analyze rt_controller/greenhouse_controller.c || true

.PHONY: help install setup build run clean mosquitto-start mosquitto-stop sensor-start controller-start dashboard test lint
