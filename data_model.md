# Modelo de datos - FIWARE Urban Mobility con NGSI-LD

## 1. Principios de modelado

1. Las entidades estáticas de GTFS se modelan como contexto maestro.
2. Los atributos dinámicos del servicio en tiempo real se separan en entidades específicas de estado.
3. Se prioriza NGSI-LD en todas las entidades, propiedades y relaciones.
4. Se reutilizan patrones de Smart Data Models transversales cuando aportan interoperabilidad clara, especialmente en identificadores, localización, observaciones y telemetría.
5. La información histórica no se duplica en el modelo de contexto: se persiste en QuantumLeap/CrateDB a partir de cambios de estado.

## 2. Convenciones NGSI-LD

- Toda entidad debe incluir `id`, `type` y `@context`.
- Las propiedades simples se modelan como `Property`.
- Las relaciones se modelan como `Relationship`.
- Las geometrias se modelan como `GeoProperty`.
- Los valores temporales que cambian frecuentemente no deben mezclarse con los datos estáticos GTFS.
- Los identificadores deben ser estables y reproducibles a partir del feed original.

## 3. Capa GTFS estática

### 3.1 GtfsRoute

Entidad que representa una ruta o línea de transporte.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| routeShortName | Property | Estático | Código corto de la línea. |
| routeLongName | Property | Estático | Nombre descriptivo de la ruta. |
| routeDesc | Property | Estático | Descripción opcional. |
| routeType | Property | Estático | Tipo GTFS de ruta. |
| routeColor | Property | Estático | Color visual para UI. |
| routeTextColor | Property | Estático | Color de texto. |
| operatorName | Property | Estático | Operador del servicio, si existe. |
| location | GeoProperty | Estático | Geometría de referencia o caja de cobertura si se decide representarla. |

Relaciones:
- `hasTrip` → GtfsTrip
- `servesStop` → GtfsStop

### 3.2 GtfsStop

Entidad que representa una parada.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| stopName | Property | Estático | Nombre de la parada. |
| stopCode | Property | Estático | Código operativo. |
| stopDesc | Property | Estático | Descripción opcional. |
| platformCode | Property | Estático | Andén o plataforma. |
| wheelchairBoarding | Property | Estático | Accesibilidad GTFS. |
| zoneId | Property | Estático | Zona tarifaria si existe. |
| location | GeoProperty | Estático | Punto geográfico de la parada. |

Relaciones:
- `isPartOfRoute` → GtfsRoute
- `hasStopTime` → GtfsStopTime
- `hasPrediction` → StopCrowdPrediction
- `isVisitedBy` → UserProfile

### 3.3 GtfsTrip

Entidad que representa un viaje concreto dentro de una ruta.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| tripHeadsign | Property | Estático | Destino visible del viaje. |
| tripShortName | Property | Estático | Identificador corto. |
| directionId | Property | Estático | Sentido de la ruta. |
| blockId | Property | Estático | Bloque operativo si existe. |
| shapeId | Property | Estático | Referencia a la forma. |

Relaciones:
- `hasRoute` → GtfsRoute
- `hasService` → GtfsService
- `hasStopTime` → GtfsStopTime
- `hasShape` → GtfsShape
- `isTrackedBy` → VehicleState

### 3.4 GtfsStopTime

Entidad intermedia que representa el horario de paso de un viaje por una parada.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| arrivalTime | Property | Estático | Hora planificada de llegada. |
| departureTime | Property | Estático | Hora planificada de salida. |
| stopSequence | Property | Estático | Orden de paso. |
| pickupType | Property | Estático | Regla GTFS de recogida. |
| dropOffType | Property | Estático | Regla GTFS de descenso. |

Relaciones:
- `hasStop` → GtfsStop
- `hasTrip` → GtfsTrip

### 3.5 GtfsShape

Entidad que representa el trazado geográfico de una ruta o viaje.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| shapePoints | Property | Estático | Lista ordenada de coordenadas o geometría compactada. |
| location | GeoProperty | Estático | `LineString` con el trazado. |
| shapeLength | Property | Estático | Longitud calculada. |

Relaciones:
- `isShapeOf` → GtfsTrip

### 3.6 GtfsService

Entidad que agrupa la vigencia de un servicio.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| startDate | Property | Estático | Fecha inicial de vigencia. |
| endDate | Property | Estático | Fecha final de vigencia. |
| monday | Property | Estático | Opera los lunes. |
| tuesday | Property | Estático | Opera los martes. |
| wednesday | Property | Estático | Opera los miércoles. |
| thursday | Property | Estático | Opera los jueves. |
| friday | Property | Estático | Opera los viernes. |
| saturday | Property | Estático | Opera los sábados. |
| sunday | Property | Estático | Opera los domingos. |

Relaciones:
- `appliesToTrip` → GtfsTrip
- `hasExceptionDate` → GtfsCalendarDate

### 3.7 GtfsCalendarDate

Entidad opcional para excepciones de calendario.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| date | Property | Estático | Fecha concreta. |
| exceptionType | Property | Estático | Añadido o eliminado del servicio. |

Relaciones:
- `belongsToService` → GtfsService

## 4. Capa dinámica de movilidad

### 4.1 VehicleState

Entidad dinámica principal. Representa el estado operativo de un vehículo activo en tiempo real.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Origen |
|----------|--------------|-------------------|--------|
| currentPosition | GeoProperty | Dinámico | Simulador / IoT Agent |
| delaySeconds | Property | Dinámico | Simulador / IoT Agent |
| occupancy | Property | Dinámico | Simulador / IoT Agent |
| speedKmh | Property | Dinámico | Simulador / IoT Agent |
| heading | Property | Dinámico | Simulador / IoT Agent |
| nextStopName | Property | Dinámico | Simulador / backend |
| predictedArrivalTime | Property | Dinámico | Backend / cálculo auxiliar |
| status | Property | Dinámico | Simulador / backend |

