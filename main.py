"""Edge application entry point.

Starts all services in order:
  1. SQLite schema init + migrations
  2. MQTT client (background loop)
  3. Device ingest subscriber (raw ESP32 topics → processed relay)
  4. Actuator command subscriber (intercept + log backend→device commands)
  5. Heartbeat service (periodic cloud POST)
  6. Sync service (periodic soil + PIR cloud sync with retry queue)
  7. Flask HTTP API (blocking, serves soil and IAM endpoints)
"""

import logging
import os

from flask import Flask

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    from iam.interfaces.services import iam_api
    from soil.interfaces.services import soil_api

    app = Flask(__name__)
    app.register_blueprint(iam_api)
    app.register_blueprint(soil_api)
    return app


def main():
    from shared.infrastructure.database import init_db
    from shared.infrastructure.mqtt_client import get_mqtt_client
    from shared.infrastructure.device_ingest_subscriiber import start as start_device_ingest
    from shared.infrastructure.actuator_command_subscriber import start as start_actuator_subscriber
    from shared.infrastructure.heartbeat_service import start as start_heartbeat
    from shared.infrastructure.sync_service import start as start_sync

    logger.info("Edge starting up")

    init_db()
    logger.info("Database ready")

    get_mqtt_client()
    logger.info("MQTT client initialised")

    start_device_ingest()
    start_actuator_subscriber()
    start_heartbeat()
    start_sync()

    app = create_app()
    host = os.getenv("HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("HTTP_PORT", "5000"))
    logger.info("Starting HTTP server on %s:%s", host, port)
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
