# Proposal

## Why

Todo el POC (RAG, agente y la evaluación con un LLM como juez) depende de modelos de lenguaje y de embeddings. Si cada módulo llamara directo al SDK de un proveedor, cambiar de proveedor o testear sin red sería caro. Por eso, antes que cualquier otra cosa, se necesita un cliente único y tipado, con reintentos y timeouts medidos, y un generador de embeddings determinista.

## What Changes

- Interfaz `LLMClient` con tres operaciones: completar (respuesta completa), streaming (tokens incrementales) y salida estructurada (JSON validado contra un esquema).
- Adaptadores para Anthropic y OpenAI, más un proveedor `fake` determinista para tests y CI. Modelo por defecto: `claude-haiku-5-5`.
- Interfaz `Embedder` **separada** del LLM. Anthropic no ofrece embeddings, así que son dos proveedores distintos. Adaptador local con `intfloat/multilingual-e5-small` (384 dimensiones, multilingüe) y un `fake` determinista.
- Selección del proveedor y del modelo por variables de entorno, validada al arrancar.
- Política de reintentos con backoff exponencial y jitter, solo para errores transitorios, con timeout por llamada y un error tipado cuando se agotan.
- Registro de uso por llamada: tokens, latencia, proveedor y modelo, sin incluir el contenido del prompt.

## Capabilities

### New Capabilities
- `llm-client`: acceso a modelos de lenguaje independiente del proveedor, con configuración, reintentos, timeouts, salida estructurada y registro de uso.
- `embeddings`: conversión de textos a vectores con un modelo identificado y de dimensión fija, determinista y procesada en lotes.

### Modified Capabilities

## Impact

- Código nuevo en `services/ai/src/ai_doc_assistant/llm/` y `services/ai/src/ai_doc_assistant/embeddings/`.
- Dependencias nuevas: `pydantic`, `pydantic-settings`, `httpx`, SDK `anthropic`, SDK `openai` y `sentence-transformers` (con PyTorch en su versión para CPU).
- Variables de entorno: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, las claves de cada proveedor, `EMBEDDINGS_PROVIDER`, `EMBEDDINGS_MODEL` y `EMBEDDINGS_BATCH_SIZE`.
- Hay que descargar el modelo de embeddings (unos cientos de MB) la primera vez. En CI y en Docker se cachea.

## Decisiones tomadas (2026-11-24)

1. **Embeddings**: modelo local `intfloat/multilingual-e5-small` (384 dimensiones). Es gratis, no saca los documentos de la máquina y es determinista en CI sin claves. Queda detrás de `Embedder`, así que se puede comparar después contra una API.
2. **LLM por defecto**: `claude-haiku-5-5`, tanto para generar como para juzgar en la evaluación. Usar el mismo modelo como juez introduce un sesgo de autopreferencia. Se mitiga en `add-rag-core` con una verificación humana sobre una muestra.
3. **Embeddings separados del LLM**: interfaz `Embedder` propia.
4. **Ollama**: queda fuera del POC y se documenta como extensión posible.
5. **Salida estructurada**: entra en esta change porque el agente la necesita.

## Preguntas abiertas

Surgieron al implementar. Cada una tiene una implementación provisoria, que decide el autor.

1. **Cortes de conexión**: la spec nombra timeout, 429 y 5xx como transitorios. Hoy un `APIConnectionError` también se reintenta, porque es un fallo de red y no un rechazo del proveedor. La alternativa es no reintentarlo: es más estricto con la spec, pero un corte breve de red le llegaría al usuario como error. **Recomendación**: mantener el reintento y sumarlo a la spec.
2. **`Retry-After` sin tope**: se respeta el valor completo, aunque sea de 600 s. La alternativa es fallar enseguida con `LLMRateLimitError` si supera un máximo, por ejemplo 30 s: el consumidor responde antes, a cambio de no respetar al proveedor. **Recomendación**: definir el tope cuando exista el endpoint de chat (`add-rag-core`).
3. **Parámetros `system` y `max_tokens`** en `complete`, `stream` y `complete_structured`: no están en la spec. `max_tokens` es obligatorio en Anthropic y el RAG va a necesitar un *system prompt*. Hoy el default es 1024 y no hay variable de entorno. **Recomendación**: dejarlos como parámetros por llamada.
4. **`LLM_PROVIDER` y `EMBEDDINGS_PROVIDER` son obligatorias**: no tienen default. Si faltan, el arranque falla con un error de configuración, aunque `.env.example` sugiere `fake` y `local`. La alternativa es tomar esos valores por defecto: es más cómodo, pero un deploy mal configurado usaría el fake sin avisar.
5. **Salida estructurada con argumentos libres**: `anthropic.transform_schema` convierte `dict[str, object]` en un objeto con `additionalProperties: false` y sin propiedades. Con Anthropic, `argumentos` volvería siempre vacío. Esto afecta a `add-agent`: conviene un esquema por herramienta o `argumentos` como JSON en un string.
6. **`httpx` por `httpx2`**: la propuesta lista `httpx`, pero los SDKs instalados (anthropic 2.14 y openai 3.59) usan `httpx2`. Se declaró `httpx2` y se sacó `httpx`.
