# 1. Explicación detallada de la aplicación

La aplicación que vamos a implementar es un sistema integral de movilidad inteligente para la ciudad de A Coruña, que combina en una sola plataforma múltiples funcionalidades avanzadas:

- **Un gemelo digital del transporte público** — La página principal muestra un mapa de la ciudad (en vista 2D con Leaflet y en 3D inmersiva con Three.js) donde los autobuses se mueven sobre las rutas GTFS en tiempo real. Los vehículos se representan como elementos coloreados que se desplazan suavemente por la ciudad, y el usuario puede «volar» por la escena, hacer clic sobre cualquier autobús y consultar su retraso, nivel de ocupación y próximo destino.
- **Un sistema de «viaje en el tiempo»** — Permite seleccionar cualquier instante pasado dentro del período del que se dispone de datos históricos y visualizar dónde estaban exactamente los vehículos en ese momento. Esta funcionalidad se apoya en QuantumLeap, el componente FIWARE especializado en el almacenamiento y consulta de series temporales.
- **Un sistema de predicción de afluencia en paradas** — No se limita a mostrar la posición de los vehículos, sino que predice cuántos pasajeros se espera que haya en cada parada. Esto permite a los viajeros planificar sus desplazamientos para evitar aglomeraciones y a los operadores del transporte público tomar decisiones informadas (por ejemplo, reforzar una línea con autobuses adicionales cuando se prevé alta demanda).
- **Un minijuego de gamificación** — Diseñado para fomentar el uso del transporte público, los viajeros acumulan puntos cada vez que toman un autobús y desbloquean «zonas» o logros cuando descienden o suben en nuevas paradas que no habían visitado antes. Los puntos acumulados pueden canjearse por descuentos virtuales, incentivando así la exploración de la ciudad y el uso habitual del transporte público.

# 2. Tecnologías utilizadas y su propósito

La aplicación se construye sobre la plataforma FIWARE, un ecosistema de componentes de código abierto diseñado específicamente para entornos inteligentes, y se complementa con tecnologías de visualización y análisis de datos.

## Componentes FIWARE

| Componente | Tecnología | Propósito en la aplicación |
|------------|------------|----------------------------|
| Orion-LD | Context Broker NGSI-LD | Es el núcleo de la plataforma: almacena en tiempo real el estado actual de todas las entidades (autobuses, rutas, paradas, viajes, etc.) y gestiona las suscripciones para notificar cambios. Implementa el estándar ETSI NGSI-LD (versión 1.6.1/1.8.1), lo que permite consultas avanzadas y relaciones semánticas entre entidades. |
| IoT Agent JSON | Puente MQTT ↔ NGSI-LD | Recibe los mensajes MQTT enviados por el simulador de vehículos (posición, retraso, ocupación, velocidad) y los traduce a entidades NGSI-LD en Orion-LD. Soporta tanto MQTT como HTTP como transporte. |
| Mosquitto | Broker MQTT | Actúa como intermediario de mensajería ligera: el simulador publica en tópicos MQTT y el IoT Agent se suscribe a ellos para recibir las actualizaciones de los vehículos. |
| QuantumLeap | Almacenamiento de series temporales | Se suscribe a Orion-LD para recibir notificaciones de los cambios en atributos relevantes (posición, retraso, ocupación) y los persiste en una base de datos de series temporales, permitiendo consultas históricas y la funcionalidad de «viaje en el tiempo». |
| CrateDB | Base de datos de series temporales | Almacena de forma eficiente grandes volúmenes de datos temporales (posiciones y estados de los vehículos a lo largo del tiempo). Soporta consultas geoespaciales y se integra nativamente con herramientas de visualización como Grafana. |
| Grafana | Dashboard de análisis | Conectado directamente a CrateDB, ofrece dashboards profesionales con gráficos de evolución de retrasos, mapas de calor de ocupación por parada y otras visualizaciones analíticas para operadores. |

## Tecnologías del Frontend y análisis

