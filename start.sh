#!/usr/bin/env bash
set -euo pipefail

echo "Starting Docker Compose stack..."
docker compose up -d --build

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


# Wait for the locally published ports exposed by Docker Compose.
wait_for localhost 1883 Mosquitto 30

# MongoDB is required by Orion-LD during startup.
wait_for localhost 27017 MongoDB 30

wait_for localhost 1026 Orion-LD 60
wait_for localhost 4041 "IoT Agent JSON" 60
wait_for localhost 4200 CrateDB 60
wait_for localhost 8668 QuantumLeap 60
wait_for localhost 3000 Grafana 60
wait_for localhost 8000 Backend 60
wait_for localhost 8081 Frontend 60

echo "All critical services responded; the stack is ready."

if [[ $# -gt 0 ]]; then
  exec "$@"
fi
