import os
import subprocess
import json


def publish_via_cli(topic: str, payload, host: str = None, port: int = 1883):
    host = host or os.environ.get('FIWARE_HOST', 'localhost')
    cmd = ['mosquitto_pub', '-h', host, '-p', str(port), '-t', topic, '-m', json.dumps(payload)]
    subprocess.run(cmd, check=True)


def try_publish(topic: str, payload, host: str = None, port: int = 1883):
    """Try to publish using paho, fallback to mosquitto_pub CLI."""
    try:
        import paho.mqtt.publish as publish

        host = host or os.environ.get('FIWARE_HOST', 'localhost')
        publish.single(topic, json.dumps(payload), hostname=host, port=int(port))
        return True
    except Exception:
        try:
            publish_via_cli(topic, payload, host=host, port=port)
            return True
        except Exception:
            return False