| Tecnología | Propósito |
|------------|-----------|
| Leaflet + OpenStreetMap | Proporciona la visualización en mapa 2D: rutas coloreadas, marcadores de paradas y vehículos en movimiento, con interacción básica. |
| Three.js | Permite la experiencia inmersiva en 3D: representación de la ciudad con edificios genéricos, vehículos como objetos tridimensionales, cámara orbitable y movimiento suave mediante interpolación entre posiciones recibidas. |
| Chart.js | Genera gráficos estadísticos en tiempo real: evolución de retrasos por línea, ocupación por parada, etc. |
| Flask (Python) | Backend propio que actúa como orquestador: expone una API REST para el frontend, comunica con Orion-LD y QuantumLeap, entrena y ejecuta el modelo de Machine Learning para predicción de afluencia, y gestiona la lógica del minijuego de gamificación. |
| scikit-learn / Pandas | Biblioteca de Machine Learning para entrenar el modelo predictivo de afluencia en paradas (RandomForest o regresión) usando datos históricos de ocupación y horarios. |
| Docker + Docker Compose | Orquestación de todos los servicios (Orion-LD, IoT Agent, Mosquitto, QuantumLeap, CrateDB, Grafana, backend, frontend) en contenedores independientes pero interconectados. |

# 3. Visión general del sistema

La arquitectura sigue el patrón típico de FIWARE:

1. **Capa de datos estáticos** — Un script (`load_gtfs.py`) ingesta el feed GTFS estático de la ciudad (rutas, paradas, horarios, formas geométricas, calendarios) y lo transforma a entidades NGSI-LD que se almacenan en Orion-LD. Estas entidades no cambian a menos que se actualice el feed.
2. **Capa de simulación de datos dinámicos** — El simulador (`dynamic_simulator.py`) determina qué viajes están activos según la hora actual y el calendario, calcula la posición interpolada de cada vehículo sobre su ruta, añade un retraso aleatorio realista y publica el estado en un tópico MQTT.
3. **Capa de ingesta** — El IoT Agent JSON recibe los mensajes MQTT, los traduce a NGSI-LD y actualiza las entidades `VehicleState` en Orion-LD.
4. **Capa de persistencia histórica** — Una suscripción configurada en Orion-LD notifica a QuantumLeap cada cambio en los atributos de `VehicleState`. QuantumLeap persiste estos datos en CrateDB.
5. **Capa de backend propio** — Flask expone endpoints para que el frontend consulte:
   - Estado actual de vehículos, rutas y paradas (desde Orion-LD).
   - Datos históricos para el «viaje en el tiempo» (desde QuantumLeap).
   - Predicciones de afluencia (usando el modelo ML entrenado con datos históricos).
   - Puntuaciones y progreso de los usuarios en el minijuego.
6. **Capa de frontend** — HTML/JS que consume la API del backend y actualiza en tiempo real:
   - Mapa Leaflet con vehículos, rutas y paradas.
   - Escena Three.js con vehículos animados en 3D.
   - Control deslizante de tiempo y botón de reproducción para «viajar en el tiempo».
   - Gráficos Chart.js.
   - Panel del minijuego (puntos acumulados, zonas desbloqueadas).
7. **Capa de monitorización** — Grafana conectado directamente a CrateDB para dashboards analíticos.

# 4. Especificación completa del sistema

## 4.1. Datos GTFS estáticos

La aplicación debe ingestar un feed GTFS real de A Coruña (o una ciudad de similar tamaño) y modelarlo según los `dataModel.UrbanMobility` de FIWARE. Las entidades principales son:

- **GtfsRoute** — rutas (líneas de autobús), con atributos como `routeShortName` (número de línea), `routeLongName` (nombre), `routeColor` (color para visualización) y relaciones con viajes y paradas.
- **GtfsStop** — paradas, con atributos `name`, `stopLat`, `stopLon` y una geo-propiedad `location` de tipo `Point`.
- **GtfsTrip** — viajes (cada recorrido concreto de una ruta en un día/horario), con relaciones `hasRoute` (→ `GtfsRoute`) y `hasService` (→ `GtfsService`).
- **GtfsStopTime** — horarios de paso por paradas, con atributos `arrivalTime`, `departureTime`, `stopSequence` y relaciones `hasStop` (→ `GtfsStop`) y `hasTrip` (→ `GtfsTrip`).
- **GtfsShape** — trazado geográfico de la ruta, con una geo-propiedad `location` de tipo `LineString`.
- **GtfsService / GtfsCalendar** — reglas de servicio (días operativos, fechas de inicio y fin).

## 4.2. Datos dinámicos de los vehículos

Para cada viaje activo se crea una entidad `VehicleState` (propia) con atributos dinámicos:

- `currentPosition` — geo-propiedad `Point` con las coordenadas actuales del autobús.
- `delaySeconds` — retraso en segundos (valor entero, puede ser negativo si va adelantado).
- `occupancy` — ocupación estimada (0–100%).
- `speed` — velocidad en km/h.
- `trip` — relación hacia la entidad `GtfsTrip` correspondiente.

## 4.3. Datos del minijuego

