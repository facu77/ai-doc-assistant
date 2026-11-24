# Set de oro (solo lectura)

Preguntas con respuesta y fuentes esperadas. Contra este set se evalúa el RAG.

Reglas:

- **El agente no modifica nada en esta carpeta sin aviso explícito** (ver CLAUDE.md). La regla de permisos en `.claude/settings.json` pide confirmación para cualquier edición.
- Nunca se ajustan prompts, chunking ni parámetros mirando las preguntas de este set.
- Existe un segundo set **oculto**, fuera del repo, que usa solo el autor para detectar sobreajuste.

Formato (se define en `add-rag-core`): `questions.jsonl`, con una línea por pregunta y los campos `id`, `question`, `expected_answer`, `expected_sources` (doc_id y página) y `tags`.
