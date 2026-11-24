# Design

## Context

No hay código previo. Los consumidores son el RAG (`add-rag-core`), el agente (`add-agent`) y la evaluación con un LLM como juez. Todos corren dentro de FastAPI con async.

## Goals / Non-Goals

**Goals:**
- Una interfaz async única. Agregar un proveedor tiene que ser un archivo nuevo, sin tocar a los consumidores.
- Tests 100% offline con el proveedor `fake`.
- Fallos predecibles: timeout acotado, reintentos acotados y errores tipados.

**Non-Goals:**
- Caché de respuestas, enrutamiento entre modelos y control de costos por usuario.
- Tool calling nativo: lo resuelve el agente sobre esta interfaz.

## Decisions

- **`typing.Protocol`** (`LLMClient`) en vez de una clase base abstracta, para que los fakes no hereden nada. Se implementa con métodos `async`, y el streaming es un `AsyncIterator[str]`.
- **Fábrica `build_llm_client(settings)`** que lee `LLMSettings` (pydantic-settings). Un proveedor desconocido o una clave faltante hacen fallar el arranque, no la primera llamada.
- **Reintentos**: solo para timeout, 429 y 5xx. Nunca para 4xx de validación o autenticación. Se usa backoff exponencial con jitter (base de 0,5 s y tope de 8 s) y `LLM_MAX_RETRIES` intentos. Si el proveedor envía `Retry-After`, se respeta.
- **Timeouts**: se pasan al cliente HTTP del SDK y además se envuelven con `asyncio.timeout` como red de seguridad.
- **Errores**: `LLMError` es la base, con `LLMTimeoutError`, `LLMRateLimitError`, `LLMProviderError` y `LLMConfigError`. Las excepciones de los SDKs nunca salen del módulo.
- **Modelo por defecto**: `claude-haiku-5-5`. Es el más barato de la familia actual, del orden de centavos por corrida de evaluación. Como es configurable, se puede comparar contra modelos más grandes en `evals/RESULTS.md`.
- **Salida estructurada**: `complete_structured(prompt, schema: type[BaseModel]) -> BaseModel`. En Anthropic se usa el formato de salida del SDK (confirmar la firma con `docs-checker`). Si la respuesta no valida contra el esquema, se reintenta una vez con el error de validación como contexto.
- **Embeddings como interfaz aparte**: Protocol `Embedder` con `model_id`, `dimension`, `embed_queries(texts)` y `embed_passages(texts)`. La familia e5 se entrenó con los prefijos `"query: "` y `"passage: "`. Si se omiten, cae la calidad de recuperación, y por eso la interfaz obliga a declarar el rol. El adaptador local usa `sentence-transformers` en CPU, con los vectores normalizados (norma 1), así que la similitud coseno es igual al producto interno.
- **Ejecución del modelo local**: `encode` es síncrono y usa CPU intensivamente. Desde código async se llama con `asyncio.to_thread`, nunca directo dentro del event loop.
- **Uso**: cada llamada devuelve `LLMResponse(text, usage, latency_ms, provider, model)` y emite un log estructurado sin el prompt.

## Risks / Trade-offs

- Usar el mismo modelo como generador y como juez genera un sesgo de autopreferencia. La mitigación se define en `add-rag-core`.
- `sentence-transformers` trae PyTorch, que agranda la imagen Docker. Se instala la versión de PyTorch para CPU y el modelo se cachea en la imagen o en un volumen.
- Los SDKs cambian de API seguido. Para mitigarlo, se fijan las versiones en `uv.lock` y se usa `docs-checker` antes de cada adaptador.
- El streaming con reintentos es ambiguo, porque no se puede reintentar después de haber emitido tokens. Por eso se reintenta solo si el error ocurre antes del primer token.
