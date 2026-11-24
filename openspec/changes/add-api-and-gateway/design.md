# Design

## Context

`add-rag-core` entrega una función async que, dada una pregunta, filtros y `top_k`, devuelve un iterador de tokens y al final la respuesta con citas `[doc_id, page]`, el indicador de abstención y el uso de tokens. `add-ingest-pipeline` procesa archivos a `IngestedDocument` y `add-vector-index` los indexa. Falta exponer todo eso por HTTP y llevar el streaming hasta el navegador. El consumidor del gateway es una interfaz web futura y, en el POC, `curl -N` y los tests.

## Goals / Non-Goals

**Goals:**
- Un contrato de eventos único entre el servicio de IA y el gateway, y entre el gateway y el cliente.
- Nada bloqueante dentro de los endpoints async; toda llamada de red con timeout.
- Cancelación real: si el cliente se va, el LLM deja de generar.
- Tests 100% offline con el LLM `fake` y un vector store en memoria.

**Non-Goals:**
- Autenticación, ACL y rate limiting (`add-observability-security`).
- Cola de trabajos distribuida, reintentos de jobs y persistencia de jobs entre reinicios (ver preguntas abiertas).
- Interfaz web.

## Decisions

- **Formato de streaming entre ai y gateway: SSE**, el mismo que ve el cliente. El servicio de IA emite `event: token|citations|error|done` con `data` JSON validado por modelos Pydantic (`TokenEvent`, `CitationsEvent`, `ErrorEvent`, `DoneEvent`). El gateway valida cada evento con el esquema Zod equivalente y lo reenvía; no reinterpreta contenido. Se prefiere SSE sobre NDJSON porque permite probar el servicio de IA directo con un cliente SSE y reduce la traducción en el gateway.
- **SSE en FastAPI**: `StreamingResponse` con un generador async propio y `media_type="text/event-stream"`, sin `sse-starlette`, para controlar el orden de eventos y la detección de desconexión (`request.is_disconnected()`). Se revisa con `docs-checker`; si hace falta, se cambia a `sse-starlette`.
- **`/query` no streaming**: `stream: false` en el cuerpo (por defecto `true`) devuelve un `QueryResponse` JSON con `answer`, `citations`, `abstained`, `usage` y `request_id`. Comparte el mismo camino de código y consume el iterador completo.
- **Ingesta asíncrona**: `POST /ingest` valida extensión, *magic bytes* y tamaño leyendo por bloques (no confía en `Content-Type` ni en `Content-Length`), guarda los archivos en un directorio temporal y crea un job `queued`. Un `asyncio.Task` corre el pipeline con `asyncio.to_thread` (es CPU y es síncrono) bajo un `asyncio.Semaphore` de concurrencia 1 (configurable). Los jobs viven en un `JobStore` en memoria detrás de un Protocol, para cambiarlo por SQLite o Redis sin tocar los endpoints. Estados: `queued`, `running`, `succeeded`, `partial`, `failed`.
- **Health**: `/health/live` no toca dependencias. `/health/ready` consulta el vector store con un timeout de 2 s y verifica que el cliente LLM se construyó (no llama al proveedor, para no gastar tokens en cada healthcheck).
- **Errores**: un `exception_handler` traduce `ValidationError`, los errores del LLM (`LLMTimeoutError`, etc.), del vector store y los propios (`PayloadTooLarge`, `UnsupportedMediaType`, `JobNotFound`) a `ErrorBody{code, message, request_id}`. Tabla: 413 `payload_too_large`, 415 `unsupported_media_type`, 422 `validation_error`, 404 `not_found`, 503 `dependency_unavailable`, 504 `upstream_timeout`, 500 `internal_error`. Nunca se devuelve la traza ni el texto de la pregunta.
- **Request id**: middleware ASGI puro (no `BaseHTTPMiddleware`, que rompe el streaming) que lee `X-Request-ID` si cumple `^[A-Za-z0-9._-]{1,64}$` o genera un UUID4, lo guarda en un `contextvars.ContextVar` para los logs y lo devuelve en la respuesta.
- **Timeouts**: `API_QUERY_TIMEOUT_SECONDS` envuelve toda la consulta con `asyncio.timeout`; en streaming, si vence después del primer token, se emite un evento `error` con `upstream_timeout` y se cierra el stream.
- **Gateway: `node:http` + `undici` (el `fetch` nativo de Node 22) + `zod`**. Sin Express ni Fastify: son cuatro rutas y el manejo de SSE a mano es más claro. Zod valida el cuerpo y los eventos que llegan del servicio de IA, en línea con "Pydantic en los bordes". La configuración se valida con Zod al arrancar.
- **Cancelación y timeout en el gateway**: un `AbortController` por pedido, que se aborta con `req.on("close")` y con `AbortSignal.timeout(GATEWAY_UPSTREAM_TIMEOUT_SECONDS)`. El abort corta el `fetch` y el servicio de IA lo detecta como desconexión.
- **Heartbeats**: comentario SSE `: ping` cada `GATEWAY_HEARTBEAT_SECONDS` (por defecto 15) mientras no haya eventos; se limpia el intervalo al cerrar.
- **CORS**: lista explícita en `GATEWAY_CORS_ORIGINS`; sin comodín por defecto. Responde el preflight `OPTIONS`.
- **Contenedores**: `services/ai` con imagen `python:3.12-slim` multi-stage y `uv sync --frozen --no-dev`, más `tesseract-ocr` y `tesseract-ocr-spa` para la ingesta; `services/gateway` con `node:22-slim` multi-stage, `npm ci --omit=dev` y usuario no root. En compose, `ai` depende de `qdrant` sano y `gateway` de `ai` sano; ambos healthchecks pegan a los endpoints de salud.

## Risks / Trade-offs

- Los jobs en memoria se pierden al reiniciar y no escalan a varias réplicas. Es aceptable para el POC y queda en preguntas abiertas.
- Detectar la desconexión en Starlette depende del servidor ASGI; se cubre con un test de integración con `uvicorn` real además del test con el cliente en proceso.
- Correr el pipeline de ingesta en el mismo proceso compite por CPU con las consultas. La mitigación es el semáforo de concurrencia 1 y, si la prueba de carga lo muestra, mover la ingesta a un worker aparte en otra change.
- `POST` con SSE impide usar `EventSource` nativo en el navegador; el cliente tiene que leer el stream con `fetch`. Queda en preguntas abiertas.
