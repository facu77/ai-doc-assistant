#!/usr/bin/env bash
# Verificación completa del repo: lint, formato, tipos, tests y evaluación.
# Sigue aunque falle un paso y al final imprime un resumen. Sale con 1 si algo falló.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

declare -a RESULTS=()
FAILED=0

step() {
  local name="$1"; shift
  echo "::group::${name}"
  if "$@"; then
    RESULTS+=("OK    ${name}")
  else
    RESULTS+=("FALLO ${name}")
    FAILED=1
  fi
  echo "::endgroup::"
}

skip() { RESULTS+=("SKIP  $1 ($2)"); }

# Python: services/ai
step "ai: ruff check"   bash -c "cd services/ai && uv run ruff check ."
step "ai: ruff format"  bash -c "cd services/ai && uv run ruff format --check ."
step "ai: mypy"         bash -c "cd services/ai && uv run mypy"
step "ai: pytest"       bash -c "cd services/ai && uv run pytest -q"

# Python: pipelines/ingest (se inicializa en add-ingest-pipeline)
if [[ -f pipelines/ingest/pyproject.toml ]]; then
  step "ingest: ruff check" bash -c "cd pipelines/ingest && uv run ruff check ."
  step "ingest: ruff format" bash -c "cd pipelines/ingest && uv run ruff format --check ."
  step "ingest: mypy"       bash -c "cd pipelines/ingest && uv run mypy"
  step "ingest: pytest"     bash -c "cd pipelines/ingest && uv run pytest -q"
else
  skip "ingest" "sin pyproject todavía"
fi

# Node: services/gateway
if [[ ! -d services/gateway/node_modules ]]; then
  (cd services/gateway && npm ci --silent)
fi
step "gateway: eslint"    bash -c "cd services/gateway && npm run -s lint"
step "gateway: prettier"  bash -c "cd services/gateway && npm run -s format:check"
step "gateway: tsc"       bash -c "cd services/gateway && npm run -s typecheck"
step "gateway: vitest"    bash -c "cd services/gateway && npm test -s"

# Specs
if command -v openspec >/dev/null 2>&1; then
  step "openspec validate" openspec validate --all --no-interactive
else
  skip "openspec validate" "CLI no instalada"
fi

# Evaluación RAG: gate contra la línea base (desde add-rag-core)
if [[ "${SKIP_EVAL:-0}" == "1" ]]; then
  skip "eval" "SKIP_EVAL=1"
else
  step "eval" ./scripts/eval.sh --check
fi

echo
echo "===== Resumen de verificación ====="
printf '%s\n' "${RESULTS[@]}"
exit "$FAILED"
