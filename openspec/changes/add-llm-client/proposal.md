# Proposal

## Why

Todo el POC (RAG, agente, evaluación como juez) depende de un LLM. Si cada módulo llamara al SDK de un proveedor, cambiar de proveedor o testear sin red sería caro. Se necesita un cliente único, tipado y con reintentos y timeouts medidos antes de construir cualquier otra cosa.

## What Changes

- Interfaz `LLMClient` con tres operaciones: completar (respuesta completa), hacer streaming (tokens incrementales) y generar embeddings.
- Adaptadores para Anthropic, OpenAI y Ollama (local), más un proveedor `fake` determinista para tests y CI.
- Selección del proveedor y del modelo por variables de entorno, validadas al arrancar.
- Política de reintentos con backoff exponencial y jitter solo para errores transitorios, timeout por llamada y un error tipado cuando se agotan.
- Registro de uso por llamada (tokens de entrada y salida, latencia, proveedor y modelo) sin incluir el contenido del prompt.

## Capabilities

### New Capabilities
- `llm-client`: acceso a modelos de lenguaje y de embeddings independiente del proveedor, con configuración, reintentos, timeouts y registro de uso.

### Modified Capabilities

## Impact

- Código nuevo en `services/ai/src/ai_doc_assistant/llm/`.
- Dependencias nuevas: `pydantic`, `pydantic-settings`, `httpx`, los SDKs `anthropic` y `openai`, y `tenacity` o una implementación propia de reintentos (ver design).
- Variables de entorno: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, las claves por proveedor y `OLLAMA_BASE_URL` (ya documentadas en `.env.example`).

## Preguntas abiertas

1. ¿Qué proveedor usamos por defecto para la demo y qué modelo de embeddings? Esto afecta la dimensión de los vectores en `add-vector-index`.
2. ¿Incluimos Ollama en el POC o lo dejamos como extensión documentada?
3. ¿Los embeddings salen del mismo cliente o de una interfaz `Embedder` separada? Por ejemplo, para usar `sentence-transformers` en local.
4. ¿Queremos *structured output* (JSON con un esquema Pydantic) desde ahora? El agente lo va a necesitar.
