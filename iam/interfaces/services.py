from flask import Blueprint, request, jsonify

from iam.application.services import AuthApplicationService

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