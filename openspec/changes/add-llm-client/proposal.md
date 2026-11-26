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

## Decisiones tomadas (2026-11-24 y 2026-11-26)

1. **Embeddings**: modelo local `intfloat/multilingual-e5-small` (384 dimensiones). Es gratis, no saca los documentos de la máquina y es determinista en CI sin claves. Queda detrás de `Embedder`, así que se puede comparar después contra una API.
2. **LLM por defecto**: `claude-haiku-5-5`, tanto para generar como para juzgar en la evaluación. Usar el mismo modelo como juez introduce un sesgo de autopreferencia. Se mitiga en `add-rag-core` con una verificación humana sobre una muestra.
3. **Embeddings separados del LLM**: interfaz `Embedder` propia.
4. **Ollama**: queda fuera del POC y se documenta como extensión posible.
5. **Salida estructurada**: entra en esta change porque el agente la necesita.
6. **Esquemas cerrados para la salida estructurada (2026-11-26)**: un modelo Pydantic por herramienta y la llamada como unión discriminada por el nombre de la herramienta. Un esquema con objetos sin propiedades (un dict libre) se rechaza con `LLMSchemaError` antes de llamar al proveedor, en todos los proveedores.
7. **Tope de `Retry-After` de 30 s (2026-11-26)**: si el proveedor pide más, no se espera y se levanta `LLMRateLimitError` con el `retry_after` original. Con un valor dentro del tope, se espera `Retry-After` más un jitter acotado.
8. **`StructuredResponse[T]` (2026-11-26)**: `complete_structured` devuelve el objeto validado con el uso sumado de todos los intentos, la latencia, los intentos, el proveedor y el modelo. Al rendirse, loguea la llamada con resultado de error.
9. **Tests de integración visibles (2026-11-26)**: `verify.sh` con `INTEGRATION=auto|1|0` y CI con `INTEGRATION=1`, Tesseract y la caché de Hugging Face.

10. **Decisiones sobre lo que surgió al implementar (2026-11-26)**:
    - `attempts` cuenta todos los pedidos al proveedor (con reintentos transitorios), en `StructuredResponse`, `LLMValidationError` y el log.
    - Los esquemas cerrados también rechazan los campos `Any` y las uniones en la raíz.
    - Los modelos e5 `-instruct` se rechazan con un error de configuración, en vez de embeberlos sin el prompt que necesitan.
    - OpenAI `strict: true` queda afuera, porque depende de una función privada del SDK.
    - Los errores de OpenAI a mitad de un stream se tratan como permanentes. Es una limitación conocida: OpenAI no es el proveedor por defecto.
    - Se aceptan como están: reintentar los cortes de conexión, `system` y `max_tokens` como parámetros por llamada, `LLM_PROVIDER` y `EMBEDDINGS_PROVIDER` sin default, y `httpx2` en lugar de `httpx`.

## Preguntas abiertas

Ninguna.
