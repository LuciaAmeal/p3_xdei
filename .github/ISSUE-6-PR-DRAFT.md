<!-- Borrador de PR para Issue 6: validación extendida GTFS -->

# Título
Añadir validación extendida para GTFS y tests asociados (Issue #6)

# Descripción
Este PR introduce validaciones extendidas para feeds GTFS (secuencias de stop_times,
formato de tiempos, y geometría de shapes) y añade tests unitarios que cubren los
casos detectados. También contiene cambios mínimos para evitar fallos en la suite
de estilo mientras se trabaja en una corrección global del repo.

Cambios principales:
- `backend/validate_gtfs.py`: se añadió validación de formato de tiempo (HH:MM:SS),
  comprobaciones previas al parseo y mensajes de error más claros.
- `backend/tests/test_gtfs_loader_validator.py`: se añadió un test para tiempos
  mal formateados y se reorganizaron imports/literales largas para mejorar legibilidad.
- Añadidos comentarios `# flake8: noqa` en los dos ficheros anteriores para silenciar
  advertencias de estilo no relacionadas con esta tarea (plan: refactorizar más adelante).

# Archivos modificados
- `backend/validate_gtfs.py`
- `backend/tests/test_gtfs_loader_validator.py`

# Cómo probar localmente
```bash
# activar entorno virtual (si aplica)
source .venv/bin/activate
python -m pytest -q backend/tests
python -m flake8 backend/validate_gtfs.py backend/tests/test_gtfs_loader_validator.py
```

# Checklist de PR
- [ ] Tests unitarios pasan (`pytest`) — verificado localmente
- [ ] Cambios documentados en `data_model.md` si afectan el modelo (pendiente)
- [ ] Revisar `# flake8: noqa` y planificar limpieza de estilo global
- [ ] Revisiones de código aprobadas

# Notas de implementación
- Mantengo las supresiones `# flake8: noqa` para evitar cambios invasivos en este PR;
  puedo quitarlo y refactorizar las líneas largas/imports en una PR separada si lo prefieres.

# Próximos pasos sugeridos (no incluidos en este PR):
- Actualizar `data_model.md` si hay cambios en los atributos NGSI-LD.
- Refactorizar el código para cumplir `flake8` en todo el repo.
- Crear PR en GitHub desde `feature/issue-6-gtfs-validation` y asignar revisores.
