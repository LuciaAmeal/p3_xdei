# XDEI P3 — Quick start

Este repositorio contiene la orquestación mínima para levantar una pila FIWARE local para desarrollo.

Requisitos:
- Docker y Docker Compose instalados.

Arranque rápido:

```bash
# (opcional) preparar y esperar servicios críticos
./start.sh

# Levantar toda la pila (en segundo plano opcionalmente)
docker compose up --build
```

Servicios expuestos (puertos locales):
- Mosquitto MQTT: `1883`
- Orion-LD: `1026`
- IoT Agent JSON: `4041`
- CrateDB: `4200`
- QuantumLeap: `8668`
- Grafana: `3000`
- Backend (stub): `8000` (`/health`)
- Frontend (stub): `8080`

Nota de modelado de datos:
Las entidades NGSI-LD deben alinearse con los esquemas estándar de `dataModel.UrbanMobility` de FIWARE (PublicTransportStop, PublicTransportRoute, Vehicle, etc.). Consultar `data_model.md`.
