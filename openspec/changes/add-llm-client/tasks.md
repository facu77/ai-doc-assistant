# Tasks

## 1. Contrato y configuración

- [x] 1.1 Usar `docs-checker` para confirmar las firmas de `pydantic-settings`, de los SDKs `anthropic` (incluida la salida estructurada) y `openai`, y de `sentence-transformers` en las versiones instaladas
- [x] 1.2 Definir `LLMSettings`, `LLMResponse`, `Usage` y la jerarquía `LLMError`
- [x] 1.3 Definir los Protocols `LLMClient` (complete, stream, complete_structured) y `Embedder` (embed_queries, embed_passages), con sus fábricas

## 2. Tests primero

- [x] 2.1 Usar `test-writer` para escribir los tests de todos los escenarios con un proveedor falso programable (fallas N veces, latencia, 429 con Retry-After)
- [x] 2.2 Confirmar que los tests fallan por la razón correcta

## 3. Implementación

- [x] 3.1 Proveedor `fake` determinista
- [x] 3.2 Política de reintentos y timeout
- [x] 3.3 Adaptadores de Anthropic y OpenAI, con salida estructurada
- [x] 3.4 `Embedder` local (`multilingual-e5-small`, CPU, vectores normalizados) y `Embedder` fake determinista
- [x] 3.5 Log estructurado de uso, con un test que verifica la ausencia del prompt

## 4. Cierre

- [x] 4.1 Correr `/verify` en verde
- [ ] 4.2 Test de integración opcional (`-m integration`) contra un proveedor real, con la clave tomada del entorno (escrito en `tests/llm/test_real_providers.py` y corrido con `make test-integration`: se saltea porque no hay `ANTHROPIC_API_KEY`; falta una corrida con clave)
- [ ] 4.3 Pasar `reviewer` sobre el diff y resolver los hallazgos
- [x] 4.4 Agregar la sección `llm` al README de `services/ai`

## 5. Ronda de revisión (2026-11-26)

- [x] 5.1 Esquemas cerrados: `ensure_closed_schema` y `LLMSchemaError` antes de llamar al proveedor, con tests de contrato contra el `transform_schema` real y contra los cuerpos que serializan los SDKs
- [x] 5.2 `StructuredResponse[T]` con uso sumado, intentos, latencia, proveedor y modelo, y log de error al rendirse
- [x] 5.3 Tope de `Retry-After` de 30 s y jitter acotado sobre `Retry-After`
- [x] 5.4 Errores SSE con HTTP 200 clasificados por `body.error.type`
- [x] 5.5 Tests de la fábrica de punta a punta (`LLM_MAX_RETRIES`, `LLM_TIMEOUT_SECONDS`, `EMBEDDINGS_BATCH_SIZE`), OpenAI sin `LLM_MODEL` y guardia de los reintentos del SDK de OpenAI
- [x] 5.6 `aclose()` en `LLMClient` y prefijos de e5 solo para la familia e5
- [x] 5.7 `verify.sh` con `INTEGRATION=auto|1|0`, CI con Tesseract, caché de Hugging Face e `INTEGRATION=1`, y `make install` con `uv sync --locked`
