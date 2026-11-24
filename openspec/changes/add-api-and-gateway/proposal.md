# Proposal

## Why

El RAG de `add-rag-core` es una librería: hasta que no tenga una API no se puede usar desde una interfaz, medir bajo carga ni desplegar. El POC necesita endpoints tipados para ingestar y consultar, y un gateway que entregue la respuesta token a token por SSE al navegador, con cancelación y errores predecibles. Es también la pieza que muestra el stack mixto Python y Node del perfil buscado.

## What Changes

- API FastAPI en `services/ai` con tres grupos de endpoints:
  - `POST /ingest`: recibe uno o más archivos, valida tamaño y tipo, y devuelve un job id. `GET /ingest/{job_id}` informa el estado y el resultado por documento.
  - `POST /query`: recibe `{question, filters, top_k}` y responde en streaming (tokens, después citas `[doc_id, page]` y uso) o, si se pide, en una sola respuesta JSON.
  - `GET /health/live` y `GET /health/ready`: vida del proceso y disponibilidad del vector store y de la configuración del LLM.
- Errores tipados con un formato único, request id propagado de punta a punta y timeouts explícitos.
- Gateway Node/TypeScript en `services/gateway` que expone `POST /api/query` como Server-Sent Events con los eventos `token`, `citations`, `error` y `done`, heartbeats, cancelación hacia arriba cuando el cliente se desconecta, CORS configurable y validación de la entrada.
- Dockerfiles para ambos servicios y los servicios `ai` y `gateway` en `deploy/compose.yaml`, con healthchecks.
- Una prueba de carga corta con el LLM `fake` para fijar una cota de latencia p95.

**Fuera de alcance:** autenticación, autorización y ACL por documento (llegan en `add-observability-security`), rate limiting por usuario y una interfaz web.

## Capabilities

### New Capabilities
- `query-api`: API HTTP del servicio de IA para ingestar documentos de forma asíncrona, consultar el RAG en streaming o completo y exponer el estado de salud, con errores tipados, request id y timeouts.
- `sse-gateway`: gateway que traduce el streaming del servicio de IA a Server-Sent Events para clientes web, con heartbeats, cancelación, timeout, CORS y validación.

### Modified Capabilities

## Impact

- Código nuevo: `services/ai/src/ai_doc_assistant/api/` y `services/gateway/src/` (reemplaza el placeholder actual).
- Dependencias de Python: `fastapi`, `uvicorn`, `python-multipart` y `sse-starlette` o una implementación propia (ver design); `httpx` para los tests.
- Dependencias de Node: `zod` y un framework HTTP liviano o `node:http` (ver design).
- Infraestructura: `services/ai/Dockerfile`, `services/gateway/Dockerfile` y los servicios `ai` y `gateway` en `deploy/compose.yaml`, que dependen de `qdrant` sano.
- Variables de entorno nuevas en `.env.example`: `API_MAX_UPLOAD_MB`, `API_MAX_FILES`, `API_QUERY_TIMEOUT_SECONDS`, `GATEWAY_PORT`, `GATEWAY_AI_URL`, `GATEWAY_CORS_ORIGINS`, `GATEWAY_UPSTREAM_TIMEOUT_SECONDS` y `GATEWAY_HEARTBEAT_SECONDS`.
- Depende de `add-rag-core` (respuesta con citas, abstención y streaming), de `add-ingest-pipeline` y de `add-vector-index`.

## Preguntas abiertas

1. ¿Los jobs de ingesta se guardan en memoria (se pierden al reiniciar, alcanza para el POC) o en un almacén persistente como SQLite o Redis?
2. ¿Qué límites de subida usamos? Propuesta: 20 MB por archivo, 10 archivos por pedido y solo PDF, PNG, JPEG y TIFF.
3. ¿Qué cota de p95 aceptamos en la prueba de carga? Propuesta: 50 consultas concurrentes con el LLM `fake` y p95 hasta el último evento de 500 ms o menos en local.
4. ¿El gateway expone también `/api/ingest` (proxy de la subida) o la ingesta queda solo en el servicio de IA para el POC?
5. ¿El gateway usa `POST` con cuerpo JSON (más simple para filtros) o `GET` con query string para poder usar `EventSource` nativo en el navegador?
6. ¿Se agrega un endpoint de borrado de documentos (`DELETE /documents/{doc_id}`) en esta change o en `add-observability-security`, junto con las ACL?
