# Design

## Context

Llegan de las changes anteriores `LLMClient` (completar, streaming y embeddings), `VectorStore` con los modelos `Chunk` y `SearchHit`, y el chunker de la línea base (800 tokens con solapamiento de 100, sin cruzar páginas). Consumen esta change el endpoint `/ask` (`add-api-and-gateway`), el agente (`add-agent`, como herramienta de búsqueda) y el gate de `make verify`.

## Goals / Non-Goals

**Goals:**
- Un pipeline de línea base simple y medido, contra el que se compara cada mejora.
- Etapas enchufables (chunker, retriever, reranker, reescritor) seleccionables por nombre de variante, sin tocar el resto del pipeline.
- Una evaluación reproducible: misma variante, mismo set y misma semilla dan las mismas métricas deterministas.

**Non-Goals:**
- Encuadre del contexto contra *prompt injection* y filtrado por ACL (`add-observability-security`).
- Memoria conversacional y preguntas de varios turnos.
- Correr los experimentos de mejora: acá se construyen y se prueban las piezas; las corridas comparativas van en una sesión posterior.

## Decisions

- **Pipeline de línea base**: embeddings de la pregunta → búsqueda vectorial top-k (`RAG_TOP_K`, por defecto 5) → prompt con los chunks numerados y sus metadatos `[doc_id, page]` → `LLMClient.complete` o `stream`. El resultado es un `RagAnswer(text, citations, abstained, retrieved, latency_ms)`.
- **Citas**: el prompt pide citas con el formato `[doc_id, p. N]`. Un parser las extrae y las valida contra los chunks recuperados; las citas que no corresponden a un chunk recuperado se descartan y se registran como `invalid_citation`. Una respuesta sin ninguna cita válida se trata como abstención.
- **Abstención en dos niveles**: (1) si ningún hit supera `RAG_MIN_SCORE`, se abstiene sin llamar al LLM; (2) si no, el prompt instruye al modelo a responder exactamente el texto de abstención cuando el contexto no alcanza. El umbral se calibra en un set de desarrollo aparte, nunca con el set de oro.
- **Streaming**: `answer_stream()` devuelve un `AsyncIterator` de eventos (`token`, y al final `citations` y `done`). Las citas se emiten al cerrar, después de validarlas sobre el texto completo.
- **Variantes enchufables**: cada etapa es un `Protocol` (`Chunker`, `Retriever`, `Reranker`, `QueryRewriter`), y una variante es un `RagConfig` Pydantic con nombre, en `evals/variants.yaml`. `--variant` elige una; la línea base es `baseline`. Cada variante cambia una sola etapa respecto de `baseline`:
  - `structure_chunking`: corta por títulos y secciones detectados en la ingesta, con el mismo tope de tokens. Requiere reindexar en una colección separada por variante.
  - `hybrid_rrf`: BM25 más vectores, combinados con Reciprocal Rank Fusion (k = 60). BM25 en proceso con `rank-bm25`, o vectores dispersos de Qdrant si la versión instalada los soporta (lo confirma `docs-checker`).
  - `rerank_ce`: recupera top-20 y reordena con un cross-encoder multilingüe local (`sentence-transformers`), quedándose con top-5.
  - `query_rewrite`: el LLM reescribe la pregunta (expansión o HyDE) antes de recuperar. Suma una llamada y latencia, que quedan medidas.
- **Métricas**:
  - recall@5: fracción de las `expected_sources` (`doc_id` y página) presentes en el top-5. MRR: inverso del rango de la primera fuente esperada. Ambas se calculan solo sobre las preguntas con respuesta.
  - Fidelidad (*faithfulness*): el juez descompone la respuesta en afirmaciones y marca cuáles están sustentadas por los chunks citados; la métrica es la proporción sustentada. Relevancia: puntaje de 1 a 5 normalizado a 0–1, comparado con `expected_answer`.
  - Corrección de citas: proporción de citas válidas cuya página está entre las `expected_sources`.
  - Precisión de abstención: en las preguntas con tag `unanswerable`, proporción en que el sistema se abstuvo; también se reporta la tasa de falsas abstenciones en las que sí tienen respuesta.
  - Latencia p50 y p95 de punta a punta por pregunta, con 3 preguntas de calentamiento descartadas.
- **Juez**: `LLMClient` separado, configurado por `EVAL_JUDGE_PROVIDER` y `EVAL_JUDGE_MODEL`, con temperatura 0 y salida JSON validada con Pydantic. Si el JSON es inválido se reintenta una vez y después la pregunta cuenta como `judge_error` (no como 0).
- **Salida de la corrida**: `evals/runs/<timestamp>_<variant>.json` con commit, variante, configuración, métricas agregadas y por pregunta. Si `MLFLOW_TRACKING_URI` está definida, se registran parámetros, métricas y el JSON como artefacto. Sin MLflow la corrida funciona igual.
- **Gate `--check`**: compara contra `evals/baseline.json` métrica por métrica con la tolerancia de cada una (absoluta para calidad, relativa para latencia) y sale con código 1 si alguna empeora más de lo tolerado. `--update-baseline` reescribe la línea base y solo se usa a mano.
- **Set oculto**: `run_eval.py --golden <ruta>` acepta otro archivo con el mismo formato; el set oculto vive fuera del repo y nunca se commitean sus corridas.

## Risks / Trade-offs

- **Sesgo del juez**: un LLM tiende a preferir textos de su misma familia, respuestas largas y la primera opción. Se mitiga con un juez de otra familia que el generador, rúbricas con criterios binarios por afirmación, temperatura 0 y una validación manual de 10 preguntas al principio, con su acuerdo humano-juez reportado en `RESULTS.md`.
- **Costo y ruido de las métricas con juez**: varían entre corridas aunque la temperatura sea 0. Por eso el gate en CI usa solo métricas deterministas, y las comparaciones de variantes reportan la media de 3 corridas.
- **Set chico**: con 50 preguntas, una diferencia de 0,02 puede ser ruido. Se reporta el intervalo de confianza por *bootstrap* junto con cada métrica.
- **Sobreajuste al set de oro**: se mitiga con la regla de no mirar las preguntas, el set de desarrollo separado para calibrar y el set oculto del autor.
- **Reindexar por variante de chunking** duplica el almacenamiento en Qdrant. Es aceptable para el tamaño del corpus.
