import peewee
from flask import Blueprint, request, jsonify

from iam.application.services import AuthApplicationService

iam_api = Blueprint("iam_api", __name__)

_auth_service = AuthApplicationService()


@iam_api.route("/api/v1/devices/register", methods=["POST"])
def register_device():
    """Zero-touch provisioning: register a device using its MAC address as the API key.

    Request body (JSON):
        device_id (int, required)
        farm_id   (int, required)
        mac       (str, required): device MAC address, used as the api_key.

    Responses:
        200: Device registered (or already existing record returned).
        400: Missing required field.
    """
    data = request.json or {}
    try:
        device_id = int(data["device_id"])
        farm_id = int(data["farm_id"])
        mac = data["mac"]
        if not mac:
            raise KeyError("mac")
    except KeyError as exc:
        return jsonify({"error": f"Missing required field: {exc}"}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    device = _auth_service.register_device(device_id, farm_id, mac)
    return jsonify({
        "device_id": device.device_id,
        "farm_id": device.farm_id,
        "api_key": device.api_key,
    }), 200


@iam_api.route("/api/v1/devices/<int:device_id>/status", methods=["GET"])
def device_status(device_id: int):
    """Return whether a device is currently online (heartbeat/message seen within the last 60s)."""
    from iam.infrastructure.models import Device as DeviceModel
    from shared.infrastructure.device_tracker import is_online

    try:
        row = DeviceModel.get(DeviceModel.device_id == device_id)
    except peewee.DoesNotExist:
        return jsonify({"error": "Device not found"}), 404

    return jsonify({
        "device_id": row.device_id,
        "farm_id": row.farm_id,
        "online": is_online(device_id),
    }), 200


def authenticate_request():
    """Validate device credentials for an incoming HTTP request.

    Extracts ``device_id`` from the JSON body and ``X-API-Key`` from headers,
    then delegates to the IAM application service.

    Returns:
        tuple[Response, int] | None: 401 tuple on failure; None on success.
    """
    body = request.json or {}
    device_id = body.get("device_id")
    api_key = request.headers.get("X-API-Key")

    if device_id is None or not api_key:
        return jsonify({"error": "Missing device_id or X-API-Key"}), 401

    try:
        device_id = int(device_id)
    except (TypeError, ValueError):
        return jsonify({"error": "device_id must be an integer"}), 401

    if not _auth_service.authenticate(device_id, api_key):
        return jsonify({"error": "Invalid device_id or API key"}), 401

    return None