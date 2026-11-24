# Spec Delta

## Purpose

Hacer visible lo que hace el sistema en cada request (logs correlacionados, métricas, trazas, dashboard y alertas, todo levantado como código) y dejar registrada cada corrida de evaluación como un experimento comparable.

## ADDED Requirements

### Requirement: Logs estructurados correlacionados
El gateway y el servicio de IA SHALL emitir logs en JSON, una línea por evento, con los campos `ts`, `level`, `service`, `request_id` y `event`, y MUST propagar el mismo `request_id` desde el gateway hasta el servicio de IA.

#### Scenario: Mismo request_id en ambos servicios
- **WHEN** un cliente hace un `/query` a través del gateway
- **THEN** todas las líneas de log de ese request, en el gateway y en el servicio de IA, son JSON válido y tienen el mismo `request_id`, y la respuesta lo devuelve en el header `X-Request-ID`

#### Scenario: request_id entrante
- **WHEN** el cliente envía un `X-Request-ID` con formato válido
- **THEN** el sistema usa ese valor; si el formato es inválido, genera uno nuevo y no registra el valor recibido

### Requirement: Métricas de servicio
Cada servicio SHALL exponer métricas por endpoint de cantidad de requests, errores (respuestas 5xx) y latencia con la que se pueden calcular p50 y p95, y MUST etiquetarlas por la plantilla de la ruta y no por la URL concreta.

#### Scenario: Métricas después de tráfico
- **WHEN** se hacen 20 requests a `/query` y 5 a `/health`, y 2 de los de `/query` fallan con 5xx
- **THEN** las métricas expuestas muestran 20 requests y 2 errores para `/query`, 5 requests y 0 errores para `/health`, y un histograma de latencia por endpoint

#### Scenario: Cardinalidad acotada
- **WHEN** se hacen requests a 100 URLs que difieren solo en un identificador de path
- **THEN** la cantidad de series de latencia no crece con el identificador

### Requirement: Métricas de LLM, recuperación y abstención
El servicio de IA SHALL exponer los tokens de entrada y salida y el costo estimado en USD por modelo, la latencia de la recuperación y la cantidad de respuestas y de abstenciones del RAG, de forma que la tasa de abstención se pueda calcular.

#### Scenario: Tokens y costo
- **WHEN** se responde una consulta con el proveedor `fake`, que reporta 100 tokens de entrada y 50 de salida, y la tabla de precios de prueba asigna 1 USD por millón de tokens de cada tipo
- **THEN** los contadores de tokens aumentan en 100 y 50, y el costo estimado aumenta en 0,00015 USD

#### Scenario: Abstención
- **WHEN** se hacen 10 consultas y en 3 el RAG se abstiene
- **THEN** las métricas permiten calcular una tasa de abstención de 0,3

### Requirement: Trazas distribuidas
El sistema SHALL generar una traza por request que cubra el gateway, el servicio de IA, la llamada al LLM y la búsqueda vectorial, y MUST NOT incluir en los atributos de los spans el texto del prompt, de la respuesta ni de los chunks.

#### Scenario: Traza de punta a punta
- **WHEN** se hace un `/query` con todos los servicios levantados
- **THEN** existe una única traza, con el `trace_id` presente en los logs de ese request, que contiene spans del gateway, del endpoint del servicio de IA, de la búsqueda vectorial y de la llamada al LLM, anidados en ese orden

#### Scenario: Sin contenido en los spans
- **WHEN** se traza una consulta que contiene `secreto-de-prueba`
- **THEN** la cadena `secreto-de-prueba` no aparece en ningún atributo ni evento de la traza

### Requirement: Dashboard y alerta como código
El entorno local SHALL levantar, con el comando de arranque del repo y sin pasos manuales, un dashboard con request rate, error rate, latencia p50 y p95 por endpoint, tokens, costo estimado, latencia de recuperación y tasa de abstención, y MUST incluir al menos una regla de alerta versionada sobre la latencia p95 o la tasa de errores en una ventana de 5 minutos.

#### Scenario: Dashboard provisionado
- **WHEN** se levanta el entorno local desde cero
- **THEN** el dashboard y la regla de alerta existen sin intervención manual y sus paneles muestran datos después de generar tráfico

#### Scenario: Alerta disparada a propósito
- **WHEN** se corre el script de disparo de alerta con la inyección de fallas habilitada
- **THEN** la regla pasa a estado de disparo en 10 minutos o menos (propuesto) y el script termina con código 0; con la inyección deshabilitada, el endpoint de fallas no existe

#### Scenario: Umbral de la alerta
- **WHEN** la tasa de errores de `/query` supera el 5% o su p95 supera 5 s durante 5 minutos (umbrales propuestos)
- **THEN** la alerta se dispara, y no se dispara con tráfico normal de la demo

### Requirement: Seguimiento de experimentos de evaluación
Cada corrida de evaluación SHALL quedar registrada en el servidor de experimentos del entorno local con sus parámetros (configuración del pipeline, modelo y commit de git), sus métricas y sus artefactos (resultados en JSON y tabla Markdown), y MUST poder compararse con otras corridas del mismo experimento.

#### Scenario: Corrida registrada
- **WHEN** se corre la evaluación RAG con el servidor de experimentos levantado
- **THEN** aparece una corrida nueva en el experimento de evaluación RAG con el commit, los parámetros, las métricas y los artefactos

#### Scenario: Servidor caído
- **WHEN** se corre la evaluación y el servidor de experimentos no responde
- **THEN** la evaluación termina igual, guarda sus resultados en disco y avisa en el log que la corrida no se registró
