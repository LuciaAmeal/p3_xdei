#!/bin/bash
set -e

# Colores para la salida
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Preparando el entorno de movilidad urbana...${NC}"

# Comprobar si hay conflictos de puertos
check_port() {
  local port=$1
  if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${RED}⚠️  Error: El puerto $port ya está en uso por otro proceso.${NC}"
    echo -e "${RED}Por favor, detén cualquier otro contenedor o servicio que use este puerto.${NC}"
    return 1
  fi
  return 0
}

echo "Comprobando puertos..."
check_port 1026 || exit 1
check_port 8000 || exit 1
check_port 4200 || exit 1

# Asegurar un estado limpio
echo -e "${BLUE}🧹 Limpiando contenedores anteriores...${NC}"
docker compose down

# Levantar los contenedores
echo -e "${BLUE}🏗️  Levantando contenedores...${NC}"
docker compose up --build -d

echo -e "${BLUE}⏳ Esperando a que los servicios estén listos...${NC}"

# Función para esperar a un servicio con timeout
wait_for_service() {
  local url=$1
  local name=$2
  local timeout=60
  local count=0
  echo -n "Esperando a $name..."
  until curl --output /dev/null --silent --fail "$url" || [ $count -eq $timeout ]; do
    echo -n "."
    sleep 2
    count=$((count + 1))
  done

  if [ $count -eq $timeout ]; then
    echo -e " ${RED}❌ Error: Timeout esperando a $name${NC}"
    docker compose logs backend | tail -n 20
    exit 1
  fi
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
