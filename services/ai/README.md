# services/ai

Servicio Python (FastAPI, RAG, agente LangGraph, `llm_client`). Gestionado con `uv`.

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                  # offline: excluye los tests marcados `integration`
uv run pytest -m integration   # o `make test-integration` desde la raíz
```

PyTorch se instala **solo para CPU** desde `https://download.pytorch.org/whl/cpu`
(`[[tool.uv.index]]` con `explicit = true` en `pyproject.toml`). El índice de PyPI trae las
ruedas con CUDA, que pesan varios GB y no se usan en este POC.

## llm

Cliente LLM independiente del proveedor: `ai_doc_assistant.llm`.

```python
from ai_doc_assistant.llm import build_llm_client

client = build_llm_client()  # lee LLM_* del entorno; si falta algo, falla acá
respuesta = await client.complete("¿Cuántos días de licencia anual hay?")
async for fragmento in client.stream("Resumí la política de vacaciones"):
    ...
resultado = await client.complete_structured("Elegí una herramienta", LlamadaHerramienta)
resultado.value  # objeto validado; además: usage, attempts, latency_ms, provider, model
await client.aclose()  # al apagar el servicio: cierra el cliente HTTP del SDK
```

- `LLMClient` (`llm/client.py`) es un `Protocol` con `complete`, `stream` y `complete_structured`.
  Los consumidores lo reciben inyectado y no importan ningún SDK.
- `ResilientLLMClient` (`llm/resilient.py`) implementa el timeout, los reintentos, la
  validación de la salida estructurada y el log de uso para todos los proveedores. Cada
  adaptador (`llm/providers/`) hace una sola llamada y traduce sus errores.
- Errores: `LLMError` y sus subclases `LLMConfigError`, `LLMTimeoutError`,
  `LLMRateLimitError`, `LLMProviderError`, `LLMValidationError` y `LLMSchemaError`. La
  excepción del SDK queda en `__cause__`.
- Cada llamada emite un log `llm_call` (logger `ai_doc_assistant.llm`, atributo `llm_call` del
  registro) con proveedor, modelo, operación, tokens, latencia, intentos y resultado. No
  incluye el prompt ni la respuesta. Los loggers `anthropic` y `openai` quedan en `WARNING`.
  En `DEBUG`, el SDK de Anthropic loguea el cuerpo de cada request. El de OpenAI 3.59 ya no
  lo hace, y su logger se fija en `WARNING` por defensa en profundidad.

### Salida estructurada: solo esquemas cerrados

Cada herramienta declara sus argumentos con un modelo propio, y la llamada es una unión
discriminada por el nombre de la herramienta, envuelta en un modelo contenedor (la raíz
tiene que ser un objeto):

```python
class BuscarDocumentos(BaseModel):
    herramienta: Literal["buscar_documentos"]
    query: str
    top_k: int


class ObtenerPagina(BaseModel):
    herramienta: Literal["obtener_pagina"]
    doc_id: str
    pagina: int


class LlamadaHerramienta(BaseModel):
    llamada: Annotated[BuscarDocumentos | ObtenerPagina, Field(discriminator="herramienta")]
```

Se rechaza con `LLMSchemaError`, antes de llamar al proveedor (`llm/schema.py`), un esquema
que tenga alguno de estos elementos:

- un objeto sin propiedades: `dict[str, object]` o un modelo sin campos;
- un objeto que admite propiedades libres (`extra="allow"`);
- un campo `Any`;
- un array sin `items` (por ejemplo, una tupla);
- una unión en la raíz.

El motivo es que `anthropic.transform_schema` convierte un dict libre en un objeto vacío y
cerrado, y el modelo no puede llenar nada. Si la respuesta no valida, se reintenta una vez
con el error como contexto. Si vuelve a fallar, se levanta `LLMValidationError`.

Limitaciones conocidas de OpenAI: la salida estructurada va con `strict: false`, porque
`strict: true` depende de una función privada del SDK, y la valida Pydantic. Un error a mitad
de un stream de OpenAI se trata como permanente y no se reintenta.

### Configuración

| Variable | Default | Qué hace |
| --- | --- | --- |
| `LLM_PROVIDER` | *(obligatoria)* | `anthropic`, `openai` o `fake` (determinista, sin red, para tests y CI) |
| `LLM_MODEL` | `claude-haiku-5-5` | Id del modelo. Con `openai` es obligatorio (si falta, `LLMConfigError` al arrancar). `fake` lo ignora y reporta `fake-llm` |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout de cada intento. En streaming, es el tiempo máximo entre fragmentos |
| `LLM_MAX_RETRIES` | `3` | Intentos **totales** (`1` = sin reintentos) |
| `ANTHROPIC_API_KEY` | — | Obligatoria con `LLM_PROVIDER=anthropic`. Si está vacía, cuenta como faltante |
| `OPENAI_API_KEY` | — | Obligatoria con `LLM_PROVIDER=openai` |

