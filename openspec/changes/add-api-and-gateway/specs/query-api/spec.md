# Spec Delta

## Purpose

Exponer por HTTP la ingesta de documentos y las consultas al RAG con citas, en streaming o completas, junto con el estado de salud del servicio, con contratos tipados, errores predecibles y latencia medida bajo carga.

## ADDED Requirements

### Requirement: Ingesta asíncrona por subida de archivos
`POST /ingest` SHALL aceptar uno o más archivos en `multipart/form-data`, responder 202 con un `job_id` sin esperar al procesamiento, y `GET /ingest/{job_id}` SHALL informar el estado del job (`queued`, `running`, `succeeded`, `partial` o `failed`) y, al terminar, el `doc_id` o el error de cada archivo.

#### Scenario: Subida válida
- **WHEN** se suben 2 PDFs ficticios válidos
- **THEN** la respuesta es 202 con un `job_id` en menos de 1 segundo, y al consultar el job termina en `succeeded` con 2 `doc_id` indexados

#### Scenario: Lote con un archivo fallido
- **WHEN** se suben un PDF válido y un PDF corrupto
- **THEN** el job termina en `partial`, con un `doc_id` para el válido y un error tipado para el corrupto

#### Scenario: Job inexistente
- **WHEN** se consulta `GET /ingest/{job_id}` con un id que no existe
- **THEN** la respuesta es 404 con el código `not_found`

### Requirement: Límites de tamaño y tipo en la subida
`POST /ingest` MUST rechazar el pedido completo, sin crear un job, si algún archivo supera `API_MAX_UPLOAD_MB`, si hay más de `API_MAX_FILES` archivos o si el contenido real de algún archivo no es PDF, PNG, JPEG o TIFF, sin importar la extensión ni el `Content-Type` declarados (propuesto: 20 MB y 10 archivos).

#### Scenario: Archivo demasiado grande
- **WHEN** se sube un archivo de 21 MB con `API_MAX_UPLOAD_MB=20`
- **THEN** la respuesta es 413 con el código `payload_too_large` y no se crea ningún job

#### Scenario: Tipo disfrazado
- **WHEN** se sube un ejecutable renombrado como `informe.pdf` con `Content-Type: application/pdf`
- **THEN** la respuesta es 415 con el código `unsupported_media_type`

### Requirement: Consulta en streaming
`POST /query` SHALL aceptar un cuerpo `{question, filters, top_k}` validado y, por defecto, responder como `text/event-stream` con cero o más eventos `token`, exactamente un evento `citations` con la lista de `[doc_id, page]` y el indicador de abstención, y un evento final `done` con el uso de tokens, la latencia y el `request_id`, en ese orden.

#### Scenario: Pregunta con respuesta en el corpus
- **WHEN** se consulta con el LLM `fake` una pregunta cuya respuesta está en un documento indexado
- **THEN** llegan eventos `token` cuya concatenación es la respuesta, después un `citations` con al menos una cita de ese documento y por último un `done` con tokens de entrada y salida

#### Scenario: Abstención
- **WHEN** se consulta una pregunta sin evidencia en el índice
- **THEN** el evento `citations` tiene la lista vacía y `abstained: true`, y el stream termina con `done`

#### Scenario: Primer evento rápido
- **WHEN** se consulta con el LLM `fake` sin latencia simulada
- **THEN** el primer evento llega en 300 ms o menos desde el pedido (propuesto)

### Requirement: Consulta sin streaming
`POST /query` con `stream: false` SHALL devolver una sola respuesta JSON con `answer`, `citations`, `abstained`, `usage` y `request_id`, equivalente al contenido del modo streaming.

#### Scenario: Equivalencia de modos
- **WHEN** se hace la misma consulta con el LLM `fake` en modo streaming y con `stream: false`
- **THEN** el `answer` es igual a la concatenación de los `token` y las citas son las mismas

