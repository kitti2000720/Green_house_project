"""
Physics / dynamics model for a single Raspberry Pi plant node.

Each node (one RPi, one plant) has its own local environment:
  - soil moisture   : affected by pump state
  - temperature     : affected by ventilation state
  - humidity        : affected by ventilation state
  - CO2             : affected by ventilation state

Call step() once per simulation tick to advance the state.
"""

import random


class PlantNodeDynamics:
    """
    Simulates all sensors on a single Raspberry Pi plant node.

    This replaces the previous split between EnvironmentDynamics
    and PlantDynamics.  With the new architecture (1 RPi per plant)
    every node is responsible for its own temperature, humidity, CO2
    and soil moisture readings.

    Typical actuator feedback
    -------------------------
    pump_on = True   -> soil moisture rises
    window_open = True -> temperature, humidity and CO2 drop
    """

    # Physical limits for each measurement
    TEMP_MIN     = 15.0
    TEMP_MAX     = 40.0
    HUMIDITY_MIN = 30.0
    HUMIDITY_MAX = 95.0
    CO2_MIN      = 400.0
    CO2_MAX      = 2000.0
    SOIL_MIN     = 0.0
    SOIL_MAX     = 100.0

    def __init__(
        self,
        initial_temp: float     = None,
        initial_humidity: float = None,
        initial_co2: float      = None,
        initial_soil: float     = None,
    ):
        # Slight random variation between nodes so each plant differs
        self.temp     = initial_temp     if initial_temp     is not None else random.uniform(20.0, 25.0)
        self.humidity = initial_humidity if initial_humidity is not None else random.uniform(55.0, 75.0)
        self.co2      = initial_co2      if initial_co2      is not None else random.uniform(700.0, 900.0)
        self.soil     = initial_soil     if initial_soil     is not None else random.uniform(40.0,  70.0)

        self.pump_on     = False
        self.window_open = False

    # ------------------------------------------------------------------
    # Actuator control
    # ------------------------------------------------------------------

    def set_pump(self, on: bool) -> None:
        self.pump_on = on

    def set_window(self, open_state: bool) -> None:
        self.window_open = open_state

    # ------------------------------------------------------------------
    # Simulation step
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance all sensor values by one simulation tick."""

        # Temperature: rises naturally, drops when window is open
        if self.window_open:
            self.temp -= random.uniform(0.1, 0.3)
        else:
            self.temp += random.uniform(0.0, 0.2)

        # Humidity: rises when window is closed, drops when open
        if self.window_open:
            self.humidity -= random.uniform(0.5, 1.5)
        else:
            self.humidity += random.uniform(0.0, 0.5)

        # CO2: rises naturally (plant respiration), drops when window opens
        if self.window_open:
            self.co2 -= random.uniform(10.0, 30.0)
        else:
            self.co2 += random.uniform(5.0, 20.0)

        # Soil moisture: rises when pump is on, dries out otherwise
        if self.pump_on:
            self.soil += random.uniform(1.0, 3.0)
        else:
            self.soil -= random.uniform(0.3, 1.0)

        # Clamp all values to physical limits
        self.temp     = max(self.TEMP_MIN,     min(self.TEMP_MAX,     self.temp))
        self.humidity = max(self.HUMIDITY_MIN, min(self.HUMIDITY_MAX, self.humidity))
        self.co2      = max(self.CO2_MIN,      min(self.CO2_MAX,      self.co2))
        self.soil     = max(self.SOIL_MIN,     min(self.SOIL_MAX,     self.soil))

    # ------------------------------------------------------------------
    # Convenience accessor
    # ------------------------------------------------------------------

    @property
    def readings(self) -> dict:
        """Return all current sensor readings as a plain dict."""
        return {
            "temp":     self.temp,
            "humidity": self.humidity,
            "co2":      self.co2,
            "soil":     self.soil,
        }
