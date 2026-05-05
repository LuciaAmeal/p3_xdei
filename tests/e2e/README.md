E2E tests
=========

Requisitos previos
- `docker-compose` disponible localmente
- Permisos para crear/levantar contenedores

Ejecutar localmente

1. Levantar el stack (usando el script de helper):

```bash
bash scripts/e2e_setup.sh
```

2. Ejecutar tests E2E (marcador `e2e`):

```bash
pytest tests/e2e -m e2e -q
```

3. Bajar el stack:

```bash
bash scripts/e2e_teardown.sh
```

Notas
- Usa la variable `FIWARE_HOST` si los servicios están en otra IP.
- Para evitar teardown automático además exporta `SKIP_E2E_TEARDOWN=1`.
