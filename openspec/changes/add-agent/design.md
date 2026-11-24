# Design

## Context

El agente reutiliza piezas de changes anteriores: el `LLMClient` (`add-llm-client`), que no hace tool calling nativo; el `VectorStore` con filtros (`add-vector-index`); y la generación con citas `[doc_id, página]` y abstención de `add-rag-core`. Los endpoints se montan en la app FastAPI de `add-api-and-gateway`. Todo corre async.

## Goals / Non-Goals

**Goals:**
- Un agente acotado y predecible: ninguna corrida supera sus límites y ninguna acción con efectos ocurre sin aprobación.
- Tests 100% offline con un LLM falso que emite decisiones guionadas.
- Trayectorias evaluables con métricas reproducibles.

**Non-Goals:**
- Multiagente, planificación jerárquica o memoria entre hilos.
- Integración con un sistema de tickets real.
- Control de acceso por usuario sobre las herramientas (`add-observability-security`).
- Streaming de pasos por SSE (pregunta abierta 5).

## Decisions

- **Grafo propio con LangGraph** (`StateGraph`), no el agente prearmado, para controlar límites y aprobación en nodos explícitos: `agent` (decide), `guard` (límites y bucles), `approval` (solo para herramientas con efectos), `tools` (ejecuta) y `finalize` (respuesta con citas o parcial). La API concreta (`interrupt`, `Command(resume=...)`, firmas del checkpointer) se confirma con `docs-checker` en la versión de `uv.lock`.
- **Decisiones del modelo por *structured output***: el nodo `agent` pide al `LLMClient` un JSON validado con Pydantic, que es `ToolCall(name, args)` o `FinalAnswer(text, citations)`. Un JSON inválido cuenta como paso y se reintenta una vez con el error de validación; si vuelve a fallar, la corrida termina con `failed`. Depende de la pregunta abierta 4 de `add-llm-client`.
- **Herramientas como funciones async tipadas** con argumentos Pydantic y una marca `side_effect: bool`. Un error de una herramienta (argumentos inválidos, página fuera de rango, documento inexistente) se devuelve al agente como observación tipada, no como excepción.
- **Aprobación con `interrupt`**: el nodo `approval` pausa con el payload `{tool, args, tool_call_id}`. Al reanudar recibe `{decision: approve | reject | edit, args?}`. Como LangGraph reejecuta el nodo interrumpido desde el principio al reanudar, el efecto vive en el nodo `tools`, nunca antes del `interrupt`. El destino falso deduplica por `run_id + tool_call_id`, así que una reanudación repetida no duplica tickets.
- **Checkpointer**: `AsyncSqliteSaver` en `AGENT_CHECKPOINT_PATH` para la app y `InMemorySaver` en los tests. `thread_id = run_id`.
- **Límites en el estado del grafo**: contadores de pasos, llamadas, tokens (sumando el `usage` de cada `LLMResponse`, incluidas las de `summarize_document` y `compare_documents`) y tiempo activo. El tiempo de espera de aprobación no cuenta. El `recursion_limit` de LangGraph se fija por encima de `AGENT_MAX_STEPS` como red de seguridad. El tiempo se controla con un reloj inyectable, para testearlo sin esperar.
- **Bucles**: se calcula un hash de `(tool, args canónicos en JSON ordenado)`. La segunda llamada idéntica no se reejecuta: devuelve la observación anterior con una advertencia. La tercera detiene la corrida con `loop_detected`.
- **Citas**: `finalize` valida que cada cita pertenezca al conjunto de fuentes observadas en la corrida, descarta las que no y, si no queda ninguna, convierte la respuesta en abstención.
- **API**: `POST /agent/runs` lanza la corrida en una tarea de fondo y responde 202. `GET` lee el estado desde el checkpointer. `POST .../approval` reanuda en segundo plano. Estados: `running`, `awaiting_approval`, `completed`, `stopped` (con `stop_reason`) y `failed`.
- **Evaluación de trayectorias**: cada caso de `cases.jsonl` tiene `id`, `question`, `expected_tools`, `match` (`exact`, `subsequence` o `set`), `forbidden_tools`, `expected` (doc_ids citados, abstención, `stop_reason`), `approval_expected` y `human_decision`. Las métricas se definen así:
  - Éxito de tarea: el caso cumple todas sus propiedades finales.
  - Coincidencia de trayectoria: según el modo del caso, en exacta y en subsecuencia.
  - Precisión de herramientas: llamadas a herramientas esperadas sobre llamadas totales.
  - Pasos por tarea: media y p95.
  - Aprobación correcta: casos donde se pidió aprobación si y solo si se esperaba, sobre N.
  
  Hay dos modos: `--llm fake` (decisiones guionadas por caso, determinista, va a CI y valida el arnés) y `--llm real` (mide al modelo y se registra en `RESULTS.md`).

## Risks / Trade-offs

- La API de LangGraph cambia seguido (`interrupt`, checkpointers). Para mitigarlo, se fija la versión y se usa `docs-checker` antes de cada nodo.
- Si el proceso se reinicia, una corrida en estado `running` (no pausada) se pierde. Se marca `failed` al consultarla y no se reanuda sola. Las pausadas sí sobreviven.
- Con 15 a 20 casos, cada caso pesa entre un 5% y un 7% de la métrica. Sirve para detectar regresiones gruesas, no diferencias finas entre modelos.
- La salida del modo `fake` mide el arnés, no la calidad del modelo. Hay que decirlo explícitamente en el README.
