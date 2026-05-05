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

Grafana se arranca con un datasource de CrateDB ya provisionado, usando el driver PostgreSQL contra `crate:5432` dentro de la red de Docker Compose.

## Dashboards de Grafana (Issue #29)

Tres dashboards operativos se provisionan automáticamente al arrancar Grafana. Estos dashboards consultan directamente la tabla `doc.vehiclestate` en CrateDB, que es poblada por QuantumLeap a partir de cambios en las entidades `VehicleState` de Orion-LD.

**Auto-refresh**: 30 segundos | **Rango temporal por defecto**: últimas 2 horas

### 1. Delays Dashboard
- URL: `http://localhost:3000/d/delays`
- **Serie temporal de retraso promedio**: Retraso medio cada minuto
- **Ranking de máximos por vehículo**: Top 20 vehículos con mayor retraso
- Caso de uso: Detectar líneas o vehículos con degradación operativa

### 2. Occupancy Dashboard
- URL: `http://localhost:3000/d/occupancy`
- **Serie temporal de ocupación**: Ocupación media cada 5 minutos
- **Tabla por vehículo**: Ocupación máxima y promedio (Top 20)
- Caso de uso: Identificar paradas o vehículos con saturación

### 3. Volume Dashboard
- URL: `http://localhost:3000/d/volume`
- **Volumen de viajes por hora**: Número de viajes activos por franja horaria
- **Volumen por vehículo**: Distribución de registros (Top 20)
- Caso de uso: Análisis de demanda y distribución de carga

**Nota**: Para que los paneles muestren datos, es necesario que el simulador esté corriendo y publicando telemetría:
```bash
python backend/dynamic_simulator.py --gtfs-zip <archivo.zip>
```

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
>>>>>>> c9a1d1b (feat: provision Grafana dashboards for delays, occupancy, and volume)

Nota de modelado de datos:
Las entidades NGSI-LD deben alinearse con los esquemas estándar de `dataModel.UrbanMobility` de FIWARE (PublicTransportStop, PublicTransportRoute, Vehicle, etc.). Consultar `data_model.md`.

## Autenticación para Desarrollo

### Descripción

El backend implementa autenticación JWT mock para desarrollo. Esto permite simular usuarios autenticados sin necesidad de un servidor OAuth2 o sistema de autenticación real.

**Importante**: Esta es **solo para desarrollo**. No usar en producción sin implementar autenticación real.

### Características

- **Tokens JWT** con firma HMAC-SHA256
- **Expiración**: 24 horas
- **Credenciales mock**: Acepta cualquier username/password no-vacíos
- **Backward compatible**: Sigue soportando header `X-User-Id` para tests

### Login

#### Endpoint: POST `/api/login`

**Request**:
```bash
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test_user",
    "password": "test_password"
  }'
```

**Response** (200 OK):
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "test_user",
  "expires_in_hours": 24
}
```

### Uso del Token

El token JWT se almacena automáticamente en `localStorage` del navegador bajo la clave `xdei.auth.token`.

Para usar el token en requests subsecuentes, incluir el header `Authorization: Bearer <token>`:

```bash
curl -X GET http://localhost:8000/api/user/test_user/profile \
  -H "Authorization: Bearer <token>"
```

### Frontend

1. **Login**: Formulario de login se muestra automáticamente si no hay token
2. **Almacenamiento**: Token se guarda en `localStorage` automáticamente
3. **Inyección automática**: El API client inyecta el Bearer token en todos los requests
4. **Logout**: Botón "Cerrar sesión" limpia el token y vuelve a mostrar el login

### Puntos de Integración

- **Backend**: `backend/auth.py` - Utilidades JWT
- **Backend**: `backend/app.py` - Endpoint `/api/login` y validación en `_authenticated_user_id()`
- **Frontend**: `frontend/static/js/auth-manager.js` - Gestión de token
- **Frontend**: `frontend/static/js/api-client.js` - Inyección de Bearer token
- **Frontend**: `frontend/static/js/login-ui.js` - Interfaz de login
- **Frontend**: `frontend/static/js/gamification-manager.js` - Integración con flujo de autenticación

### Testing

Ejecutar tests de autenticación:

```bash
# Tests de utilidades JWT
pytest backend/tests/test_jwt_auth.py -v

# Tests del endpoint de login
pytest backend/tests/test_login_endpoint.py -v

# Tests de endpoints protegidos con JWT
pytest backend/tests/test_gamification_api.py::TestJWTAuth -v

# Todos los tests
pytest backend/tests/ -v
```

### Variables de Entorno

- `JWT_SECRET_KEY` (default: `dev-secret-key`) - Clave secreta para firmar tokens
- `JWT_EXPIRATION_HOURS` (default: `24`) - Horas de validez del token
