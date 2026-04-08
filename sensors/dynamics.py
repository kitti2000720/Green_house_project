"""
Physics / dynamics models for the greenhouse simulation.

Each class is stateful and independent of MQTT or any I/O concern.
Call step() once per simulation tick to advance the state.
"""

import random


class EnvironmentDynamics:
    """
    Models temperature, humidity and CO2 inside a greenhouse.

    Behaviour
    ---------
    - Window open  : temperature and CO2 drop, humidity drops faster.
    - Window closed: temperature and CO2 rise slowly (sunlight + plants).
    """

    TEMP_MIN     = 15.0
    TEMP_MAX     = 40.0
    HUMIDITY_MIN = 30.0
    HUMIDITY_MAX = 95.0
    CO2_MIN      = 400.0
    CO2_MAX      = 2000.0

    def __init__(self):
        self.temp        = 22.0
        self.humidity    = 65.0
        self.co2         = 800.0
        self.window_open = False

    def set_window(self, open_state: bool) -> None:
        self.window_open = open_state

    def step(self) -> None:
        if self.window_open:
            self.temp     -= random.uniform(0.1, 0.3)
            self.humidity -= random.uniform(0.5, 1.5)
            self.co2      -= random.uniform(10, 30)
        else:
            self.temp     += random.uniform(0.0, 0.2)
            self.humidity += random.uniform(0.0, 0.5)
            self.co2      += random.uniform(5, 20)

        self.temp     = max(self.TEMP_MIN,     min(self.TEMP_MAX,     self.temp))
        self.humidity = max(self.HUMIDITY_MIN, min(self.HUMIDITY_MAX, self.humidity))
        self.co2      = max(self.CO2_MIN,      min(self.CO2_MAX,      self.co2))

    @property
    def readings(self) -> dict:
        return {
            "temp":     self.temp,
            "humidity": self.humidity,
            "co2":      self.co2,
        }


class PlantDynamics:
    """
    Models soil moisture for a single plant.

    Behaviour
    ---------
    - Pump on : moisture rises quickly.
    - Pump off: moisture drops slowly (evaporation + plant uptake).
    """

    MOISTURE_MIN = 0.0
    MOISTURE_MAX = 100.0

    def __init__(self, initial_moisture: float = None):
        self.moisture = (
            initial_moisture
            if initial_moisture is not None
            else random.uniform(40.0, 70.0)
        )
        self.pump_on = False

    def set_pump(self, on: bool) -> None:
        self.pump_on = on

    def step(self) -> None:
        if self.pump_on:
            self.moisture += random.uniform(1.0, 3.0)
        else:
            self.moisture -= random.uniform(0.3, 1.0)

        self.moisture = max(self.MOISTURE_MIN, min(self.MOISTURE_MAX, self.moisture))
