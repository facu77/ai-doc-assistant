# Tasks

## 1. Contrato y configuración

- [ ] 1.1 Usar `docs-checker` para confirmar las APIs de `fastapi` (`StreamingResponse`, `UploadFile`, `exception_handler`), `python-multipart`, `uvicorn`, `zod` y el `fetch` y `AbortSignal` de Node 22 en las versiones instaladas
- [ ] 1.2 Definir los modelos Pydantic `QueryRequest`, `QueryResponse`, `ErrorBody`, `IngestJob` y los eventos `TokenEvent`, `CitationsEvent`, `ErrorEvent` y `DoneEvent`, más `ApiSettings`
- [ ] 1.3 Definir los esquemas Zod equivalentes y `GatewayConfig` en `services/gateway/src/contract.ts`, con un test que compare un evento de ejemplo serializado por Pydantic con su parseo en Zod
- [ ] 1.4 Definir el Protocol `JobStore` y documentar las variables nuevas en `.env.example`

## 2. Tests primero

- [ ] 2.1 Usar `test-writer` para escribir los tests de `query-api` con `httpx.AsyncClient`, el LLM `fake` programable (latencia, cuelgue, falla tras N tokens) y un vector store en memoria
- [ ] 2.2 Usar `test-writer` para escribir los tests de `sse-gateway` en Vitest contra un servicio de IA simulado con `node:http` (eventos programables, silencio, corte, 422, conexión rechazada)
- [ ] 2.3 Escribir la prueba de carga (`-m load`) de 50 consultas concurrentes y el test de desconexión con `uvicorn` real
- [ ] 2.4 Confirmar que los tests fallan por la razón correcta

## 3. Implementación

- [ ] 3.1 Middleware ASGI de request id y manejadores de errores tipados
- [ ] 3.2 `GET /health/live` y `GET /health/ready`
- [ ] 3.3 `POST /query` en streaming y sin streaming sobre el RAG de `add-rag-core`, con timeout y cancelación
- [ ] 3.4 `POST /ingest` con validación de tamaño y *magic bytes*, `JobStore` en memoria, ejecución con `asyncio.to_thread` y `GET /ingest/{job_id}`
- [ ] 3.5 Gateway: configuración, validación de entrada, proxy SSE, heartbeats, cancelación, timeout, CORS y `/healthz`
- [ ] 3.6 Dockerfiles multi-stage de `services/ai` y `services/gateway` con usuario no root
- [ ] 3.7 Servicios `ai` y `gateway` en `deploy/compose.yaml` con healthchecks y `depends_on: condition: service_healthy`

## 4. Cierre

- [ ] 4.1 Correr `/verify` en verde y la prueba de carga, con el p95 medido registrado en `evals/RESULTS.md`
- [ ] 4.2 Prueba de humo con `make up`: ingestar un PDF del corpus y consultar con `curl -N` a través del gateway
- [ ] 4.3 Pasar `reviewer` sobre el diff y resolver los hallazgos
- [ ] 4.4 Documentar los endpoints, el contrato de eventos y los ejemplos de `curl` en los README de `services/ai` y `services/gateway`, aclarando que no hay autenticación hasta `add-observability-security`
