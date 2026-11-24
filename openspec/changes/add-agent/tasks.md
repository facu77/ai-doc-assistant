# Tasks

## 1. Contrato

- [ ] 1.1 Usar `docs-checker` para confirmar en la versión instalada de `langgraph` las firmas de `StateGraph`, `interrupt`, `Command(resume=...)`, `recursion_limit` y de los checkpointers `InMemorySaver` y `AsyncSqliteSaver`, incluida la semántica de reejecución del nodo al reanudar
- [ ] 1.2 Definir `AgentSettings` (límites y `AGENT_CHECKPOINT_PATH`), los modelos `ToolCall`, `FinalAnswer`, `ApprovalDecision`, `RunStatus` y `TrajectoryStep`, y los esquemas de argumentos de cada herramienta
- [ ] 1.3 Definir el Protocol del destino de tickets y el destino falso con deduplicación por `run_id + tool_call_id`
- [ ] 1.4 Definir el formato de `evals/agent/cases.jsonl` y agregar las variables `AGENT_*` a `.env.example`

## 2. Tests primero

- [ ] 2.1 Usar `test-writer` para escribir los tests de todos los escenarios con un LLM falso que emite decisiones guionadas, un reloj inyectable, `InMemorySaver` y un `VectorStore` en memoria
- [ ] 2.2 Escribir el test de reanudación después de un reinicio con el checkpointer SQLite sobre un archivo temporal
- [ ] 2.3 Confirmar que los tests fallan por la razón correcta

## 3. Implementación

- [ ] 3.1 Herramientas de solo lectura con errores como observación tipada
- [ ] 3.2 Grafo: nodos `agent`, `guard`, `approval`, `tools` y `finalize`
- [ ] 3.3 Límites (pasos, llamadas, tokens, tiempo activo) y detección de bucles
- [ ] 3.4 Aprobación con `interrupt` y `create_ticket` hacia el destino falso
- [ ] 3.5 Validación de citas contra las fuentes observadas y abstención
- [ ] 3.6 Endpoints `/agent/runs` montados en la app de `add-api-and-gateway`
- [ ] 3.7 Log estructurado de la trayectoria, con un test que verifica la ausencia de la pregunta y de los documentos
- [ ] 3.8 Escribir los 15 a 20 casos ficticios en `evals/agent/cases.jsonl` y el script `evals/run_agent_eval.py` (modos `fake` y `real`) con su salida en `evals/runs/agent/`

## 4. Cierre

- [ ] 4.1 Correr `/verify` en verde, con la evaluación determinista incluida
- [ ] 4.2 Correr la evaluación con el modelo real y registrar las métricas y la corrida en `evals/RESULTS.md`
- [ ] 4.3 Pasar `reviewer` sobre el diff y resolver los hallazgos
- [ ] 4.4 Agregar la sección `agent` al README de `services/ai`, con los límites, el flujo de aprobación y la aclaración de que el modo `fake` mide el arnés, no el modelo
