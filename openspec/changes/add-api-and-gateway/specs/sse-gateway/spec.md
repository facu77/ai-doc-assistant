# Spec Delta

## Purpose

Entregar a los clientes web las respuestas del servicio de IA token a token mediante Server-Sent Events, con un contrato de eventos estable, entrada validada, cancelación hacia arriba y fallos que siempre terminan en un evento explícito.

## ADDED Requirements

### Requirement: Endpoint SSE de consulta
El gateway SHALL exponer `POST /api/query` con cuerpo JSON `{question, filters, top_k}` y responder con `Content-Type: text/event-stream`, reenviando el stream del servicio de IA como eventos `token`, `citations`, `error` y `done`, en el mismo orden y sin alterar su contenido.

#### Scenario: Stream completo
- **WHEN** el servicio de IA emite 5 eventos `token`, un `citations` y un `done`
- **THEN** el cliente recibe exactamente esos 7 eventos con los mismos tipos, el mismo orden y los mismos datos

#### Scenario: Sin buffering
- **WHEN** el servicio de IA emite un token cada 100 ms
- **THEN** el cliente recibe cada token en 50 ms o menos desde que lo emitió el servicio de IA (propuesto)

### Requirement: Validación de la entrada
El gateway MUST validar el cuerpo antes de llamar al servicio de IA y rechazar con 400 y un cuerpo `{code, message, request_id}` una entrada inválida, sin abrir el stream.

#### Scenario: Pregunta faltante
- **WHEN** se envía `{"top_k": 5}` sin `question`
- **THEN** la respuesta es 400 con el código `validation_error` y no se hace ningún pedido al servicio de IA

#### Scenario: Cuerpo demasiado grande
- **WHEN** se envía un cuerpo de más de 16 KB (propuesto)
- **THEN** la respuesta es 413 y no se hace ningún pedido al servicio de IA

### Requirement: Eventos del servicio de IA validados
El gateway MUST validar cada evento recibido del servicio de IA contra el contrato y, ante un evento inválido, SHALL emitir un evento `error` con el código `bad_upstream_event` y cerrar el stream.

#### Scenario: Evento malformado
- **WHEN** el servicio de IA emite un evento `token` con `data` que no es JSON válido
- **THEN** el cliente recibe un evento `error` con `bad_upstream_event` y el stream se cierra

### Requirement: Heartbeats
Mientras el stream esté abierto, el gateway SHALL enviar un comentario SSE de heartbeat cada `GATEWAY_HEARTBEAT_SECONDS` sin eventos, y MUST NOT enviarlo después de cerrar el stream.

#### Scenario: Servicio de IA en silencio
- **WHEN** el servicio de IA tarda 5 segundos en emitir el primer token con `GATEWAY_HEARTBEAT_SECONDS=1`
- **THEN** el cliente recibe al menos 4 heartbeats antes del primer `token`

### Requirement: Cancelación hacia arriba
Cuando el cliente se desconecta, el gateway SHALL cancelar el pedido al servicio de IA y liberar sus recursos.

#### Scenario: Cliente que cierra la pestaña
- **WHEN** el cliente se desconecta después de recibir 2 tokens
- **THEN** la conexión hacia el servicio de IA se cierra en 1 segundo o menos y no quedan timers de heartbeat activos

### Requirement: Fallos del servicio de IA como eventos
Si el servicio de IA no responde dentro de `GATEWAY_UPSTREAM_TIMEOUT_SECONDS`, responde con un error HTTP o corta el stream sin `done`, el gateway SHALL emitir un evento `error` con un código tipado (`upstream_timeout`, `upstream_unavailable` o `upstream_error`) y el `request_id`, y MUST cerrar el stream.

#### Scenario: Timeout del servicio de IA
- **WHEN** el servicio de IA no envía nada y `GATEWAY_UPSTREAM_TIMEOUT_SECONDS=2`
- **THEN** el cliente recibe un evento `error` con `upstream_timeout` en 3 segundos o menos y el stream se cierra

#### Scenario: Servicio de IA caído
- **WHEN** el servicio de IA no acepta conexiones
- **THEN** el cliente recibe un evento `error` con `upstream_unavailable`

#### Scenario: Error de validación del servicio de IA
- **WHEN** el servicio de IA responde 422 con un cuerpo de error tipado
- **THEN** el cliente recibe un evento `error` con el mismo `code` y el mismo `request_id`

### Requirement: Propagación del request id
El gateway SHALL reenviar al servicio de IA el `X-Request-ID` recibido si es válido o uno generado, y MUST devolverlo en el encabezado de la respuesta al cliente.

#### Scenario: Id generado en el gateway
- **WHEN** el cliente consulta sin `X-Request-ID`
- **THEN** el gateway genera un id, el servicio de IA recibe ese mismo id y el cliente lo ve en el encabezado y en el evento `done`

### Requirement: CORS configurable
El gateway SHALL permitir solo los orígenes listados en `GATEWAY_CORS_ORIGINS` y responder los preflight `OPTIONS`, y MUST NOT devolver `Access-Control-Allow-Origin: *` salvo que la configuración lo pida explícitamente.

#### Scenario: Origen permitido
- **WHEN** llega un preflight desde un origen de la lista
- **THEN** la respuesta es 204 con ese origen en `Access-Control-Allow-Origin`

#### Scenario: Origen no permitido
- **WHEN** llega un pedido desde un origen fuera de la lista
- **THEN** la respuesta no incluye `Access-Control-Allow-Origin`

### Requirement: Salud y configuración del gateway
El gateway SHALL exponer `GET /healthz`, que responde 200 si el proceso atiende, y MUST fallar al arrancar si su configuración es inválida, nombrando la variable con problemas.

#### Scenario: URL del servicio de IA inválida
- **WHEN** el gateway arranca con `GATEWAY_AI_URL=no-es-una-url`
- **THEN** el proceso termina con un error de configuración que nombra `GATEWAY_AI_URL`
