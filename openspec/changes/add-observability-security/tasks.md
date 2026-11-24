# Tasks

## 1. Contrato y configuración

- [ ] 1.1 Usar `docs-checker` para confirmar las APIs de `structlog`, `pino`, `prometheus-client`, `prom-client`, los SDKs de OpenTelemetry de Python y Node, `mlflow`, el provisioning de Grafana y la configuración de gitleaks en las versiones fijadas
- [ ] 1.2 Definir `ObservabilitySettings` y `SecuritySettings` (`PII_REDACTION_MODE`, `AUTH_MODE`, ruta del mapeo de identidades, `FAULT_INJECTION`) y documentarlas en `.env.example`
- [ ] 1.3 Definir `Principal`, el Protocol `PiiRedactor`, el esquema de `config/principals.yaml` y la tabla de precios por modelo
- [ ] 1.4 Armar los datos ficticios: set de PII anotado en `evals/security/pii/`, corpus con ACL de 3 grupos y suite de inyección en `evals/security/injection/`

## 2. Tests primero

- [ ] 2.1 Usar `test-writer` para escribir los tests de `observability`: `request_id` propagado, métricas con un cliente de prueba, cardinalidad, costo con la tabla de prueba, ausencia de contenido en los spans (exportador en memoria) y MLflow caído
- [ ] 2.2 Usar `test-writer` para escribir los tests de `security-controls`: detectores de PII (incluidos los negativos por dígito verificador y Luhn), redacción en logs y hacia el LLM, 401 sin credencial, header de identidad falsificado, ACL en RAG y en el agente, delimitadores y aprobación ante inyección, gitleaks sobre un repo temporal
- [ ] 2.3 Confirmar que los tests fallan por la razón correcta

## 3. Implementación de observabilidad

- [ ] 3.1 Logs JSON con `request_id` y `trace_id` en ambos servicios, con el procesador de redacción
- [ ] 3.2 Métricas y endpoint `/metrics` en el gateway y en el servicio de IA
- [ ] 3.3 Trazas OTel con spans manuales alrededor de los Protocols de LLM y vector store
- [ ] 3.4 Servicios `prometheus`, `grafana`, `otel-collector`, `jaeger` y `mlflow` en compose, con el dashboard y la regla de alerta en `deploy/observability/`
- [ ] 3.5 Endpoint de fallas detrás de `FAULT_INJECTION` y `scripts/trigger_alert.sh`
- [ ] 3.6 Contrato de registro en MLflow para `rag-eval` y `security-eval`, con degradación si el servidor no responde

## 4. Implementación de seguridad

- [ ] 4.1 Redactor de PII y `evals/security/run_pii_eval.py` con reporte en `evals/security/results/`
- [ ] 4.2 Resolución de identidad en el gateway, header interno hacia el servicio de IA y 401 en `/ingest` y `/query`
- [ ] 4.3 Filtro de ACL dentro del retriever, cerrado por defecto, y propagación del `Principal` a las herramientas del agente
- [ ] 4.4 Delimitadores con nonce e instrucciones de sistema en la construcción del prompt
- [ ] 4.5 Script de la suite de inyección con detectores por caso y registro en `security-eval`
- [ ] 4.6 `.gitleaks.toml`, hook de pre-commit y job de CI con historial completo
- [ ] 4.7 Jobs de CI con `pip-audit` y `npm audit`, y archivo de excepciones con vencimiento

## 5. Cierre

- [ ] 5.1 Correr `/verify` en verde
- [ ] 5.2 Levantar el entorno con `make up`, correr `scripts/trigger_alert.sh` y guardar la captura del dashboard con la alerta disparada
- [ ] 5.3 Correr las suites de PII, ACL e inyección (esta última también con `-m integration` contra un proveedor real) y anotar los números en `evals/RESULTS.md` con su corrida de MLflow
- [ ] 5.4 Pasar `reviewer` sobre el diff y resolver los hallazgos
- [ ] 5.5 Agregar al README las secciones de observabilidad y de seguridad, con el modelo de amenazas cubierto y lo que queda afuera