Reintentos: solo ante timeout, 429, 5xx y cortes de conexión (y, en el stream de Anthropic,
los eventos SSE `overloaded_error` y `api_error`). Se usa backoff exponencial con *full
jitter* (base de 0,5 s y tope de 8 s). Con `Retry-After`, se espera ese valor más hasta
0,5 s de jitter. Si el proveedor pide más de 30 s, no se espera: se levanta
`LLMRateLimitError` con el `retry_after` original. Un 400, 401, 403 o 404 falla en el primer
intento. En streaming se reintenta solo si el error llega antes del primer fragmento. Los
SDKs se crean con `max_retries=0`.

## embeddings

`ai_doc_assistant.embeddings`: interfaz `Embedder` (`embeddings/base.py`), separada del LLM.

```python
from ai_doc_assistant.embeddings import build_embedder

embedder = build_embedder()  # con `local` carga el modelo (bloqueante, unos segundos)
consultas = await embedder.embed_queries(["¿cómo pido vacaciones?"])
pasajes = await embedder.embed_passages(["Procedimiento para solicitar la licencia anual"])
```

- `LocalEmbedder` agrega el prefijo del rol (`"query: "` / `"passage: "`), procesa en lotes de
  `EMBEDDINGS_BATCH_SIZE` y corre `encode` en `asyncio.to_thread` para no bloquear el event
  loop. Devuelve vectores normalizados (norma 1), así que coseno = producto interno.
- `FakeEmbedder` genera vectores deterministas desde un hash. No captura significado: sirve para
  testear lo que viene después del embedding.

| Variable | Default | Qué hace |
| --- | --- | --- |
| `EMBEDDINGS_PROVIDER` | *(obligatoria)* | `local` o `fake` |
| `EMBEDDINGS_MODEL` | `intfloat/multilingual-e5-small` | Modelo de sentence-transformers (384 dimensiones). Si cambia, hay que reindexar |
| `EMBEDDINGS_BATCH_SIZE` | `64` | Textos por lote |

Los prefijos dependen del id del modelo, tanto con la fábrica como con el constructor de
`LocalEmbedder`. Si el último segmento empieza con `e5-` o `multilingual-e5-`, se usan
`query: ` y `passage: `. Cualquier otro modelo va sin prefijo. Las variantes `-instruct`
necesitan un prompt `Instruct: ...` que este POC no implementa, así que se rechazan con
`EmbeddingsConfigError` antes de cargar el modelo.

El modelo se descarga de Hugging Face la primera vez (unos 470 MB en `~/.cache/huggingface`).

## Tests de integración

Llevan `@pytest.mark.integration` y `uv run pytest` los excluye (`addopts` con
`-m 'not integration'`). `scripts/verify.sh` (`make verify`) los corre según `INTEGRATION`:

| `INTEGRATION` | Qué hace |
| --- | --- |
| `auto` (default) | `services/ai` corre si el modelo e5 ya está en la caché de Hugging Face, y `pipelines/ingest` si existe y `tesseract` está instalado. Si no, el resumen muestra `SKIP` con el motivo. No descarga nada |
| `1` | Los corre siempre. Descarga e5 si hace falta, salvo con `HF_HUB_OFFLINE=1`. Si falta una dependencia, o si pytest no recolecta ningún test de integración (código 5), el paso falla. Es lo que usa CI |
| `0` | No los corre |

```bash
INTEGRATION=1 SKIP_EVAL=1 ./scripts/verify.sh   # todo, con integración obligatoria
make test-integration                           # solo los de integración
```

- `tests/embeddings/test_local_e5.py` usa el modelo e5 real: dimensión 384, determinismo
  (coseno ≥ 0,9999), normalización, lote de 250 y similitud semántica. Necesita acceso a
  `huggingface.co` la primera vez.
- `tests/llm/test_real_providers.py` llama a las APIs pagas. Se saltea si no está
  `ANTHROPIC_API_KEY` u `OPENAI_API_KEY`. Para OpenAI, además, hay que elegir el modelo con
  `OPENAI_INTEGRATION_MODEL`.
