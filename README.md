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
