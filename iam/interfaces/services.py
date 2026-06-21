from flask import Blueprint, request, jsonify

from iam.application.services import AuthApplicationService
from iam.infrastructure.repositories import DeviceRepository

iam_api = Blueprint("iam_api", __name__)

_auth_service = AuthApplicationService()


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


@iam_api.route("/api/v1/devices/register", methods=["POST"])
def register_device():
    """Pre-register a device by MAC address before first MQTT contact.

    Request body (JSON):
        device_id  (int, required): Backend device ID.
        farm_id    (int, required): Farm this device belongs to.
        mac        (str, required): WiFi MAC address — used as api_key.

    Responses:
        201: Device registered (new).
        200: Device already registered (idempotent); api_key updated if MAC changed.
        400: Missing or invalid fields.
    """
    data = request.json or {}
    try:
        device_id = int(data["device_id"])
        farm_id   = int(data["farm_id"])
        mac       = str(data["mac"]).upper().strip()
    except KeyError as exc:
        return jsonify({"error": f"Missing required field: {exc}"}), 400
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    if not mac:
        return jsonify({"error": "mac must not be empty"}), 400

    device = DeviceRepository.find_or_create_by_mac(device_id, farm_id, mac)
    return jsonify({
        "device_id": device.device_id,
        "farm_id":   device.farm_id,
        "api_key":   device.api_key,
    }), 200


@iam_api.route("/api/v1/devices/<int:device_id>/status", methods=["GET"])
def device_status(device_id: int):
    """Return registration status for a device.

    Responses:
        200: Device found — returns device info and online status.
        404: Device not registered on this edge.
    """
    from shared.infrastructure.device_tracker import is_online
    from iam.infrastructure.models import Device as DeviceModel
    import peewee

    try:
        row = DeviceModel.get(DeviceModel.device_id == device_id)
    except peewee.DoesNotExist:
        return jsonify({"error": "Device not registered"}), 404

    return jsonify({
        "device_id": row.device_id,
        "farm_id":   row.farm_id,
        "api_key":   row.api_key,
        "online":    is_online(device_id),
    }), 200