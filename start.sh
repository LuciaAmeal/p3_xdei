#!/bin/bash
set -e

# Colores para la salida
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Iniciando el stack de movilidad urbana...${NC}"

# Levantar los contenedores
docker compose up --build -d

echo -e "${BLUE}⏳ Esperando a que los servicios estén listos...${NC}"

# Función para esperar a un servicio
wait_for_service() {
  local url=$1
  local name=$2
  echo -n "Esperando a $name..."
  until $(curl --output /dev/null --silent --fail "$url"); do
    echo -n "."
    sleep 2
  done
  echo -e " ${GREEN}¡Listo!${NC}"
}

# Esperar a los servicios clave
wait_for_service "http://localhost:4200/" "CrateDB"
wait_for_service "http://localhost:1026/version" "Orion-LD"
wait_for_service "http://localhost:8000/health" "Backend"

# Pequeña espera adicional para asegurar que CrateDB acepta conexiones SQL
sleep 5

echo -e "${BLUE}🌱 Sembrando datos históricos en CrateDB...${NC}"
docker compose exec backend python seed_historical_data.py

echo -e "${BLUE}🚍 Cargando datos estáticos GTFS...${NC}"
curl -X POST http://localhost:8000/api/gtfs/load

echo -e "${BLUE}🎮 Sembrando datos de gamificación...${NC}"
docker compose exec backend python seed_gamification.py

echo -e "${GREEN}✅ ¡Sistema inicializado correctamente!${NC}"
echo -e "Mapa 2D/3D: http://localhost:8081"
echo -e "Grafana: http://localhost:3000 (Dashboards listos)"
echo -e "Backend API: http://localhost:8000"
