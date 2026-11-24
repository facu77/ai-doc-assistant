# Tasks

## 1. Contrato y set de oro

- [ ] 1.1 Usar `docs-checker` para confirmar las APIs de `rank-bm25` (o de los vectores dispersos de Qdrant), `sentence-transformers` (cross-encoder) y `mlflow` en las versiones instaladas
- [ ] 1.2 Definir `RagConfig`, `RagAnswer`, `Citation`, los eventos de streaming, la jerarquía `RagError` y los Protocols `Chunker`, `Retriever`, `Reranker` y `QueryRewriter`
- [ ] 1.3 Definir el esquema Pydantic de `questions.jsonl`, el del JSON de corrida y el de `evals/baseline.json`
- [ ] 1.4 Generar un borrador de 40 a 60 preguntas ficticias (con 15% a 20% `unanswerable`) fuera de `evals/golden/` y pedir al humano que lo revise y lo copie
- [ ] 1.5 Armar un set de desarrollo aparte, chico, para calibrar `RAG_MIN_SCORE` sin mirar el set de oro

## 2. Tests primero

- [ ] 2.1 Usar `test-writer` para escribir los tests de `rag-answering` con el LLM `fake`, embeddings deterministas y FAISS en memoria
- [ ] 2.2 Usar `test-writer` para escribir los tests de `rag-evaluation` con un set de ejemplo de pocas preguntas, métricas calculables a mano y un juez falso programable
- [ ] 2.3 Confirmar que los tests fallan por la razón correcta

## 3. Implementación

- [ ] 3.1 Pipeline `baseline`: recuperación, prompt con fragmentos numerados, parser y validador de citas, abstención en dos niveles
- [ ] 3.2 Streaming con eventos `token`, `citations` y `done`
- [ ] 3.3 `evals/run_eval.py`: carga y validación del set, métricas, juez, JSON en `evals/runs/` y MLflow opcional
- [ ] 3.4 Gate `--check` con tolerancias por métrica y `--update-baseline` manual
- [ ] 3.5 Variantes enchufables en `evals/variants.yaml`: `structure_chunking`, `hybrid_rrf`, `rerank_ce` y `query_rewrite`, cada una con un test de que solo cambia su etapa
- [ ] 3.6 Validación manual del juez sobre 10 preguntas y registro del acuerdo humano-juez

## 4. Cierre

- [ ] 4.1 Correr la línea base, commitear `evals/baseline.json` y la primera fila de `evals/RESULTS.md` con su corrida y su run de MLflow
- [ ] 4.2 Correr `/verify` en verde, con `eval.sh --check` activo
- [ ] 4.3 Pasar `reviewer` sobre el diff y resolver los hallazgos
- [ ] 4.4 Agregar la sección `rag` al README de `services/ai` y actualizar `evals/README.md` con el uso de `--variant`, `--check` y `--golden`
- [ ] 4.5 Dejar anotadas en `evals/RESULTS.md` las filas pendientes de los cuatro experimentos, para correrlos de a una variable en la sesión siguiente
