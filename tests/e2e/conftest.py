import os
import subprocess
import time
import socket
import requests
import pytest


def repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def wait_for_port(host: str, port: int, timeout: int = 120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except Exception:
            time.sleep(1)
    return False


@pytest.fixture(scope="session")
def start_compose():
    root = repo_root()
    # Start compose
    subprocess.run(['docker-compose', 'up', '-d'], cwd=root, check=True)

    # Run start.sh if present (wait helpers)
    start_sh = os.path.join(root, 'start.sh')
    if os.path.exists(start_sh):
        subprocess.run(['bash', start_sh], cwd=root, check=False)

    # Wait for core services
    host = os.environ.get('FIWARE_HOST', 'localhost')
    # common FIWARE ports
    ready = wait_for_port(host, int(os.environ.get('ORION_PORT', 1026)), timeout=120)
    ready = ready and wait_for_port(host, int(os.environ.get('QUANTUMLEAP_PORT', 8668)), timeout=120)
    ready = ready and wait_for_port(host, int(os.environ.get('MOSQUITTO_PORT', 1883)), timeout=120)

    if not ready:
        pytest.skip('Required services did not become available in time')

    yield

    if os.environ.get('SKIP_E2E_TEARDOWN') != '1':
        subprocess.run(['docker-compose', 'down', '-v'], cwd=root)


@pytest.fixture
def orion_url():
    host = os.environ.get('FIWARE_HOST', 'localhost')
    port = os.environ.get('ORION_PORT', '1026')
    return f'http://{host}:{port}'


@pytest.fixture
def clean_orion(orion_url):
    # Remove all entities created during tests to keep runs idempotent
    def _clean():
        try:
            res = requests.get(f"{orion_url}/ngsi-ld/v1/entities?limit=1000")
            if res.status_code == 200:
                entities = res.json()
                for ent in entities:
                    eid = ent.get('id')
                    if eid:
                        requests.delete(f"{orion_url}/ngsi-ld/v1/entities/{eid}")
        except Exception:
            pass

    _clean()
    yield _clean
    _clean()


def _mosquitto_pub_available():
    try:
        subprocess.run(['mosquitto_pub', '--help'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


@pytest.fixture
def mqtt_publish():
    """Return a helper callable publish(topic, payload, host=...)"""

    def publish(topic, payload, host=None, port=1883, qos=0):
        host = host or os.environ.get('FIWARE_HOST', 'localhost')
        try:
            import paho.mqtt.publish as publish_mod

            publish_mod.single(topic, payload, hostname=host, port=int(port), qos=int(qos))
            return True
        except Exception:
            if _mosquitto_pub_available():
                cmd = ['mosquitto_pub', '-h', host, '-p', str(port), '-t', topic, '-m', str(payload)]
                subprocess.run(cmd, check=True)
                return True
        return False

    return publish
