#!/usr/bin/env bash
# Evaluación RAG contra el set de oro (evals/golden/).
#   ./scripts/eval.sh          corre la evaluación y agrega la corrida a evals/runs/
#   ./scripts/eval.sh --check  igual, pero falla si hay regresión contra evals/baseline.json
# La implementación real llega con la change add-rag-core (evals/run_eval.py).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f evals/run_eval.py ]]; then
  echo "eval: todavía no hay evals/run_eval.py (llega con add-rag-core). Nada que evaluar."
  exit 0
fi

cd services/ai
exec uv run python ../../evals/run_eval.py "$@"
