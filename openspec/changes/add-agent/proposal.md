# Proposal

## Why

El RAG responde una pregunta por vez. Hay tareas que piden varios pasos (buscar, leer una página puntual, comparar dos documentos y, al final, abrir un ticket) y ahí un agente con herramientas aporta valor. Pero un agente sin límites ni control es caro, impredecible y peligroso cuando una herramienta tiene efectos. Para el portfolio, lo que hay que mostrar es un agente acotado: con presupuesto, que se detiene solo, que pide aprobación humana antes de cualquier efecto y cuya trayectoria se evalúa con números.

## What Changes

- Agente de documentos con herramientas de solo lectura: buscar en el índice, leer una página de un documento, resumir un documento y comparar dos documentos.
- Una herramienta con efectos (`create_ticket`) que escribe en un destino falso y que nunca se ejecuta sin aprobación humana explícita: la corrida se pausa, la persona aprueba, rechaza o edita los argumentos, y la corrida se reanuda.
- Estado persistido por hilo, para que una aprobación pueda llegar después de que terminó la request que inició la corrida.
- Límites por corrida: pasos, llamadas a herramientas, tokens, tiempo y detección de bucles. Al tocar un límite, el agente se detiene con una respuesta parcial y el motivo.
- Toda respuesta final con contenido cita sus fuentes `[doc_id, página]`, tomadas solo de lo que el agente observó en la corrida.
- Endpoints livianos: `POST /agent/runs`, `GET /agent/runs/{run_id}` y `POST /agent/runs/{run_id}/approval`.
- Evaluación de trayectorias: `evals/agent/cases.jsonl` con 15 a 20 casos ficticios y un script que mide éxito de tarea, coincidencia de trayectoria, precisión de llamadas a herramientas, pasos por tarea y aprobación pedida correctamente.

## Capabilities

### New Capabilities
- `document-agent`: agente con herramientas sobre los documentos indexados, con límites de ejecución, aprobación humana para acciones con efectos, estado persistido por hilo, respuestas con citas y evaluación de trayectorias.

### Modified Capabilities

## Impact

- Código nuevo: `services/ai/src/ai_doc_assistant/agent/` (grafo, herramientas, límites, destino falso de tickets) y `services/ai/src/ai_doc_assistant/api/agent.py`.
- Evaluación: `evals/agent/cases.jsonl`, `evals/run_agent_eval.py` y salidas en `evals/runs/agent/`. Las métricas nuevas van a `evals/RESULTS.md` en una tabla propia.
- Dependencias: `langgraph` y un checkpointer persistente (`langgraph-checkpoint-sqlite`, ver design).
- Variables de entorno: `AGENT_MAX_STEPS`, `AGENT_MAX_TOOL_CALLS`, `AGENT_MAX_TOKENS`, `AGENT_MAX_SECONDS`, `AGENT_CHECKPOINT_PATH` (hay que agregarlas a `.env.example`).
- Depende de `add-llm-client` (completado y *structured output*), `add-vector-index` (búsqueda con filtros), `add-rag-core` (citas y abstención) y `add-api-and-gateway` (montaje de los endpoints y convenciones de errores).

## Preguntas abiertas

1. ¿Confirmamos los límites propuestos: 8 pasos, 12 llamadas a herramientas, 20 mil tokens y 60 segundos por corrida (sin contar la espera de aprobación)?
2. ¿Cuál es la acción con efectos: `create_ticket` o `send_report`? ¿Alcanza con una sola para el POC? Propuesta: solo `create_ticket` hacia un destino falso (archivo JSONL local).
3. ¿Las aprobaciones pendientes vencen? Propuesta: sin vencimiento en el POC y documentarlo como deuda; alternativa, 24 horas y estado `expired`.
4. ¿Checkpointer en SQLite (archivo local, alcanza para compose) o en Postgres (más realista para k8s, pero suma un servicio)?
5. ¿El progreso de la corrida se transmite por SSE a través del gateway en esta change o alcanza con consultar el estado (*polling*)? Propuesta: *polling* ahora y SSE como extensión.
6. ¿La evaluación de trayectorias con un LLM real entra en el gate de CI o corre solo a mano y se registra en `RESULTS.md`? Propuesta: en CI solo el modo determinista con el LLM falso.
7. ¿Qué umbrales de aceptación usamos? Propuesta: éxito de tarea de 0,80 o más, coincidencia de trayectoria por subsecuencia de 0,80 o más, precisión de herramientas de 0,85 o más, aprobación correcta de 1,00 y una media de 5 pasos o menos.
