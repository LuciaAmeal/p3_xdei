# Checklist de aceptación — Validación E2E

Objetivo: Validar que el stack se levanta correctamente, las funcionalidades MVP funcionan (ingestión MQTT → IoT Agent → Orion → QuantumLeap; endpoints Flask; sincronía frontend) y criterios de performance y reproducibilidad se cumplen.

Requisitos mínimos automáticos
- Docker Compose levanta todos los servicios (`docker-compose up -d`) y `start.sh` confirma disponibilidad.
- Tests E2E automatizados en `tests/e2e/` pasan sin fallos.
- Los tests limpian la base de datos (Orion) entre ejecuciones.

Flujos funcionales a validar
- Publicar telemetry MQTT y comprobar entidad `Vehicle` creada en Orion.
- Consultar series en QuantumLeap para la entidad creada.
- Llamadas a endpoints Flask claves devuelven estado esperado.
- Frontend refleja cambios (API-driven checks).

Performance (umbrales)
- Endpoints API: 95p de respuestas < 500ms.
- Ingestión MQTT → disponibilidad en Orion: mediana < 2s (aceptable hasta 5s en CI lento).

Reproducibilidad
- Tests usan seeds fijos cuando es necesario (`RANDOM_SEED` env var).
- `scripts/e2e_seed.py` produce datos idempotentes.

Manual / checklist visual
- Frontend 2D/3D: elementos visibles, interpolaciones coherentes (ver [tests/test_issue_21_e2e.md](tests/test_issue_21_e2e.md)).
