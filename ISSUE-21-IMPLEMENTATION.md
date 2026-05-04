# Issue 21: Vehículos 3D animados coloreados por ruta

## Overview

Implementación del render 3D de vehículos como meshes coloreados por `routeColor`, con interpolación entre updates y rotación por `heading`. El cambio se ha concentrado en el frontend 3D para reutilizar el contrato existente de rutas y vehículos.

## Cambios Implementados

### Phase 1: Contrato de datos
- Se reutiliza `frontend/static/js/api-client.js` para cargar rutas y vehículos.
- El color se resuelve en frontend desde `tripId -> route -> routeColor`.
- Se aprovecha `heading` de `/api/vehicles/current` sin cambios de backend.

### Phase 2: Escena 3D
- `frontend/index.html` carga `api-client.js` antes de `scene3d.js`.
- `frontend/static/js/scene3d.js` ahora crea meshes 3D por vehículo.
- Cada mesh se colorea con el color de su ruta o con un fallback determinista.

### Phase 3: Animación
- La posición de cada vehículo se interpola entre muestras recibidas por polling.
- La orientación se suaviza a partir de `heading`.
- El polling se limpia en `cleanup()` para evitar duplicaciones y fugas.

### Phase 4: Validación
- Se validó sintaxis de `scene3d.js` e `index.html` con el verificador de errores.

## Archivos Modificados

| Archivo | Cambios | Descripción |
|---|---|---|
| `frontend/index.html` | Carga `api-client.js` antes de la escena 3D | Permite que `scene3d.js` consuma `window.MapApiClient` |
| `frontend/static/js/scene3d.js` | Nueva lógica de vehículos 3D animados | Meshes, color por ruta, interpolación y heading |

## Validaciones & Edge Cases

- Sin `routeColor`, se usa un color fallback estable.
- Sin `heading`, el vehículo conserva una orientación válida.
- Si falta posición, el vehículo se omite sin romper la escena.
- Si el polling falla, la escena mantiene el estado actual y registra el error.

## Commits en Orden

- Pendiente de commit.

## Checklist de Validación

- [x] Sintaxis correcta en `frontend/static/js/scene3d.js`
- [x] Sintaxis correcta en `frontend/index.html`
- [ ] Render 3D verificado en navegador
- [ ] Meshes coloreados por ruta confirmados
- [ ] Interpolación entre updates confirmada
- [ ] Rotación por heading confirmada

## Conclusión

La base funcional del issue ya está implementada en el frontend 3D. Queda pendiente la validación visual y el cierre GitHub Flow completo con commit, push y PR.