from typing import Any

ALERT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "temp": {"max": 30, "unit": "C", "alert_type": "HIGH_TEMP", "severity": "critical"},
    "co2": {"max": 1500, "unit": "ppm", "alert_type": "HIGH_CO2", "severity": "critical"},
    "soil": {"min": 30, "unit": "%", "alert_type": "LOW_MOISTURE", "severity": "warning"},
}


def parse_topic(topic: str, value: str, greenhouse_id: int) -> dict[str, Any] | None:
    """Parse an MQTT topic into a structured dictionary."""
    prefix = f"greenhouse/{greenhouse_id}/"
    if not topic.startswith(prefix):
        return None

    parts = topic[len(prefix):].split("/")

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


def check_alerts(parsed: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not parsed or parsed["category"] != "plant":
        return []

    metric = parsed.get("metric", "")
    if metric not in ALERT_THRESHOLDS:
        return []

    try:
        numeric = int(parsed["value"])
    except (ValueError, TypeError):
        return []

    rule = ALERT_THRESHOLDS[metric]
    alerts = []

    if "max" in rule and numeric > rule["max"]:
        alerts.append({
            "type": rule["alert_type"],
            "plant_id": parsed["plant_id"],
            "message": f"plant[{parsed['plant_id']}] {metric}={numeric}{rule['unit']} exceeds {rule['max']}{rule['unit']}",
            "severity": rule["severity"],
        })

    if "min" in rule and numeric < rule["min"]:
        alerts.append({
            "type": rule["alert_type"],
            "plant_id": parsed["plant_id"],
            "message": f"plant[{parsed['plant_id']}] {metric}={numeric}{rule['unit']} below {rule['min']}{rule['unit']}",
            "severity": rule["severity"],
        })

    return alerts
