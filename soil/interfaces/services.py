from flask import Blueprint, request, jsonify

from iam.interfaces.services import authenticate_request
from soil.application.services import SoilReadingApplicationService

soil_api = Blueprint("soil_api", __name__)

_soil_service = SoilReadingApplicationService()


def _extract_value(data: dict, *keys: str):
    """Return the first value found for any of the given keys, or None."""
    return next((data[k] for k in keys if k in data), None)


def _resolve_payload(data: dict) -> dict:
    """Resolve ESP32 field names to internal names; fall back to legacy names.

    Priority: ESP32 name first, then legacy name, then None.
    """
    MAPPED = [
        ("moisture",             "moisture",             "humidity_fc28"),
        ("ec",                   "ec",                   "salinity_hr202l"),
        ("temperature",          "temperature",          "soil_temp_ds18b20"),
        ("ambient_temperature",  None,                   "ambient_temp_dht11"),
        ("security_pir_status",  None,                   "security_pir_status"),
    ]
    resolved = {
        internal: _extract_value(data, esp32_key, legacy_key) if legacy_key else data.get(esp32_key)
        for internal, legacy_key, esp32_key in MAPPED
    }
    resolved["ph"] = data.get("ph", 7.0)
    return resolved


@soil_api.route("/api/v1/soil-monitoring/readings", methods=["POST"])
def create_reading():
    """Record a soil-sensor reading, persist locally, and publish to MQTT.

    Request headers:
        X-API-Key (required): API key registered for the device.

    Request body (JSON) — ESP32 field names (preferred) or legacy names:
        device_id           (int, required):   Backend device/sensor ID.
        farm_id             (int, required):   Farm this device belongs to.
        zone_id             (int, optional):   Irrigation zone.
        humidity_fc28       (float):           FC28 soil moisture [0, 100] %.
        salinity_hr202l     (float):           HR202L electrical conductivity.
        ambient_temp_dht11  (float):           DHT11 ambient air temperature °C.
        soil_temp_ds18b20   (float):           DS18B20 soil temperature °C.
        security_pir_status (str):             PIR security status.
        ph                  (float, optional): Soil pH [0, 14]; default 7.0.
        recorded_at         (str, optional):   ISO 8601 timestamp.

    Legacy field names also accepted: moisture, ec, temperature.

    Responses:
        201: Reading saved and published.
        400: Missing/invalid fields or sensor values out of range.
        401: Missing or invalid device credentials.
    """
    auth_result = authenticate_request()
    if auth_result:
        return auth_result

    data = request.json or {}
    try:
        device_id   = int(data["device_id"])
        farm_id     = int(data["farm_id"])
        zone_id     = int(data["zone_id"]) if data.get("zone_id") is not None else None
        recorded_at = data.get("recorded_at")
    except KeyError as exc:
        return jsonify({"error": f"Missing required field: {exc}"}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    resolved = _resolve_payload(data)

    try:
        reading = _soil_service.record_reading(
            device_id, farm_id, zone_id,
            resolved["moisture"], resolved["ec"], resolved["ph"], resolved["temperature"],
            recorded_at,
            request.headers.get("X-API-Key"),
            ambient_temperature=resolved["ambient_temperature"],
            security_pir_status=resolved["security_pir_status"],
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "id": reading.id,
        "device_id": reading.device_id,
        "farm_id": reading.farm_id,
        "zone_id": reading.zone_id,
        "moisture": reading.moisture,
        "ec": reading.ec,
        "ph": reading.ph,
        "temperature": reading.temperature,
        "ambient_temperature": reading.ambient_temperature,
        "security_pir_status": reading.security_pir_status,
        "recorded_at": reading.recorded_at.isoformat() + "Z",
    }), 201