#!/usr/bin/env bash
# Verificación completa del repo: lint, formato, tipos, tests (unitarios e integración) y evaluación.
# Sigue aunque falle un paso y al final imprime un resumen. Sale con 1 si algo falló.
# Variables: INTEGRATION=auto|1|0 (ver abajo) y SKIP_EVAL=1.
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
fail() { RESULTS+=("FALLO $1 ($2)"); FAILED=1; }

# Tests de integración: INTEGRATION=auto (default) | 1 | 0.
#   auto: corre cada grupo solo si su dependencia ya está disponible; si no, SKIP con motivo.
#   1:    los corre siempre; si falta una dependencia, el paso FALLA (lo que usa CI).
#   0:    no los corre.
INTEGRATION="${INTEGRATION:-auto}"
case "$INTEGRATION" in
  auto|1|0) ;;
  *) echo "INTEGRATION tiene que ser auto, 1 o 0 (vino: ${INTEGRATION})" >&2; exit 2 ;;
esac

# Criterio para services/ai: el modelo e5 está en la caché de Hugging Face. En `auto` no se
# descarga nada (una corrida local no baja ~470 MB sin avisar); con INTEGRATION=1 se
# descarga, salvo que HF_HUB_OFFLINE=1 lo impida.
E5_REPO_DIR="${HF_HUB_CACHE:-${HF_HOME:-$HOME/.cache/huggingface}/hub}/models--intfloat--multilingual-e5-small"
e5_cached() { compgen -G "${E5_REPO_DIR}/snapshots/*/model.safetensors" >/dev/null; }

# pytest sale con 5 si no hay tests con el marcador: eso no es un fallo.
pytest_integration() {
  (cd "$1" && uv run pytest -q -m integration; rc=$?; [[ $rc -eq 0 || $rc -eq 5 ]])
}

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

# Integración (después de los unitarios, para que un fallo rápido no espere al modelo)
if [[ "$INTEGRATION" == "0" ]]; then
  skip "ai: integración" "INTEGRATION=0"
elif e5_cached; then
  step "ai: integración" pytest_integration services/ai
elif [[ "$INTEGRATION" == "1" && "${HF_HUB_OFFLINE:-0}" == "1" ]]; then
  fail "ai: integración" "el modelo e5 no está en la caché y HF_HUB_OFFLINE=1 impide bajarlo"
elif [[ "$INTEGRATION" == "1" ]]; then
  step "ai: integración" pytest_integration services/ai
else
  skip "ai: integración" "el modelo e5 no está en la caché de HF; INTEGRATION=1 lo descarga"
fi

if [[ "$INTEGRATION" == "0" ]]; then
  skip "ingest: integración" "INTEGRATION=0"
elif [[ ! -f pipelines/ingest/pyproject.toml ]]; then
  skip "ingest: integración" "sin pyproject todavía"
elif command -v tesseract >/dev/null 2>&1; then
  step "ingest: integración" pytest_integration pipelines/ingest
elif [[ "$INTEGRATION" == "1" ]]; then
  fail "ingest: integración" "tesseract no está instalado"
else
  skip "ingest: integración" "tesseract no está instalado"
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
