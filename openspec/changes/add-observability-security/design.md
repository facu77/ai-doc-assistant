# Design

## Context

Ya existen `/ingest`, `/query` (SSE) y `/health` (`add-api-and-gateway`), el RAG con citas y abstención (`add-rag-core`) y el agente con una herramienta que requiere aprobación (`add-agent`). Los chunks llevan `acl_groups` y la búsqueda acepta filtros (`add-vector-index`). El cliente LLM ya devuelve `usage` y `latency_ms`. El hook `guard_secrets.py` protege solo las escrituras del agente de código, no el repo.

## Goals / Non-Goals

**Goals:**
- Seguir un request de punta a punta por su `request_id` en logs, métricas y trazas.
- Que todo se levante con `make up`, sin pasos manuales en Grafana.
- Que cada control de seguridad tenga una prueba automatizada con un número reportado.

**Non-Goals:**
- Login, gestión de usuarios o rotación de claves.
- Enviar alertas a canales externos: alcanza con verlas disparadas en Grafana.
- PII no estructurada (nombres, direcciones) con modelos de NER.

## Decisions

- **Logs**: `structlog` (JSON) en Python y `pino` en el gateway. El gateway acepta un `X-Request-ID` UUID o genera uno y lo reenvía. Todo valor pasa por el redactor de PII antes de emitirse.
- **Métricas**: `prometheus-client` y `prom-client` en `/metrics`. Etiquetas `route` (la plantilla, nunca la URL cruda), `method` y `status`. Los tokens y el costo van por modelo. El costo sale de una tabla de precios en YAML y en el dashboard figura como estimado.
- **Trazas**: OpenTelemetry con autoinstrumentación de FastAPI, `httpx` y `http` de Node, y propagación W3C. Los spans `llm.*` y `vector.search` se agregan con decoradores alrededor de los Protocols, así ningún adaptador depende de OTel. Se exporta por OTLP a un colector y de ahí a Jaeger (pregunta abierta 5).
- **Compose**: `prometheus`, `grafana`, `otel-collector`, `jaeger` y `mlflow` (con SQLite y un volumen para los artefactos) en un perfil `observability`. El datasource, el dashboard JSON y la regla de alerta se provisionan desde `deploy/observability/grafana/`.
- **Alerta disparable**: `scripts/trigger_alert.sh` usa un endpoint de fallas que solo existe con `FAULT_INJECTION=true`, genera errores hasta pasar el umbral y consulta la API de Grafana hasta ver la alerta en `firing`, o hasta que vence el timeout.
- **MLflow**: los experimentos `rag-eval` (registrados por `add-rag-core`) y `security-eval` llevan como parámetros la configuración y el commit, y como artefactos `metrics.json` y la tabla Markdown.
- **Secretos**: `.gitleaks.toml` extiende las reglas por defecto con las de `guard_secrets.py`. Corre en CI con `fetch-depth: 0` y en `pre-commit`. Para probarlo, un test crea un repo temporal y commitea un secreto falso generado en el momento, así nunca queda guardado en el repo.
- **PII**: regex con validación: módulo 11 para CUIT/CUIL, Luhn para tarjetas, formato con puntos o contexto para DNI y formatos argentinos de teléfono. Cada valor se reemplaza por un marcador tipado (`[EMAIL]`, `[CUIT]`, …). `PII_REDACTION_MODE` acepta `logs` (por defecto) o `logs_and_llm`.
- **Identidad y ACL**: el gateway resuelve `X-API-Key` a un `Principal(user_id, groups)` con `config/principals.yaml` (claves guardadas como hash). Lo reenvía en un header interno, y el gateway descarta cualquier valor de ese header que llegue desde afuera. El filtro por `acl_groups` se aplica dentro del retriever, no en cada endpoint, para que el agente lo herede. Si un documento no tiene grupos, no lo ve nadie.
- **Inyección**: el contexto va entre delimitadores `<document id=… nonce=…>` con un nonce por request, y el prompt de sistema lo declara como dato. Lo que realmente cierra el ataque es estructural: la herramienta con efectos siempre se detiene en el nodo de aprobación de LangGraph. La suite detecta un ataque exitoso con un canario en la salida, con una llamada a herramienta registrada o con citas de documentos no recuperados.
- **Dependencias**: `pip-audit` sobre lo exportado por `uv` y `npm audit --audit-level=high`, en jobs separados de `verify`. Las excepciones se justifican y llevan fecha de vencimiento en un archivo.

## Risks / Trade-offs

- Las regex de PII dan falsos positivos (números de expediente que parecen DNI). Por eso se mide la precisión y no solo el recall.
- La suite de inyección con el proveedor `fake` solo prueba lo estructural: aprobación, ACL y delimitadores. La tasa contra el modelo real se mide a mano con `-m integration` y se registra en MLflow.
- El nonce no impide que el modelo obedezca un texto. La garantía la dan la aprobación y el ACL, no el prompt.
- Cinco contenedores más hacen más pesado `make up`. Por eso van en un perfil que se puede apagar.
