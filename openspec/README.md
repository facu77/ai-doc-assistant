# OpenSpec: changes del POC

Cada pieza del POC es una change con su propuesta, su diseño, sus specs con escenarios verificables y sus tareas. Antes de aplicar una change, revisá su spec y respondé sus **Preguntas abiertas**.

| # | Change | Resultado verificable | Depende de | Tanda |
| --- | --- | --- | --- | --- |
| 1 | `add-llm-client` | Cambio de proveedor por variable de entorno; tests de reintentos y timeouts | n/a | A |
| 2 | `add-ingest-pipeline` | 20 documentos procesados con reporte de OCR y CER | n/a | A |
| 3 | `add-vector-index` | Benchmark FAISS frente a Qdrant con recall@10 y p95 | 2 | B |
| 4 | `add-rag-core` | Evaluación contra línea base; tabla de mejoras | 1, 3 | — |
| 5 | `add-api-and-gateway` | `/ingest`, `/query` en streaming, `/health`; gateway SSE | 4 | C |
| 6 | `add-agent` | 15 a 20 casos con trayectoria esperada; límites y aprobación humana | 4 | C |
| 7 | `add-deploy-and-ci` | Compose y kind funcionando; pipeline con gate de evaluación | 5 | B (esqueleto) |
| 8 | `add-observability-security` | Dashboard, MLflow, gitleaks, PII, ACL y prueba de inyección | 5 | C (después) |
| 9 | `improve-ocr-quality` | Escaneo limpio en 2 % o menos sin romper las páginas a dos columnas (psm según la estructura de la página) y un perfil de escaneo ruidoso más difícil, con umbral preregistrado | 2 | — |

## Ciclo por change

1. **Spec**: revisá `openspec/changes/<nombre>/` y cerrá las preguntas abiertas.
2. **Plan**: Claude Code en modo plan, con `openspec instructions apply --change <nombre>`.
3. **Tests primero**: subagente `test-writer`.
4. **Verificación**: `/verify` (y `/eval` si es RAG).
5. **Revisión**: subagente `reviewer`.
6. **Archivo**: `openspec archive <nombre>` y commit con la métrica medida.

Skills de OpenSpec disponibles en Claude Code: `/openspec-propose`, `/openspec-apply-change`, `/openspec-archive-change`, `/openspec-explore`, `/openspec-update-change` y `/openspec-sync-specs`.

## Paralelización con worktrees

```bash
git worktree add ../ai-doc-assistant-add-llm-client -b add-llm-client
git worktree add ../ai-doc-assistant-add-ingest-pipeline -b add-ingest-pipeline
```

Seguí estas reglas:

- Usá un worktree y una rama por change, con el nombre de la change.
- Los contratos compartidos (Protocols y modelos Pydantic) se commitean en `main` antes de abrir una tanda.
- Integrá de a una change por vez y corré `/verify` después de cada merge.
