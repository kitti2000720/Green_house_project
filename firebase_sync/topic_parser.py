"""
MQTT topic parser and alert generator.

Responsibilities
----------------
- Parse a raw MQTT topic string into a structured dict.
- Check whether the value breaches a threshold and return alert dicts.

To add a new alert rule: add an entry to ALERT_THRESHOLDS.
To add a new topic category: extend parse_topic().
"""

from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
# Alert thresholds
# To add a rule: insert a key matching the metric name from the topic.
# ------------------------------------------------------------------

ALERT_THRESHOLDS: Dict[str, Dict[str, Any]] = {
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

def parse_topic(topic: str, value: str, greenhouse_id: int) -> Optional[Dict[str, Any]]:
    """
    Parse an MQTT topic into a structured record.

    Returns None when the topic does not belong to this greenhouse
    or has an unrecognised structure.

    Examples
    --------
    parse_topic("greenhouse/1/env/temp", "27", 1)
        -> {"category": "env", "metric": "temp", "value": "27"}

    parse_topic("greenhouse/1/plant/2/soil", "45", 1)
        -> {"category": "plant", "plant_id": 2, "metric": "soil", "value": "45"}
    """
    prefix = f"greenhouse/{greenhouse_id}/"
    if not topic.startswith(prefix):
        return None

    parts = topic[len(prefix):].split("/")

    if parts[0] == "env" and len(parts) == 2:
        return {"category": "env", "metric": parts[1], "value": value}

    if parts[0] == "plant" and len(parts) == 3:
        try:
            plant_id = int(parts[1])
        except ValueError:
            return None
        return {"category": "plant", "plant_id": plant_id, "metric": parts[2], "value": value}

    if parts[0] == "actuators" and len(parts) == 2:
        return {"category": "actuator", "name": parts[1], "value": value}

    if parts[0] == "status" and len(parts) == 2:
        return {"category": "status", "name": parts[1], "value": value}

    return None


def check_alerts(parsed: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return a list of alert dicts for a parsed topic record.

    An empty list means no thresholds were breached.
    """
    if not parsed:
        return []

    try:
        numeric = int(parsed["value"])
    except (ValueError, KeyError, TypeError):
        return []

    alerts = []
    metric = parsed.get("metric") or parsed.get("name", "")

    if metric not in ALERT_THRESHOLDS:
        return []

    rule = ALERT_THRESHOLDS[metric]

    if "max" in rule and numeric > rule["max"]:
        base = {
            "type":     rule["alert_type"],
            "message":  f"{metric}={numeric}{rule['unit']} exceeds limit {rule['max']}{rule['unit']}",
            "severity": rule["severity"],
        }
        if parsed.get("plant_id") is not None:
            base["plant_id"] = parsed["plant_id"]
        alerts.append(base)

    if "min" in rule and numeric < rule["min"]:
        base = {
            "type":     rule["alert_type"],
            "message":  f"{metric}={numeric}{rule['unit']} below minimum {rule['min']}{rule['unit']}",
            "severity": rule["severity"],
        }
        if parsed.get("plant_id") is not None:
            base["plant_id"] = parsed["plant_id"]
        alerts.append(base)

    return alerts
