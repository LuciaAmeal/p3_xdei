# PRD - Plataforma FIWARE de movilidad urbana para A Coruña

## 1. Resumen ejecutivo

La aplicación propuesta es una plataforma de movilidad inteligente construida sobre FIWARE para monitorizar, simular y analizar el transporte público urbano de A Coruña. El sistema integra datos GTFS estáticos, telemetría dinámica de vehículos, consulta histórica tipo viaje en el tiempo, predicción de afluencia en paradas, gamificación y cuadros de mando analíticos.

El objetivo del producto es ofrecer una experiencia útil para dos perfiles principales: viajeros, que necesitan entender el estado del transporte en tiempo real y planificar desplazamientos; y operadores, que necesitan supervisar servicio, retrasos, ocupación y comportamiento histórico.

## 2. Objetivos del producto

1. Centralizar el estado del transporte público en un modelo de contexto NGSI-LD.
2. Visualizar en tiempo real vehículos, rutas y paradas en mapa 2D y escena 3D.
3. Permitir consultar la posición histórica de los vehículos en cualquier instante disponible.
4. Predecir la afluencia esperada en paradas a corto plazo.
5. Introducir mecánicas de gamificación para incentivar el uso del transporte público.
6. Exponer dashboards técnicos para análisis operativo.
7. Mantener un despliegue reproducible y local mediante Docker Compose.

## 3. Alcance

### 3.1 Incluido

- Ingesta de feed GTFS estático y publicación en Orion-LD.
- Simulación de vehículos activos con actualización periódica por MQTT.
- Traducción MQTT → NGSI-LD mediante IoT Agent.
- Persistencia histórica en QuantumLeap y CrateDB.
- Frontend con mapa 2D, escena 3D, línea temporal y panel de análisis.
- Endpoint de predicción de afluencia para paradas.
- Módulo de gamificación con usuarios autenticados, puntos y descuentos.
- Dashboards en Grafana.

### 3.2 Excluido

- Integración con sistemas de ticketing reales.
- Pago real de descuentos o integración bancaria.
- Autenticación federada con proveedor externo si no se define en la fase inicial.
- Optimización avanzada de rutas o replanificación automática del servicio.
- IA generativa o recomendaciones no justificadas por los datos disponibles.

## 4. Usuarios y necesidades

### 4.1 Viajero

Necesita ver dónde están los autobuses, cuándo llegará el próximo servicio y si una parada está congestionada. También puede participar en el sistema de puntos.

### 4.2 Operador de movilidad

Necesita supervisar retrasos, ocupación, histórico de servicio y patrones de uso para tomar decisiones operativas.

### 4.3 Administrador técnico

Necesita desplegar el sistema localmente, verificar salud de servicios y asegurar la integridad de los flujos de datos.

## 5. Requisitos funcionales

| ID | Requisito | Descripción |
|----|-----------|-------------|
| RF-01 | Carga GTFS | El sistema debe ingerir un feed GTFS completo y generar entidades NGSI-LD estáticas para rutas, paradas, viajes, horarios, shapes y servicios. |
| RF-02 | Simulación de vehículos | Debe existir un simulador que publique posición, retraso, ocupación y velocidad de cada vehículo activo cada 3 a 5 segundos. |
| RF-03 | Actualización en tiempo real | El IoT Agent debe traducir la telemetría MQTT a entidades NGSI-LD actualizadas en Orion-LD. |
| RF-04 | Histórico | Los cambios relevantes deben persistirse en QuantumLeap y CrateDB para consulta temporal. |
| RF-05 | Mapa 2D | El frontend debe mostrar rutas, paradas y vehículos en Leaflet con actualización automática. |
| RF-06 | Visualización 3D | El frontend debe mostrar una escena 3D navegable con vehículos animados y cámara orbital. |
| RF-07 | Viaje en el tiempo | El usuario debe poder seleccionar un instante histórico y ver el estado de los vehículos en ese momento. |
| RF-08 | Predicción de afluencia | El sistema debe estimar la ocupación esperada en una parada a 30 minutos vista. |
| RF-09 | Gamificación | El usuario debe acumular puntos al viajar y desbloquear logros al visitar nuevas paradas. |
| RF-10 | Descuentos | Los puntos deben poder canjearse por descuentos virtuales con trazabilidad. |
| RF-11 | Dashboards | Grafana debe mostrar métricas de retraso, ocupación y evolución temporal. |
| RF-12 | Responsividad | La interfaz debe funcionar en móvil y escritorio con controles táctiles y adaptación de layout. |

## 6. Historias de usuario

1. Como viajero, quiero ver en el mapa dónde está mi autobús para estimar si llegaré a tiempo.
2. Como viajero, quiero consultar la ocupación prevista de una parada para evitar aglomeraciones.
3. Como viajero, quiero explorar el estado pasado del servicio para comparar días y horas.
4. Como operador, quiero detectar líneas con retrasos recurrentes para priorizar acciones.
5. Como operador, quiero analizar ocupación histórica por parada para ajustar oferta.
6. Como usuario autenticado, quiero acumular puntos por mis trayectos y desbloquear recompensas.

## 7. Prioridad de funcionalidades

### MVP

1. Ingesta GTFS estático.
2. Simulación de vehículos y actualización en Orion-LD.
3. Mapa 2D con estado en tiempo real.
4. Histórico básico desde QuantumLeap.

### Segunda fase

1. Escena 3D.
2. Línea temporal y viaje en el tiempo.
3. Predicción de afluencia.
4. Grafana con métricas operativas.

### Tercera fase

1. Gamificación completa.
2. Integración de descuentos y logros.
3. Refinamiento móvil y UX avanzada.

## 8. Requisitos no funcionales

- Despliegue local completo con Docker Compose.
- Uso preferente de NGSI-LD en lugar de NGSIv2.
- Modelo ML ligero, entrenable en menos de 5 minutos en un portátil estándar.
- La escena 3D debe sostener al menos 30 FPS con hasta 20 vehículos simultáneos.
- Los datos de prueba deben ser reproducibles mediante scripts.
- El sistema debe seguir funcionando sin conexión una vez descargadas las dependencias y el feed GTFS.
- El ZIP de entrega no debe superar 200 MB.

## 9. Criterios de éxito

- El mapa muestra vehículos y paradas con datos reales o simulados sin intervención manual.
- El usuario puede retroceder y avanzar en el tiempo y obtener posiciones históricas correctas.
- La predicción devuelve un valor útil y coherente con horarios y datos históricos.
- El sistema de puntos acumula y redime recompensas de forma consistente.
- El despliegue local se levanta con un único comando documentado.

## 10. Suposiciones y dependencias

- Existe un feed GTFS concreto aprobado para A Coruña.
- Los usuarios de gamificación estarán autenticados.
- Orion-LD es el broker de contexto principal.
- QuantumLeap y CrateDB se usarán para histórico temporal.
- El IoT Agent actuará como puente entre MQTT y NGSI-LD.

## 11. Riesgos

1. Inconsistencias entre GTFS estático y simulación dinámica.
2. Exceso de complejidad en la escena 3D para navegadores modestos.
3. Poca calidad o escasez de datos históricos para el modelo de afluencia.
4. Complejidad añadida por la autenticación si se intenta resolver demasiado pronto.
5. Dependencia de detalles del feed GTFS seleccionado.

## 12. Métricas operativas

- Latencia media de actualización del vehículo en el frontend.
- Tiempo de consulta del histórico por intervalo.
- Error medio de predicción de ocupación.
- Número de puntos y canjes por usuario.
- Tiempo de arranque completo del stack en local.
