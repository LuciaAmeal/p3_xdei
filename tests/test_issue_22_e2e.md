# E2E Test: Issue 22 - VehicleManager compartido 2D ↔ 3D

## Setup

- [ ] Abrir la aplicación con la vista 2D y la escena 3D disponibles.
- [ ] Verificar que `api-client.js` y `vehicle-manager.js` cargan sin errores.

## Sync Checks

- [ ] Un único polling alimenta el estado de vehículos para ambas vistas.
- [ ] Un update de vehículo se refleja en el mapa 2D y en la escena 3D.
- [ ] Ambas vistas muestran el mismo `vehicleId` y la misma posición base.
- [ ] No aparecen duplicados tras varias actualizaciones consecutivas.

## Fallback / Resilience

- [ ] Si falla una petición de vehículos, la vista conserva el estado previo.
- [ ] Si el manager no está disponible, la 3D sigue mostrando el bootstrap inicial.
- [ ] La aplicación sigue funcionando con `sampleData()`.

## Cleanup

- [ ] Al cerrar o recargar la página, se detienen suscripciones y polling.
- [ ] No quedan marcadores, meshes ni listeners huérfanos.

## Acceptance Criteria

- [ ] El estado de vehículos está centralizado en `VehicleManager`.
- [ ] `map.js` y `scene3d.js` consumen la misma fuente de datos.
- [ ] No hay errores de consola relacionados con sincronización 2D/3D.