Relaciones:
- `trip` → GtfsTrip
- `currentStop` → GtfsStop

Observación:
- Esta entidad es la principal candidata a persistencia histórica en QuantumLeap.

### 4.2 StopCrowdPrediction

Entidad opcional para almacenar o publicar predicciones de afluencia.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| predictedOccupancy | Property | Dinámico | Ocupación estimada. |
| confidence | Property | Dinámico | Nivel de confianza del modelo. |
| validFrom | Property | Dinámico | Inicio de vigencia de la predicción. |
| validTo | Property | Dinámico | Fin de vigencia. |
| modelVersion | Property | Dinámico | Versión del modelo usado. |

Relaciones:
- `hasStop` → GtfsStop
- `hasTrip` → GtfsTrip

## 5. Capa de gamificación

### 5.1 UserProfile

Entidad que representa el progreso de un usuario autenticado.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| displayName | Property | Estático/Dinámico | Nombre visible del usuario. |
| totalPoints | Property | Dinámico | Puntos acumulados. |
| visitedStops | Property | Dinámico | Lista o contador de paradas visitadas. |
| achievements | Property | Dinámico | Logros desbloqueados. |
| lastActivityAt | Property | Dinámico | Última actividad registrada. |
| redeemedDiscounts | Property | Dinámico | Historial resumido de canjes. |

Relaciones:
- `visitedStop` → GtfsStop
- `redeemed` → RedeemedDiscount

### 5.2 RedeemedDiscount

Entidad que registra un canje de puntos por un descuento virtual.

| Atributo | Tipo NGSI-LD | Estático/Dinámico | Descripción |
|----------|--------------|-------------------|-------------|
| discountCode | Property | Dinámico | Código del descuento. |
| discountValue | Property | Dinámico | Valor del descuento. |
| redeemedAt | Property | Dinámico | Fecha de canje. |
| validUntil | Property | Dinámico | Fecha de caducidad. |
| status | Property | Dinámico | Estado del canje. |

Relaciones:
- `belongsToUser` → UserProfile

## 6. Capa de observabilidad y sensórica transversal

Cuando haya necesidad de representar telemetría o fuentes de observación de forma transversal, se recomienda reutilizar patrones de Smart Data Models de sensórica:

- `Device` para representar una fuente de datos o dispositivo lógico si se decide exponer la procedencia de la telemetría.
- `Sensor` para describir el origen del dato cuando el simulador o una futura fuente real se modele explícitamente.
- `ObservedProperty` o estructuras equivalentes para datos medidos repetidos.
- `Measurement` o entidad equivalente para series de observación si en el futuro se quiere desacoplar la observación del estado agregado.

En esta primera versión, estas piezas pueden mantenerse como documentación de extensión, porque el sistema ya modela el estado útil en `VehicleState` y la persistencia temporal se delega a QuantumLeap.

## 7. Atributos estáticos y dinámicos

### 7.1 Estáticos

Se consideran estáticos los datos que proceden del GTFS y no deberían cambiar en tiempo real:

- rutas, nombres, colores y tipos de servicio;
- paradas y su localización;
- viajes, shapes y calendarios;
- horarios de paso planificados.

### 7.2 Dinámicos

Se consideran dinámicos los datos generados por simulación o por actualización operativa:

- posición del vehículo;
- retraso;
- ocupación;
- velocidad;
- heading;
- estado de servicio;
- predicción de ocupación;
- progreso del usuario;
- canjes de descuento.

## 8. Ejemplos de modelo NGSI-LD

### 8.1 VehicleState

```json
{
  "id": "urn:ngsi-ld:VehicleState:bus-12-trip-2026-04-28T09:15:00Z",
  "type": "VehicleState",
  "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
  "currentPosition": {
    "type": "GeoProperty",
    "value": {
      "type": "Point",
      "coordinates": [-8.403, 43.362]
    }
  },
  "delaySeconds": { "type": "Property", "value": 120 },
  "occupancy": { "type": "Property", "value": 68 },
  "speedKmh": { "type": "Property", "value": 24.5 },
  "trip": {
    "type": "Relationship",
    "object": "urn:ngsi-ld:GtfsTrip:route-4-trip-20260428-0915"
  }
}
```

### 8.2 GtfsStop

```json
{
  "id": "urn:ngsi-ld:GtfsStop:stop-0134",
  "type": "GtfsStop",
  "@context": ["https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"],
  "stopName": { "type": "Property", "value": "Praza de Ourense" },
  "location": {
    "type": "GeoProperty",
    "value": {
      "type": "Point",
      "coordinates": [-8.404, 43.371]
    }
  }
}
```

## 9. Reglas de persistencia histórica

1. Orion-LD mantiene el estado actual.
2. QuantumLeap escucha cambios sobre `VehicleState` y entidades de predicción si se desea histórico analítico.
3. CrateDB almacena las series temporales.
4. El modelo de contexto no debe duplicar el histórico por atributo salvo necesidad analítica clara.

## 10. Reglas de evolución del modelo

- Los atributos de GTFS solo se actualizan cuando cambie el feed de origen.
- La entidad `VehicleState` puede crearse y eliminarse según viajes activos.
- Las entidades de gamificación deben poder persistir por usuario sin depender del ciclo de vida del vehículo.
- Si una futura fuente real de telemetría aparece, el modelo sensórico transversal debe incorporarse sin romper las entidades principales.
