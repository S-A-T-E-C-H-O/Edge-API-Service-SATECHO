from flask import Blueprint, request, jsonify

from iam.interfaces.services import authenticate_request
from pir.application.services import PirEventApplicationService

pir_api = Blueprint("pir_api", __name__)

_pir_service = PirEventApplicationService()


@pir_api.route("/api/v1/pir-monitoring/events", methods=["POST"])
def create_pir_event():
    """Record a PIR detection event, classify it, and publish to MQTT.

    Request headers:
        X-API-Key (required): API key registered for the device.

    Request body (JSON):
        device_id           (int, required):   Backend device ID.
        farm_id             (int, required):   Farm this device belongs to.
        zone_id             (int, optional):   Irrigation zone.
        pulse_duration_ms   (float, required): Duration PIR pin stayed HIGH (ms).
        triggers_per_minute (int, required):   Detection count in last 60 s window.
        recorded_at         (str, optional):   ISO 8601 timestamp; defaults to now (UTC).

    Responses:
        201: Event classified, saved, and published.
             Body includes ``classification``: "WIND" | "ANIMAL" | "PERSON".
        400: Missing/invalid fields.
        401: Missing or invalid device credentials.
    """
    auth_result = authenticate_request()
    if auth_result:
        return auth_result

    data = request.json or {}
    try:
        device_id           = int(data["device_id"])
        farm_id             = int(data["farm_id"])
        zone_id             = int(data["zone_id"]) if data.get("zone_id") is not None else None
        pulse_duration_ms   = data["pulse_duration_ms"]
        triggers_per_minute = int(data["triggers_per_minute"])
        recorded_at         = data.get("recorded_at")
    except KeyError as exc:
        return jsonify({"error": f"Missing required field: {exc}"}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        event = _pir_service.record_event(
            device_id, farm_id, zone_id,
            pulse_duration_ms, triggers_per_minute, recorded_at,
            request.headers.get("X-API-Key"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "id": event.id,
        "device_id": event.device_id,
        "farm_id": event.farm_id,
        "zone_id": event.zone_id,
        "pulse_duration_ms": event.pulse_duration_ms,
        "triggers_per_minute": event.triggers_per_minute,
        "classification": event.classification.value,
        "recorded_at": event.recorded_at.isoformat() + "Z",
    }), 201