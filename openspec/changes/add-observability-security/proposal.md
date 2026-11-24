# Proposal

## Why

Un asistente que lee documentos internos y llama herramientas no es demostrable si no se ve qué hace ni se prueba qué no debe hacer. Hoy no hay métricas, ni trazas, ni control de acceso por documento, y nada impide que un texto ingestado le dé órdenes al modelo. Esta change agrega la observabilidad que permite mostrar latencia, costo y errores con números, y los controles de seguridad que el README va a afirmar respaldados por pruebas: secretos, PII, ACL e inyección de prompts.

## What Changes

- Logs JSON estructurados con un `request_id` que se propaga del gateway al servicio de IA y aparece en cada línea.
- Métricas por endpoint (tasa de requests, tasa de errores, latencia p50 y p95), de LLM (tokens y costo estimado), de recuperación (latencia) y de abstención del RAG.
- Trazas distribuidas gateway → ai → LLM y vector store.
- Prometheus, Grafana (con un dashboard y una regla de alerta provisionados como código) y un servidor MLflow agregados a `deploy/compose.yaml`, más un script que dispara la alerta a propósito.
- Las corridas de evaluación quedan como experimentos en MLflow, con parámetros, métricas y artefactos.
- Escaneo de secretos en CI y en pre-commit, con una prueba que demuestra que falla ante un secreto falso plantado.
- Redacción de PII (emails, teléfonos, DNI, CUIT y tarjetas) en logs y, si se configura, antes de enviar texto al LLM, con precisión y recall medidos sobre un set ficticio.
- ACL a nivel de documento: cada request lleva una identidad con grupos, y la recuperación filtra por `acl_groups`, también cuando la usa el agente.
- Suite de inyección de prompts con documentos ficticios maliciosos, encuadre delimitado del contenido recuperado y reporte de la tasa de éxito de los ataques.
- Auditoría de dependencias de Python y Node en CI.

## Capabilities

### New Capabilities
- `observability`: logs estructurados correlacionados, métricas, trazas, dashboard y alerta provisionados como código, y seguimiento de experimentos de evaluación.
- `security-controls`: detección de secretos, redacción de PII medida, control de acceso por documento, resistencia medida a la inyección de prompts y auditoría de dependencias.

### Modified Capabilities

## Impact

- Código nuevo: `services/ai/src/ai_doc_assistant/observability/` y `services/ai/src/ai_doc_assistant/security/`, middleware equivalente en `services/gateway/src/`.
- Toca el código de `add-api-and-gateway` (middleware, identidad en `/ingest` y `/query`), de `add-rag-core` (filtro de ACL, encuadre del contexto, registro en MLflow) y de `add-agent` (identidad propagada a las herramientas). Esta change va después de esas tres.
- Dependencias nuevas: SDKs de OpenTelemetry para Python y Node, `prometheus-client`, `prom-client`, `mlflow`, `pip-audit` y gitleaks (binario en CI y hook de pre-commit). Detalle en el design.
- Infraestructura: servicios `prometheus`, `grafana`, `mlflow` y un colector OTel con visor de trazas en compose; configuración en `deploy/observability/`.
- Datos de prueba nuevos y ficticios: `evals/security/pii/`, `evals/security/injection/` y un corpus con ACL.
- Variables de entorno nuevas: `OTEL_EXPORTER_OTLP_ENDPOINT`, `PII_REDACTION_MODE`, `AUTH_MODE` y el archivo de mapeo de identidades, más la tabla de precios por modelo para el costo estimado. Se documentan en `.env.example`.

## Preguntas abiertas

1. ¿Cómo se identifica al usuario? Propuesta: un mapeo de API key a grupos en un archivo de configuración (simple y suficiente para la demo), con JWT firmado como extensión documentada.
2. ¿La redacción de PII antes del LLM queda activa por defecto? Redactar cambia el contexto y puede bajar la calidad del RAG. Propuesta: activa en logs siempre y opcional hacia el LLM, con la eval corrida en ambos modos.
3. ¿Qué umbrales de alerta y de PII usamos? Propuesta: alerta si p95 de `/query` > 5 s o tasa de errores > 5% durante 5 minutos; precisión ≥ 0,95 y recall ≥ 0,90 por tipo de PII.
4. ¿Qué tasa de éxito aceptamos para los ataques de inyección que no ejecutan herramientas (por ejemplo, que el modelo repita la instrucción inyectada)? Propuesta: 0 para ejecución de herramientas y ≤ 10% para el resto, como gate de CI.
5. ¿Las trazas van a Jaeger, a Grafana Tempo o solo a un colector con salida a consola? Propuesta: Jaeger all-in-one, por ser un único contenedor.
6. ¿La auditoría de dependencias bloquea la CI con cualquier vulnerabilidad o solo con severidad alta o crítica?
7. ¿El escaneo de secretos se demuestra con una rama de prueba que la CI rechaza, o con un test que corre gitleaks sobre un fixture temporal? Lo segundo es reproducible sin ensuciar el historial.
