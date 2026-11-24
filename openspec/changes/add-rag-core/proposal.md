# Proposal

## Why

El valor del POC está en responder preguntas sobre los documentos con citas verificables y en poder demostrar con números que cada mejora mejora algo. Sin una línea base medida contra un set de oro, cualquier cambio de chunking, búsqueda o prompt es una opinión. Esta change arma el RAG mínimo y el arnés de evaluación que va a juzgar todo lo que venga después.

## What Changes

- Pipeline de respuesta: recuperar los chunks más relevantes, generar una respuesta basada solo en ellos y citar cada afirmación con `[doc_id, página]`. Si la evidencia no alcanza, el sistema se abstiene con "No encontré información suficiente".
- Streaming de los tokens de la respuesta a nivel de librería (el endpoint HTTP y el SSE llegan con `add-api-and-gateway`).
- Set de oro en `evals/golden/questions.jsonl`: entre 40 y 60 preguntas ficticias sobre el corpus, incluidas preguntas sin respuesta en el corpus.
- Script `evals/run_eval.py` (lo invoca `scripts/eval.sh`) con métricas de recuperación (recall@5, MRR), de generación (fidelidad y relevancia con un LLM como juez), corrección de citas, precisión de abstención y latencia p95.
- Línea base versionada en `evals/baseline.json` y gate `--check` que falla ante una regresión mayor a la tolerancia.
- Variantes enchufables (`--variant <nombre>`) para los experimentos de mejora: chunking por estructura, búsqueda híbrida, reranking y reescritura de la consulta. En esta change se construyen las piezas y se mide la línea base; los experimentos se corren de a una variable en una sesión posterior y se registran en `evals/RESULTS.md`.

## Capabilities

### New Capabilities
- `rag-answering`: respuesta a preguntas basada en los chunks recuperados, con citas por documento y página, abstención ante evidencia insuficiente y streaming.
- `rag-evaluation`: set de oro, métricas de recuperación y generación, línea base versionada, gate de regresión y comparación de variantes.

### Modified Capabilities

## Impact

- Código nuevo: `services/ai/src/ai_doc_assistant/rag/` y `evals/run_eval.py`.
- Archivos nuevos: `evals/golden/questions.jsonl` (lo escribe el humano o se aprueba explícitamente, ver CLAUDE.md), `evals/baseline.json` y las corridas en `evals/runs/`.
- Dependencias candidatas: `rank-bm25` (o los vectores dispersos de Qdrant), `sentence-transformers` para el cross-encoder y `mlflow` como opcional.
- Variables de entorno: `RAG_TOP_K`, `RAG_MIN_SCORE`, `RAG_VARIANT`, `EVAL_JUDGE_PROVIDER`, `EVAL_JUDGE_MODEL` y `MLFLOW_TRACKING_URI`.
- `scripts/verify.sh` pasa a ejecutar un gate real (`eval.sh --check`).
- Depende de `add-llm-client` (`LLMClient`) y de `add-vector-index` (`VectorStore`, `Chunk`, `SearchHit`), y a través de esta última de `IngestedDocument`.

## Preguntas abiertas

1. ¿Quién escribe el set de oro? Propuesta: el agente genera un borrador desde el corpus en un archivo aparte, el humano lo revisa y lo copia a `evals/golden/`. Así se respeta que el agente no lo toque.
2. ¿Qué umbrales aceptamos para la línea base? Propuesta: recall@5 de 0,80 o más, fidelidad de 0,85 o más, corrección de citas de 0,90 o más, precisión de abstención de 0,80 o más y p95 de 4 s o menos en local.
3. ¿Qué tolerancia usa `--check`? Propuesta: 0,02 absoluto para las métricas de calidad y 20% relativo para el p95.
4. ¿Qué modelo usamos como juez y de qué proveedor? Propuesta: un modelo de una familia distinta a la del generador, para reducir el sesgo de autopreferencia.
5. ¿Qué corre el gate en CI, sin claves? Propuesta: solo las métricas deterministas (recall@5, MRR, citas, abstención) con embeddings y LLM `fake`; las métricas con juez corren solo cuando hay claves.
6. ¿Qué proporción de preguntas sin respuesta incluye el set? Propuesta: entre 15% y 20%.
7. ¿La abstención se decide por un umbral de score de recuperación, por el propio LLM o por ambos? Ver design.
