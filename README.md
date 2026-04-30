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
- Backend Flask: `8000` (`/health`, `/api/ping`)
- Frontend: `8081`

## Estructura del Backend

El backend Flask está estructurado en módulos especializados para mantener separación de responsabilidades:

### Directorios principales

```
backend/
├── app.py                    # Aplicación Flask principal
├── config.py                 # Configuración centralizada (lee .env)
├── requirements.txt          # Dependencias Python
├── clients/                  # Clientes HTTP y MQTT para servicios FIWARE
│   ├── __init__.py
│   ├── orion.py             # Cliente Orion-LD (NGSI-LD entities)
│   ├── quantumleap.py       # Cliente QuantumLeap (series temporales)
│   └── mqtt.py              # Cliente MQTT (Mosquitto broker)
├── utils/                    # Utilidades transversales
│   ├── __init__.py
│   └── logger.py            # Logging estructurado
└── tests/                    # Tests unitarios
    ├── __init__.py
    ├── test_orion_client.py
    ├── test_quantumleap_client.py
    ├── test_mqtt_client.py
    └── test_health.py
```

### Configuración

Las variables de entorno se cargan desde `.env` (crear desde `.env.example`):

```bash
cp .env.example .env
# Editar .env según tu entorno (localmente usa defaults)
```

Variables principales:
- **Orion-LD**: `ORION_HOST`, `ORION_PORT`, `ORION_TIMEOUT`, `ORION_RETRIES`
- **QuantumLeap**: `QUANTUMLEAP_HOST`, `QUANTUMLEAP_PORT`, `QUANTUMLEAP_TIMEOUT`
- **MQTT**: `MQTT_HOST`, `MQTT_PORT`, `MQTT_TIMEOUT`, `MQTT_KEEPALIVE`
- **FIWARE**: `FIWARE_SERVICE`, `FIWARE_SERVICEPATH`
- **App**: `LOG_LEVEL`, `FLASK_ENV`, `FLASK_HOST`, `FLASK_PORT`

### Clientes disponibles

#### OrionClient (`clients/orion.py`)

Cliente HTTP para Orion-LD con reintentos automáticos y retry logic:

```python
from clients.orion import OrionClient
from config import settings

orion = OrionClient(
    base_url=settings.orion.url,
    timeout=settings.orion.timeout,
    retries=settings.orion.retries,
    fiware_headers=settings.get_fiware_headers(),
)

# Obtener entidades
entities = orion.get_entities(entity_type="GtfsRoute", limit=10)

# Crear entidad
entity_id = orion.create_entity({
    "id": "urn:ngsi-ld:GtfsRoute:route_1",
    "type": "GtfsRoute",
    "routeShortName": {"type": "Property", "value": "L1"},
    "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"]
})

# Batch upsert
stats = orion.batch_upsert(entities_list, batch_size=100)
```

#### QuantumLeapClient (`clients/quantumleap.py`)

Cliente para consultar series temporales históricas:

```python
from clients.quantumleap import QuantumLeapClient
from config import settings

ql = QuantumLeapClient(
    base_url=settings.quantumleap.url,
    timeout=settings.quantumleap.timeout,
    retries=settings.quantumleap.retries,
)

# Consultar series temporales con filtro temporal
ts_data = ql.get_time_series(
    entity_id="urn:ngsi-ld:VehicleState:bus_1",
    attrs=["currentPosition", "speed"],
    from_date="2024-01-01T00:00:00Z",
    to_date="2024-01-01T01:00:00Z",
)

# Listar entidades con histórico
entities = ql.get_available_entities()
```

#### MQTTClient (`clients/mqtt.py`)

Cliente para publicar en Mosquitto (estructura base para expansión futura):

```python
from clients.mqtt import MQTTClient
from config import settings

mqtt = MQTTClient(
    host=settings.mqtt.host,
    port=settings.mqtt.port,
    timeout=settings.mqtt.timeout,
    keepalive=settings.mqtt.keepalive,
)

mqtt.connect()

# Publicar mensaje
mqtt.publish("vehicle/bus_1/telemetry", {
    "position": [43.3623, -8.4115],
    "speed": 15.5,
    "delay_seconds": 45,
})

mqtt.disconnect()
```

### Endpoints actuales

- **`GET /health`** — Estado de salud de servicios FIWARE (respuesta JSON con status por servicio)
- **`GET /api/ping`** — Simple echo para verificar conectividad

### Testing

Ejecutar tests unitarios:

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v

# O con coverage:
pytest tests/ --cov=clients --cov=utils -v
```

Los tests usan `pytest` y `pytest-mock` para mockear conexiones HTTP y MQTT.

---

Nota de modelado de datos:
Las entidades NGSI-LD deben alinearse con los esquemas estándar de `dataModel.UrbanMobility` de FIWARE (PublicTransportStop, PublicTransportRoute, Vehicle, etc.). Consultar `data_model.md`.
