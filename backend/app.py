"""
XDEI Backend - Flask Application

Main application entry point with health check and service status endpoints.
"""

import time
from datetime import datetime, timezone

from flask import Flask, jsonify
from clients.orion import OrionClient, OrionClientConflict, OrionClientError
from clients.quantumleap import QuantumLeapClient
from clients.mqtt import MQTTClient
from config import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize FIWARE clients with configuration
orion_client = OrionClient(
    base_url=settings.orion.url,
    timeout=settings.orion.timeout,
    retries=settings.orion.retries,
    fiware_headers=settings.get_fiware_headers(),
)

ql_client = QuantumLeapClient(
    base_url=settings.quantumleap.url,
    timeout=settings.quantumleap.timeout,
    retries=settings.quantumleap.retries,
    fiware_headers=settings.get_fiware_headers(),
)

mqtt_client = MQTTClient(
    host=settings.mqtt.host,
    port=settings.mqtt.port,
    timeout=settings.mqtt.timeout,
    keepalive=settings.mqtt.keepalive,
)

VEHICLE_STATE_HISTORY_SUBSCRIPTION_ID = "urn:ngsi-ld:Subscription:vehicle-state-history"
VEHICLE_STATE_HISTORY_WATCHED_ATTRS = [
    "currentPosition",
    "delaySeconds",
    "occupancy",
    "speedKmh",
    "heading",
    "status",
    "trip",
]


def build_vehicle_state_history_subscription() -> dict:
    """Build the NGSI-LD subscription used to persist VehicleState changes."""
    return {
        "id": VEHICLE_STATE_HISTORY_SUBSCRIPTION_ID,
        "type": "Subscription",
        "description": "Persist VehicleState changes in QuantumLeap",
        "entities": [
            {
                "type": "VehicleState",
            }
        ],
        "watchedAttributes": VEHICLE_STATE_HISTORY_WATCHED_ATTRS,
        "notification": {
            "attributes": VEHICLE_STATE_HISTORY_WATCHED_ATTRS,
            "endpoint": {
                "uri": f"{settings.quantumleap.url.rstrip('/')}/v2/notify",
                "accept": "application/ld+json",
            },
        },
    }


def ensure_vehicle_state_history_subscription(max_attempts: int = 30, retry_delay_seconds: int = 2) -> bool:
    """Ensure the historical subscription exists before the backend starts serving traffic."""
    subscription = build_vehicle_state_history_subscription()

    for attempt in range(1, max_attempts + 1):
        try:
            existing_subscriptions = orion_client.get_subscriptions()
            if any(item.get("id") == subscription["id"] for item in existing_subscriptions):
                logger.info("VehicleState historical subscription already exists")
                return False

            orion_client.create_subscription(subscription)
            logger.info("Created VehicleState historical subscription")
            return True

        except OrionClientConflict:
            logger.info("VehicleState historical subscription already exists")
            return False
        except OrionClientError as exc:
            logger.warning(
                "Attempt %s/%s to create VehicleState historical subscription failed: %s",
                attempt,
                max_attempts,
                exc,
            )
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)

    raise RuntimeError("Unable to create VehicleState historical subscription")


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint that validates FIWARE service connectivity.
    
    Returns:
        JSON response with overall status and per-service health:
        - status: 'healthy', 'degraded', or 'unhealthy'
        - services: dict with individual service status
        - timestamp: ISO8601 timestamp
    """
    services_status = {}
    overall_status = 'healthy'
    
    # Check Orion-LD
    try:
        if orion_client.health_check():
            services_status['orion-ld'] = {
                'status': 'ok',
                'url': settings.orion.url,
            }
        else:
            services_status['orion-ld'] = {
                'status': 'error',
                'url': settings.orion.url,
            }
            overall_status = 'degraded'
    except Exception as e:
        services_status['orion-ld'] = {
            'status': 'error',
            'url': settings.orion.url,
            'error': str(e),
        }
        overall_status = 'degraded'
        logger.warning(f"Orion-LD health check failed: {e}")
    
    # Check QuantumLeap
    try:
        if ql_client.health_check():
            services_status['quantumleap'] = {
                'status': 'ok',
                'url': settings.quantumleap.url,
            }
        else:
            services_status['quantumleap'] = {
                'status': 'error',
                'url': settings.quantumleap.url,
            }
            overall_status = 'degraded'
    except Exception as e:
        services_status['quantumleap'] = {
            'status': 'error',
            'url': settings.quantumleap.url,
            'error': str(e),
        }
        overall_status = 'degraded'
        logger.warning(f"QuantumLeap health check failed: {e}")
    
    # Check MQTT
    try:
        mqtt_client.connect()
        if mqtt_client.is_connected:
            services_status['mqtt'] = {
                'status': 'ok',
                'host': settings.mqtt.host,
                'port': settings.mqtt.port,
            }
            mqtt_client.disconnect()
        else:
            services_status['mqtt'] = {
                'status': 'error',
                'host': settings.mqtt.host,
                'port': settings.mqtt.port,
            }
            overall_status = 'degraded'
    except Exception as e:
        services_status['mqtt'] = {
            'status': 'error',
            'host': settings.mqtt.host,
            'port': settings.mqtt.port,
            'error': str(e),
        }
        overall_status = 'degraded'
        logger.warning(f"MQTT health check failed: {e}")
    
    response = {
        'status': overall_status,
        'services': services_status,
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }
    
    # Return 200 for healthy/degraded, 503 for unhealthy
    http_status = 200 if overall_status in ['healthy', 'degraded'] else 503
    
    return jsonify(response), http_status


@app.route('/api/ping', methods=['GET'])
def ping():
    """
    Simple ping endpoint for basic connectivity check.
    
    Returns:
        JSON response with ping acknowledgment
    """
    return jsonify(ping='pong'), 200


if __name__ == '__main__':
    logger.info(f"Starting XDEI Backend on {settings.app.flask_host}:{settings.app.flask_port}")
    ensure_vehicle_state_history_subscription()
    app.run(
        host=settings.app.flask_host,
        port=settings.app.flask_port,
        debug=(settings.app.flask_env == 'development'),
    )