### Requirement: Validación de la consulta
La API MUST rechazar con 422 y el código `validation_error` una consulta con `question` vacía o de más de 2000 caracteres, con `top_k` fuera del rango 1 a 50 o con campos desconocidos (propuesto: 2000 caracteres y top_k de 1 a 50).

#### Scenario: top_k inválido
- **WHEN** se envía `top_k: 0`
- **THEN** la respuesta es 422 con el código `validation_error` y el campo `top_k` señalado, y no se llama al LLM

### Requirement: Salud del servicio
El servicio SHALL exponer `GET /health/live`, que responde 200 si el proceso atiende sin consultar dependencias, y `GET /health/ready`, que responde 200 solo si el vector store responde y el cliente LLM está configurado, y 503 con el detalle por dependencia en caso contrario. Ambos MUST responder en 2,5 segundos o menos.

#### Scenario: Vector store caído
- **WHEN** el vector store no responde
- **THEN** `/health/live` responde 200 y `/health/ready` responde 503 en 2,5 segundos o menos, indicando que la dependencia `vector_store` falla

### Requirement: Errores tipados
Todo error de la API SHALL responder con un cuerpo `{code, message, request_id}` y un código HTTP acorde, y MUST NOT incluir trazas, rutas internas ni el texto de la pregunta.

#### Scenario: Falla interna
- **WHEN** el RAG lanza una excepción inesperada durante una consulta no streaming cuya pregunta contiene `secreto-de-prueba`
- **THEN** la respuesta es 500 con el código `internal_error` y el `request_id`, y ni la traza ni `secreto-de-prueba` aparecen en el cuerpo

#### Scenario: Error después de empezar el stream
- **WHEN** el LLM falla después de haber emitido tokens
- **THEN** el stream emite un evento `error` con `code` y `request_id` y se cierra sin evento `done`

### Requirement: Propagación del request id
La API SHALL usar el `X-Request-ID` recibido si es válido o generar uno nuevo, devolverlo en el encabezado de la respuesta y en los cuerpos y eventos, e incluirlo en todos los logs del pedido.

#### Scenario: Request id recibido
- **WHEN** se consulta con `X-Request-ID: prueba-123`
- **THEN** la respuesta tiene `X-Request-ID: prueba-123`, el evento `done` lo incluye y todos los logs del pedido lo registran

#### Scenario: Request id inválido
- **WHEN** se envía un `X-Request-ID` de 200 caracteres o con caracteres de control
- **THEN** se ignora y se genera un id nuevo

### Requirement: Timeout y cancelación de la consulta
Toda consulta MUST terminar en `API_QUERY_TIMEOUT_SECONDS` más 1 segundo como máximo, y si el cliente se desconecta durante el streaming, la API SHALL dejar de pedir tokens al LLM.

#### Scenario: LLM que no termina
- **WHEN** el LLM `fake` se cuelga después del primer token y `API_QUERY_TIMEOUT_SECONDS=2`
- **THEN** el stream emite un evento `error` con `upstream_timeout` en 3 segundos o menos

#### Scenario: Cliente que se va
- **WHEN** el cliente cierra la conexión después del tercer token de una respuesta de 100 tokens
- **THEN** el LLM `fake` deja de recibir pedidos de tokens en 1 segundo o menos y se registra la cancelación

### Requirement: Concurrencia sin bloqueos
Los endpoints async MUST NOT ejecutar llamadas bloqueantes en el event loop, y la API SHALL sostener consultas concurrentes con una latencia p95 acotada.

#### Scenario: Prueba de carga corta
- **WHEN** se lanzan 50 consultas concurrentes en streaming con el LLM `fake` (20 tokens con 10 ms entre tokens) y el vector store en memoria
- **THEN** todas terminan con `done` y el p95 hasta el evento `done` es de 500 ms o menos en local (propuesto)

#### Scenario: Ingesta en curso no frena las consultas
- **WHEN** se ejecuta un job de ingesta de 5 documentos y al mismo tiempo 10 consultas con el LLM `fake`
- **THEN** el p95 de las consultas no sube más de un 50% respecto de la misma carga sin ingesta (propuesto)
