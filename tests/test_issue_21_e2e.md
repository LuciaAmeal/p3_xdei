# Issue 21 E2E Checklist - Vehículos 3D animados coloreados por ruta

## Setup

- Abrir la interfaz 3D en un navegador con soporte WebGL.
- Confirmar que el backend está disponible para `api-client.js`.

## Visual Checks

- [ ] La escena 3D carga sin errores visibles.
- [ ] Los vehículos aparecen como meshes 3D y no como marcadores planos.
- [ ] Cada vehículo usa el color de su ruta cuando existe `routeColor`.
- [ ] Los vehículos sin color válido usan un fallback consistente.

## Animation Checks

- [ ] La posición de cada vehículo cambia de forma interpolada entre updates.
- [ ] No hay saltos bruscos al recibir un nuevo poll salvo en casos de teletransporte.
- [ ] El heading del vehículo modifica su orientación en pantalla.
- [ ] La orientación no hace giros erráticos al cruzar 0/360 grados.

## Data Flow Checks

- [ ] `api-client.js` carga rutas antes de la escena 3D.
- [ ] Los vehículos actuales llegan desde `/api/vehicles/current`.
- [ ] La escena sigue funcionando si un vehículo no tiene `heading`.
- [ ] La escena sigue funcionando si un vehículo no tiene `currentPosition`.

## Resilience Checks

- [ ] Si falla una actualización de polling, la escena mantiene el estado previo.
- [ ] Al recargar la página, no quedan duplicados de meshes ni timers.
- [ ] El `cleanup()` detiene polling, observers y animation frames.

## Acceptance Criteria

- [ ] Los vehículos se ven coloreados por ruta.
- [ ] La interpolación entre updates es perceptible y suave.
- [ ] La rotación por heading es correcta.
- [ ] No se producen errores de consola relacionados con la escena 3D.