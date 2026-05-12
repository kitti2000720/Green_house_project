"""
MQTT topic parser and alert generator.

Architecture note
-----------------
Each Raspberry Pi node publishes all its sensor readings under
the per-plant prefix:

    greenhouse/{id}/plant/{plant_id}/{metric}

There are no shared env/ topics anymore.  Every metric (temp,
humidity, co2, soil) belongs to exactly one plant node.

To add a new alert rule : add an entry to ALERT_THRESHOLDS.
To add a new topic category: extend parse_topic().
"""

from typing import Any


# ------------------------------------------------------------------
# Alert thresholds
#
# Key   = metric name as it appears in the MQTT topic suffix.
# Value = threshold dict with optional "min" and/or "max" keys.
# ------------------------------------------------------------------

ALERT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "temp": {
        "max":        30,
        "unit":       "C",
        "alert_type": "HIGH_TEMP",
        "severity":   "critical",
    },
    "co2": {
        "max":        1500,
        "unit":       "ppm",
        "alert_type": "HIGH_CO2",
        "severity":   "critical",
    },
    "soil": {
        "min":        30,
        "unit":       "%",
        "alert_type": "LOW_MOISTURE",
        "severity":   "warning",
    },
}


# ------------------------------------------------------------------
# Topic parsing
# ------------------------------------------------------------------

def parse_topic(topic: str, value: str, greenhouse_id: int) -> dict[str, Any] | None:
    """
    Parse an MQTT topic into a structured record.

    Returns None when the topic does not belong to this greenhouse
    or has an unrecognized structure.

    Recognized patterns
    -------------------
    greenhouse/{id}/plant/{plant_id}/{metric}
        -> {"category": "plant", "plant_id": int, "metric": str, "value": str}

    greenhouse/{id}/actuators/{name}
        -> {"category": "actuator", "name": str, "value": str}

    greenhouse/{id}/status/{name}
        -> {"category": "status", "name": str, "value": str}

    Examples
    --------
    parse_topic("greenhouse/1/plant/2/temp", "27", 1)
        -> {"category": "plant", "plant_id": 2, "metric": "temp", "value": "27"}

    parse_topic("greenhouse/1/plant/3/soil", "22", 1)
        -> {"category": "plant", "plant_id": 3, "metric": "soil", "value": "22"}
    """
    prefix = f"greenhouse/{greenhouse_id}/"
    if not topic.startswith(prefix):
        return None

    parts = topic[len(prefix):].split("/")

    if parts[0] == "plant" and len(parts) == 3:
        try:
            plant_id = int(parts[1])
        except ValueError:
            return None
        return {
            "category": "plant",
            "plant_id": plant_id,
            "metric":   parts[2],
            "value":    value,
        }

    if parts[0] == "actuators" and len(parts) == 2:
        return {"category": "actuator", "name": parts[1], "value": value}

    if parts[0] == "status" and len(parts) == 2:
        return {"category": "status", "name": parts[1], "value": value}

    return None


def check_alerts(parsed: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Return a list of alert dicts for a parsed topic record.

    An empty list means no thresholds were breached.
    """
    if not parsed or parsed["category"] != "plant":
        return []

    metric = parsed.get("metric", "")
    if metric not in ALERT_THRESHOLDS:
        return []

    try:
        numeric = int(parsed["value"])
    except (ValueError, TypeError):
        return []

    rule   = ALERT_THRESHOLDS[metric]
    alerts = []

    if "max" in rule and numeric > rule["max"]:
        alerts.append({
            "type":     rule["alert_type"],
            "plant_id": parsed["plant_id"],
            "message":  (
                f"plant[{parsed['plant_id']}] {metric}={numeric}{rule['unit']} "
                f"exceeds limit {rule['max']}{rule['unit']}"
            ),
            "severity": rule["severity"],
        })

    if "min" in rule and numeric < rule["min"]:
        alerts.append({
            "type":     rule["alert_type"],
            "plant_id": parsed["plant_id"],
            "message":  (
                f"plant[{parsed['plant_id']}] {metric}={numeric}{rule['unit']} "
                f"below minimum {rule['min']}{rule['unit']}"
            ),
            "severity": rule["severity"],
        })

    return alerts
