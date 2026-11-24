#!/usr/bin/env bash
# PostToolUse hook: corre `ruff format` sobre el archivo Python recién editado.
# Nunca bloquea: si ruff no está disponible o falla, sale con 0 en silencio.
set -uo pipefail

file="$(jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[[ "$file" == *.py ]] || exit 0
[[ -f "$file" ]] || exit 0

# Usar el proyecto uv más cercano (services/ai, pipelines/ingest, ...)
dir="$(dirname "$file")"
while [[ "$dir" != "/" && ! -f "$dir/pyproject.toml" ]]; do dir="$(dirname "$dir")"; done

if [[ -f "$dir/pyproject.toml" ]] && command -v uv >/dev/null 2>&1; then
  (cd "$dir" && uv run --quiet ruff format --quiet "$file" && uv run --quiet ruff check --fix --quiet "$file") >/dev/null 2>&1 || true
elif command -v ruff >/dev/null 2>&1; then
  ruff format --quiet "$file" >/dev/null 2>&1 || true
fi
exit 0
