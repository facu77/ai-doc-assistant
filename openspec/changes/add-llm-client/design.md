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
- **Reintentos**: solo para timeout, 429 y 5xx. Nunca para 4xx de validación o autenticación. Se usa backoff exponencial con *full jitter* (base de 0,5 s y tope de 8 s) y `LLM_MAX_RETRIES` intentos totales. Si el proveedor envía `Retry-After`, se espera ese valor más un jitter acotado de hasta 0,5 s, para que los clientes que recibieron el mismo valor no vuelvan todos juntos. **Tope de `Retry-After`: 30 s** (`RetryPolicy.max_retry_after`). Si el proveedor pide más, no se espera: se levanta `LLMRateLimitError` enseguida, con el `retry_after` original.
- **Errores en mitad del stream**: Anthropic puede mandar un evento SSE `error` con HTTP 200. Ahí la clasificación sale de `body["error"]["type"]`: `overloaded_error` y `api_error` son transitorios, y `rate_limit_error` es `LLMRateLimitError`.
- **Timeouts**: se pasan al cliente HTTP del SDK y además se envuelven con `asyncio.timeout` como red de seguridad.
- **Errores**: `LLMError` es la base, con `LLMTimeoutError`, `LLMRateLimitError`, `LLMProviderError`, `LLMConfigError`, `LLMValidationError` (la salida estructurada no validó) y `LLMSchemaError` (el esquema pedido no es cerrado). Las excepciones de los SDKs nunca salen del módulo.
- **Modelo por defecto**: `claude-haiku-5-5`. Es el más barato de la familia actual, del orden de centavos por corrida de evaluación. Como es configurable, se puede comparar contra modelos más grandes en `evals/RESULTS.md`.
- **Salida estructurada**: `complete_structured(prompt, schema: type[T]) -> StructuredResponse[T]`, que trae el valor validado, el uso sumado de todos los intentos, los intentos totales (requests al proveedor), la latencia, el proveedor y el modelo. En Anthropic se usa `output_config.format` con `anthropic.transform_schema`, y en OpenAI `response_format` con `json_schema` y `strict: false`. `strict: true` queda afuera porque depende de una función privada del SDK (`openai.lib._pydantic.to_strict_json_schema`). Si la respuesta no valida contra el esquema, se reintenta una vez con el error de validación como contexto. Al rendirse, se loguea la llamada con `outcome=error` (`LLMValidationError`).
- **Esquemas cerrados** (`llm/schema.py`): un modelo Pydantic por herramienta, y la llamada como unión discriminada por un campo `Literal` con el nombre de la herramienta. `ensure_closed_schema` rechaza con `LLMSchemaError`, antes de llamar al proveedor, cualquier objeto sin propiedades declaradas, los objetos que admiten propiedades libres, los campos `Any`, los arrays sin `items` (una tupla sale como `prefixItems`, que `transform_schema` no soporta) y las raíces que no son objeto. Motivo: `anthropic.transform_schema` convierte `dict[str, object]` en `{"properties": {}, "additionalProperties": false}`, y el modelo no puede llenar nada. `transform_schema` sí soporta uniones: convierte el `oneOf` de Pydantic en `anyOf` y deja el discriminador como texto en la descripción. Como cada variante tiene su `const`, la unión sigue cerrada. Una unión en la raíz sale como `anyOf` sin `type: object`, así que se envuelve en un modelo contenedor (`LlamadaHerramienta(llamada: BuscarDocumentos | ObtenerPagina)`). Hay tests de contrato que llaman al `transform_schema` real y miran el cuerpo que serializa cada SDK.
- **Ciclo de vida**: `LLMClient.aclose()` cierra el cliente HTTP del SDK. Se llama al apagar el servicio.
- **Embeddings como interfaz aparte**: Protocol `Embedder` con `model_id`, `dimension`, `embed_queries(texts)` y `embed_passages(texts)`. La familia e5 se entrenó con los prefijos `"query: "` y `"passage: "`. Si se omiten, cae la calidad de recuperación, y por eso la interfaz obliga a declarar el rol. Los prefijos se deciden por el id del modelo, tanto en `from_pretrained` como en el constructor: si el último segmento empieza con `e5-` o `multilingual-e5-`, se usan `query: ` y `passage: `. Las variantes `-instruct` necesitan un prompt `Instruct: ...` que no está implementado, así que se rechazan con `EmbeddingsConfigError` antes de cargar el modelo. Cualquier otro modelo va sin prefijo. El adaptador local usa `sentence-transformers` en CPU, con los vectores normalizados (norma 1), así que la similitud coseno es igual al producto interno.
- **Ejecución del modelo local**: `encode` es síncrono y usa CPU intensivamente. Desde código async se llama con `asyncio.to_thread`, nunca directo dentro del event loop.
- **Uso**: cada llamada devuelve `LLMResponse(text, usage, latency_ms, provider, model)` (o `StructuredResponse`) y emite un único log estructurado sin el prompt.
- **Tests de integración visibles**: `scripts/verify.sh` acepta `INTEGRATION=auto|1|0`. En `auto` corre los de `services/ai` si el modelo e5 está en la caché de Hugging Face, y los de `pipelines/ingest` si `tesseract` está instalado. Si no corren, el resumen muestra `SKIP` con el motivo. CI usa `INTEGRATION=1`, con la caché de Hugging Face y Tesseract instalados.

## Risks / Trade-offs

- **Limitación conocida de OpenAI**: un error que llega a mitad de un stream de OpenAI (el SDK levanta un `APIError` sin status) se trata como permanente y no se reintenta. Se acepta porque OpenAI no es el proveedor por defecto.

- Usar el mismo modelo como generador y como juez genera un sesgo de autopreferencia. La mitigación se define en `add-rag-core`.
- `sentence-transformers` trae PyTorch, que agranda la imagen Docker. Se instala la versión de PyTorch para CPU y el modelo se cachea en la imagen o en un volumen.
- Los SDKs cambian de API seguido. Para mitigarlo, se fijan las versiones en `uv.lock` y se usa `docs-checker` antes de cada adaptador.
- El streaming con reintentos es ambiguo, porque no se puede reintentar después de haber emitido tokens. Por eso se reintenta solo si el error ocurre antes del primer token.
