#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "Starting docker-compose stack for E2E..."
docker-compose up -d

if [ -f ./start.sh ]; then
  echo "Running start.sh to wait for services..."
  bash ./start.sh || true
fi

echo "If you need to seed data, run: python3 scripts/e2e_seed.py"
