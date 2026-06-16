import logging
import os
import threading
import time

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

_client: mqtt.Client | None = None
_lock = threading.Lock()
_handlers: dict[str, callable] = {}


def get_mqtt_client() -> mqtt.Client:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = _create_client()
    return _client


def register_handler(topic: str, handler: callable) -> None:
    """Register a message handler for a topic (supports + and # wildcards).
    Re-subscribes immediately if the client is already connected.
    """
    _handlers[topic] = handler
    client = get_mqtt_client()
    client.subscribe(topic, qos=1)
    logger.info("MQTT subscribed to %s", topic)


def _create_client() -> mqtt.Client:
    host = os.getenv("MQTT_BROKER_HOST", "localhost")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    username = os.getenv("MQTT_BROKER_USERNAME", "")
    password = os.getenv("MQTT_BROKER_PASSWORD", "")

    client = mqtt.Client(client_id="agrosafe-edge", clean_session=False)

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected to %s:%s", host, port)
            for t in _handlers:
                c.subscribe(t, qos=1)
                logger.info("MQTT re-subscribed to %s", t)
        else:
            codes = {
                1: "wrong protocol version",
                2: "invalid client ID",
                3: "broker unavailable",
                4: "bad credentials",
                5: "not authorised",
            }
            logger.error("MQTT connect refused — %s (rc=%s)", codes.get(rc, "unknown"), rc)

    def on_disconnect(c, userdata, rc):
        if rc != 0:
            logger.warning("MQTT disconnected unexpectedly (rc=%s) — scheduling reconnect", rc)
            threading.Thread(target=_reconnect_loop, args=(c, host, port), daemon=True).start()
        else:
            logger.info("MQTT disconnected cleanly")

    def on_publish(c, userdata, mid):
        logger.debug("MQTT publish confirmed mid=%s", mid)

    def on_message(c, userdata, msg):
        topic = msg.topic
        try:
            payload = msg.payload.decode("utf-8", errors="replace")
        except Exception:
            payload = ""
        for pattern, handler in list(_handlers.items()):
            if _topic_matches(pattern, topic):
                try:
                    handler(topic, payload)
                except Exception as exc:
                    logger.error("Handler error for topic %s: %s", topic, exc)
                return
        logger.debug("No handler registered for topic %s", topic)

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish    = on_publish
    client.on_message    = on_message

    if username:
        client.username_pw_set(username, password)

    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
        logger.info("MQTT client initialised — connecting to %s:%s", host, port)
    except Exception as exc:
        logger.error("Initial MQTT connect failed (%s) — retrying in background", exc)
        client.loop_start()
        threading.Thread(target=_reconnect_loop, args=(client, host, port), daemon=True).start()

    return client


def _reconnect_loop(client: mqtt.Client, host: str, port: int) -> None:
    """Exponential back-off reconnect; runs in a daemon thread."""
    delay = 2
    while True:
        time.sleep(delay)
        try:
            client.reconnect()
            logger.info("MQTT reconnected to %s:%s", host, port)
            return
        except Exception as exc:
            logger.warning("MQTT reconnect failed (%s) — retry in %ss", exc, delay)
            delay = min(delay * 2, 60)


def _topic_matches(pattern: str, topic: str) -> bool:
    p_parts = pattern.split("/")
    t_parts = topic.split("/")
    if "#" in p_parts:
        idx = p_parts.index("#")
        return all(p == "+" or p == t for p, t in zip(p_parts[:idx], t_parts[:idx]))
    if len(p_parts) != len(t_parts):
        return False
    return all(p == "+" or p == t for p, t in zip(p_parts, t_parts))