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
- **Uso**: cada llamada devuelve `LLMResponse(text, usage, latency_ms, provider, model)` y emite un log estructurado sin el prompt.

## Risks / Trade-offs

- Los SDKs cambian de API seguido. Para mitigarlo, se fijan las versiones en `uv.lock` y se usa `docs-checker` antes de cada adaptador.
- El streaming con reintentos es ambiguo, porque no se puede reintentar después de haber emitido tokens. Por eso se reintenta solo si el error ocurre antes del primer token.