Se añaden dos entidades personalizadas:

- **UserProfile** — almacena el progreso de cada usuario: puntos acumulados (`totalPoints`), lista de paradas visitadas (`visitedStops`), logros desbloqueados (`achievements`) y fecha de última actualización.
- **RedeemedDiscount** — registra los descuentos canjeados por el usuario: código del descuento, valor, fecha de canje y validez.

## 4.4. Datos de predicción de afluencia

Se añade la entidad `StopCrowdPrediction` (opcional) para almacenar predicciones generadas por el modelo ML: `predictedOccupancy`, `validFrom`, `validTo`, y relaciones `hasStop` (→ `GtfsStop`) y `hasTrip` (→ `GtfsTrip`).

## 4.5. Funcionalidades clave

- **Visualización dual 2D/3D** — Leaflet para contexto geográfico general, Three.js para inmersión. Sincronización entre ambas vistas mediante la misma fuente de datos.
- **Viaje en el tiempo** — Control deslizante que permite seleccionar cualquier instante del histórico; el frontend consulta a QuantumLeap y reposiciona todos los vehículos en sus coordenadas históricas.
- **Predicción de afluencia** — Modelo ML (RandomForest) entrenado con datos históricos de ocupación; endpoint `/api/predict` que, dado un `stop_id` y una hora, devuelve la ocupación esperada.
- **Minijuego de gamificación** — El backend gestiona la acumulación de puntos cuando un usuario «toma un autobús» (evento simulado o real) y desbloquea logros al visitar nuevas paradas; se expone un endpoint para canjear puntos por descuentos.

# 5. Requisitos funcionales

| ID | Requisito | Descripción |
|----|-----------|-------------|
| RF-01 | Carga de GTFS estático | El sistema debe ingestar un feed GTFS completo y crear las correspondientes entidades NGSI-LD en Orion-LD. |
| RF-02 | Simulación de vehículos | Debe existir un simulador que publique periódicamente (cada 3–5 segundos) la posición, retraso, ocupación y velocidad de cada vehículo activo mediante MQTT. |
| RF-03 | Actualización en tiempo real | El IoT Agent debe recibir los mensajes MQTT y actualizar las entidades `VehicleState` en Orion-LD. |
| RF-04 | Almacenamiento histórico | Orion-LD debe notificar a QuantumLeap los cambios en `VehicleState` y QuantumLeap debe persistirlos en CrateDB. |
| RF-05 | Visualización en mapa 2D | El frontend debe mostrar un mapa Leaflet con rutas, paradas y vehículos móviles, actualizándose automáticamente. |
| RF-06 | Visualización en 3D | El frontend debe mostrar una escena Three.js con vehículos como objetos 3D de colores, movimiento suave y cámara orbitable. |
| RF-07 | Viaje en el tiempo | El usuario debe poder seleccionar cualquier instante histórico mediante un control deslizante y ver la posición de los vehículos en ese momento. |
| RF-08 | Predicción de afluencia | El sistema debe predecir la ocupación esperada en una parada para los próximos 30 minutos usando un modelo ML entrenado con datos históricos. |
| RF-09 | Minijuego de puntos | El usuario debe acumular puntos al «tomar un autobús» y desbloquear logros al visitar nuevas paradas. |
| RF-10 | Canje de descuentos | Los puntos acumulados deben poder canjearse por descuentos virtuales, registrando el canje en el sistema. |
| RF-11 | Dashboards analíticos | Grafana debe ofrecer dashboards con métricas de retraso y ocupación. |
| RF-12 | Responsividad móvil | La interfaz debe ser usable en dispositivos móviles (pestañas para alternar vistas, controles táctiles). |

# 6. Restricciones adicionales

1. Todo el sistema debe ser ejecutable localmente mediante `docker-compose up`, sin dependencia de servicios externos de pago.
2. El modelo ML debe ser ligero (RandomForest o regresión lineal) y entrenar en menos de 5 minutos en un portátil estándar.
3. La escena 3D debe mantener al menos 30 FPS con hasta 20 vehículos simultáneos.
4. Las entidades deben seguir estrictamente el formato NGSI-LD (no NGSIv2), incluyendo `@context` y relaciones mediante `Relationship`.
5. El archivo ZIP final de entrega no debe superar los 200 MB.
6. El repositorio GitHub debe ser accesible por el evaluador (público o privado con invitación).
7. Los datos de prueba deben generarse de forma reproducible mediante scripts, no manualmente.
8. La aplicación debe ser funcional sin conexión a Internet una vez descargados el feed GTFS y las dependencias base.