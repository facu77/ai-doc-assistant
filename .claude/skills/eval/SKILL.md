---
name: eval
description: Ejecuta la evaluación RAG contra el set de oro y compara contra la última corrida registrada y la línea base. Úsalo al cambiar chunking, embeddings, búsqueda, reranking o prompts.
argument-hint: "[nombre-de-variante]"
allowed-tools: Bash(make eval) Bash(./scripts/eval.sh *) Bash(git log *) Bash(git rev-parse *)
---

1. Corré `./scripts/eval.sh`. Si los argumentos (`$ARGUMENTS`) traen un nombre de variante, pasalo como `--variant $ARGUMENTS`.
2. Si el script dice que todavía no hay `evals/run_eval.py`, informalo: la evaluación llega con la change `add-rag-core`. No sigas.
3. Leé la corrida nueva en `evals/runs/` y comparala contra:
   - la corrida anterior más reciente en `evals/runs/`;
   - la línea base de `evals/baseline.json`.
4. Mostrá una tabla con estas columnas: métrica | línea base | anterior | actual | Δ vs. línea base. Las métricas son recall@5, MRR, fidelidad, relevancia y latencia p95. Marcá las regresiones.
5. Si el usuario lo pide, agregá una fila a `evals/RESULTS.md` con fecha, commit (`git rev-parse --short HEAD`), variante, métricas y el id del run de MLflow. Cada fila tiene que corresponder a una corrida real, sin redondear a favor.
6. Nunca modifiques `evals/golden/` ni ajustes el sistema mirando sus preguntas.
