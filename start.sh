#!/usr/bin/env bash
set -e

echo "Waiting for core services to become available..."

wait_for() {
  host=$1
  port=$2
  name=$3
  timeout=${4:-60}
  echo -n "- Waiting for $name at $host:$port... "
  for i in $(seq 1 $timeout); do
    if nc -z "$host" "$port" >/dev/null 2>&1; then
      echo "OK"
      return 0
    fi
    sleep 1
  done
  echo "TIMEOUT"
  return 1
}

# Wait for Mosquitto (MQTT)
wait_for mosquitto 1883 Mosquitto 30

# Wait for Orion-LD
wait_for orion-ld 1026 Orion-LD 60

# Wait for CrateDB
wait_for crate 4200 CrateDB 60

echo "All critical services responded; you can now run 'docker compose up' or start simulators." 

exec "$@"
