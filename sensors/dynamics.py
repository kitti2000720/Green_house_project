import random


METRIC_NAMES = ["temp", "humidity", "co2", "soil"]


class PlantNodeDynamics:
    """Simulates the environmental dynamics of a plant node in a greenhouse."""

    TEMP_MIN = 15.0
    TEMP_MAX = 40.0
    HUMIDITY_MIN = 30.0
    HUMIDITY_MAX = 95.0
    CO2_MIN = 400.0
    CO2_MAX = 2000.0
    SOIL_MIN = 0.0
    SOIL_MAX = 100.0

    def __init__(
        self,
        initial_temp: float = None,
        initial_humidity: float = None,
        initial_co2: float = None,
        initial_soil: float = None,
    ):
        self.temp     = initial_temp     if initial_temp     is not None else random.uniform(20.0, 25.0)
        self.humidity = initial_humidity if initial_humidity is not None else random.uniform(55.0, 75.0)
        self.co2 = initial_co2 if initial_co2 is not None else random.uniform(700.0, 900.0)
        self.soil = initial_soil if initial_soil is not None else random.uniform(40.0, 70.0)

        self.pump_on = False
        self.window_open = False
        self.co2_enricher = False

    def set_pump(self, on: bool) -> None:
        """Update the pump actuator state."""
        self.pump_on = on

    def set_window(self, open_state: bool) -> None:
        """Update the window actuator state."""
        self.window_open = open_state

    def set_co2_enricher(self, on: bool) -> None:
        """Update the CO2 enricher actuator state."""
        self.co2_enricher = on

    def step(self) -> None:
        """Advance the simulation state by one time step."""
        if self.window_open:
            self.temp -= random.uniform(0.1, 0.3)
            self.humidity -= random.uniform(0.5, 1.5)
        else:
            self.temp += random.uniform(0.0, 0.2)
            self.humidity += random.uniform(0.0, 0.5)

        if self.window_open:
            self.co2 -= random.uniform(10.0, 30.0)
        elif self.co2_enricher:
            self.co2 += random.uniform(20.0, 40.0)
        else:
            self.co2 += random.uniform(5.0, 20.0)

        if self.pump_on:
            self.soil += random.uniform(1.0, 3.0)
        else:
            self.soil -= random.uniform(0.3, 1.0)

        self.temp = max(self.TEMP_MIN, min(self.TEMP_MAX, self.temp))
        self.humidity = max(self.HUMIDITY_MIN, min(self.HUMIDITY_MAX, self.humidity))
        self.co2 = max(self.CO2_MIN, min(self.CO2_MAX, self.co2))
        self.soil = max(self.SOIL_MIN, min(self.SOIL_MAX, self.soil))

    @property
    def readings(self) -> dict[str, float]:
        """Return the current sensor readings as a dictionary."""
        return {
            "temp": self.temp,
            "humidity": self.humidity,
            "co2": self.co2,
            "soil": self.soil,
        }
