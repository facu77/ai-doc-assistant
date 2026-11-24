# ai-doc-assistant

POC integrador de un asistente de documentos con IA. Incluye:

- ingesta de PDFs y escaneos con OCR medido;
- búsqueda vectorial;
- respuestas con citas mediante RAG evaluado contra un set de oro;
- un agente con herramientas y aprobación humana;
- despliegue en Compose y kind, CI con gate de evaluación, observabilidad y controles de seguridad.

> **Estado**: esqueleto (día 1). Las 8 changes están especificadas en `openspec/changes/`, pero todavía no hay lógica implementada. Este README no muestra ninguna métrica: cada número que aparezca acá tiene que salir de una corrida registrada en `evals/`.

## Arquitectura (objetivo)

```
           ┌────────────┐  SSE   ┌──────────────────────────────┐
 cliente ─▶│  gateway   │──────▶│  services/ai (FastAPI)       │
           │ Node + TS  │◀──────│  /ingest /query /health      │
           └────────────┘        │  RAG · agente (LangGraph)    │
                                 │  llm_client (multi-proveedor)│
                                 └──────┬──────────────┬────────┘
                                        │              │
                              ┌─────────▼───┐   ┌──────▼──────┐
 pipelines/ingest ──chunks──▶ │   Qdrant    │   │  LLM / emb. │
 (ETL + OCR)                  └─────────────┘   └─────────────┘
                 MLflow · Prometheus/Grafana · gitleaks · ACL
```

## Estructura

```
CLAUDE.md              contexto y reglas para el agente
openspec/              specs y changes (ver openspec/README.md)
services/ai/           Python 3.12 + uv: FastAPI, RAG, agente, llm_client
services/gateway/      Node 22 + TypeScript: gateway SSE
pipelines/ingest/      ETL y OCR
evals/                 set de oro, scripts de evaluación, RESULTS.md
deploy/                compose, manifiestos para kind
scripts/               verify.sh, eval.sh
.github/workflows/     CI
.claude/               subagentes, skills (/verify, /eval), hooks, permisos
```

## Requisitos

- Python 3.12 y [`uv`](https://docs.astral.sh/uv/)
- Node 22 y npm
- Docker con Compose v2
- Opcional: [OpenSpec CLI](https://github.com/Fission-AI/OpenSpec) (`npm i -g @fission-ai/openspec@2.1.1`), kind y Tesseract OCR (`tesseract-ocr` + `tesseract-ocr-spa`)

## Uso

```bash
cp .env.example .env
make install
make verify
```

`make verify` corre lint, formato, tipos, tests, la validación de OpenSpec y la evaluación. Imprime un resumen por paso. Los otros comandos son `make eval` (evaluación RAG), `make up` / `make down` (servicios locales) y `make specs` (validación de las specs).

## Trabajo con Claude Code

| Elemento | Tipo | Ubicación |
| --- | --- | --- |
| `reviewer` | Subagente, solo lectura | `.claude/agents/reviewer.md` |
| `test-writer` | Subagente | `.claude/agents/test-writer.md` |
| `docs-checker` | Subagente, solo lectura | `.claude/agents/docs-checker.md` |
| `/verify` | Skill | `.claude/skills/verify/SKILL.md` |
| `/eval` | Skill | `.claude/skills/eval/SKILL.md` |
| Formato | Hook PostToolUse (`ruff format` y `ruff check --fix` sobre `.py`) | `.claude/hooks/format_python.sh` |
| Secretos | Hook PreToolUse (bloquea claves y `.env`) | `.claude/hooks/guard_secrets.py` |
| Skills de OpenSpec | Skills | `.claude/skills/openspec-*` |

Los permisos están en `.claude/settings.json`:

- **Sin confirmación**: tests, lint, tipos, `docker compose` (salvo `down`), `git status/diff/log` y las lecturas de OpenSpec.
- **Con confirmación**: `git push`, `rm`, `kubectl`, `helm`, `gh`, `openspec archive` y cualquier edición en `evals/golden/`.
- **Bloqueado**: leer o editar `.env`.

## Licencia

MIT (ver `LICENSE`).
