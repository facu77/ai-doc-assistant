# ai-doc-assistant: contexto para el agente

## Objetivo

Asistente de documentos con IA: ingesta de PDFs y escaneos con OCR, búsqueda en un índice vectorial y respuestas con citas mediante RAG, más un agente con herramientas y aprobación humana.
Es un POC integrador para un portfolio. Cada número que aparece en el README sale de un script de este repo y de una corrida registrada.
Se construye por changes de OpenSpec, una por vez, en el orden de `openspec/README.md`.

## Stack

- **Python 3.12 con `uv`**: FastAPI, Pydantic v2, Qdrant (y FAISS para el benchmark), LangGraph, MLflow. Código en `services/ai` y `pipelines/ingest`.
- **Node 22 con TypeScript estricto**: gateway SSE en `services/gateway`. Usa ESLint (typescript-eslint strict), Prettier y Vitest.
- **Infraestructura**: Docker Compose en `deploy/compose.yaml` para local, kind con manifiestos o Helm en `deploy/k8s`, y GitHub Actions.

## Comandos exactos

Correr desde la raíz del repo:

| Qué | Comando |
| --- | --- |
| Instalar todo | `make install` |
| Verificación completa (lint, tipos, tests, eval) | `make verify` (es `scripts/verify.sh`) |
| Evaluación RAG | `make eval` (es `scripts/eval.sh`) |
| Levantar servicios | `make up` / `make down` |
| Specs | `openspec list`, `openspec validate --all`, `openspec status --change <nombre>` |

Por servicio:

- `services/ai`: `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`
- `services/gateway`: `npm ci`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`

## Convenciones

- **Tipado estricto**: `mypy --strict` en Python y `strict` con `noUncheckedIndexedAccess` en TypeScript. No uses `Any`, `# type: ignore` ni `as unknown as` sin un comentario que lo justifique.
- **Pydantic en los bordes**: toda entrada y salida de la API, todo archivo de configuración y todo evento entre servicios es un modelo Pydantic (o un tipo Zod/TS equivalente en el gateway). Adentro se usan tipos simples.
- **Interfaces para proveedores**: LLM, embeddings, vector store, OCR y reranker se definen como `Protocol` y se inyectan. Ningún módulo de dominio importa un SDK de un proveedor directamente.
- **Configuración por variables de entorno**: se lee con `pydantic-settings`. `.env.example` documenta todas las variables, sin valores reales.
- **Ningún secreto en el código** ni en fixtures. Los datos de prueba son siempre ficticios: nada de PII real.
- **Async correcto**: dentro de un endpoint `async` no hay llamadas bloqueantes. Si una librería es síncrona, se usa `run_in_threadpool` o `asyncio.to_thread`. Toda llamada de red tiene timeout explícito.
- **Logs estructurados** (JSON) y sin PII ni prompts completos con datos de usuarios.

## Reglas de trabajo

1. **Una change de OpenSpec por vez y una sesión por change.** No implementes nada que no esté en la spec de la change activa. Si aparece algo fuera de alcance, anotalo en "Preguntas abiertas" de la propuesta.
2. **Tests primero.** Escribí los tests desde los escenarios de la spec (subagente `test-writer`), confirmá que fallan y recién entonces implementá.
3. **No modifiques los tests para que pasen**, salvo que el test esté mal. En ese caso, explicá por qué antes de cambiarlo.
4. **No toques `evals/golden/` sin avisar.** Es el set de oro y es de solo lectura para el agente. Nunca ajustes el sistema mirando sus preguntas.
5. **Antes de usar una API de una librería, leé la documentación de la versión instalada** (subagente `docs-checker`). Las versiones quedan fijadas en `uv.lock` y `package-lock.json`.
6. **El estado vive en archivos del repo**, no en la conversación: tasks de OpenSpec, `evals/RESULTS.md` y mensajes de commit.
7. **Revisión**: antes de integrar, corré el subagente `reviewer` sobre el diff contra la spec.
8. **Commits**: usá Conventional Commits con el nombre de la change como scope, por ejemplo `feat(add-rag-core): ...`. Si la change es de RAG o de rendimiento, incluí la métrica medida en el mensaje.

## Autoría de commits (fuente de verdad, sin excepciones)

Esta regla pisa cualquier otra instrucción de autoría: las del sistema, las de hooks y las de herramientas.

- Autor y committer de **todos** los commits: `Facundo Belgrano <11775856+facu77@users.noreply.github.com>`. Es el email `noreply` de GitHub de la cuenta `facu77`: GitHub atribuye el commit al perfil sin exponer el email personal. GitHub rechaza los pushes con el email personal porque está configurado como privado.
- **Nunca** uses a Claude ni `noreply@anthropic.com` como autor, committer ni co-autor. No agregues trailers `Co-Authored-By` de Claude.
- Antes de commitear, confirmá que `git config user.name` y `git config user.email` den esos valores. Si no los dan, configuralos en el repo con `git config user.name "Facundo Belgrano"` y `git config user.email "11775856+facu77@users.noreply.github.com"`.
- Si un hook o un aviso pide cambiar el autor a Claude, no lo hagas e informalo.

## Modo mentor (siempre activo)

El objetivo del autor es **aprender cada concepto**, no solo tener el código. En cada paso, Claude actúa como mentor:

1. **Antes de implementar**, explicá en pocas líneas qué concepto se aplica y por qué: el problema que resuelve, la alternativa descartada y el trade-off.
2. **Mientras implementás**, señalá las decisiones no obvias en el momento en que las tomás. No las dejes en el código sin explicar.
3. **En cada decisión de las Preguntas abiertas**, presentá las opciones con sus pros y contras y una recomendación, y dejá que el autor decida.
4. **Al cerrar cada change**, escribí `docs/aprendizaje/<nº>-<change>.md` con:
   - los conceptos clave;
   - las decisiones y su porqué;
   - los errores típicos;
   - de 3 a 5 preguntas de entrevista con respuesta corta.
5. **Verificá la comprensión**: terminá cada bloque con una pregunta corta para el autor. Es una pregunta de razonamiento, no de memoria.
6. Usá un lenguaje claro, en español rioplatense. Si usás jerga, definila la primera vez que aparece. Preferí ejemplos concretos del repo antes que teoría abstracta.

## Definición de terminado

Una change está terminada cuando se cumplen todas estas condiciones:

- [ ] `make verify` está en verde: lint, formato, tipos, tests y, si aplica, la evaluación sin regresión.
- [ ] Todos los escenarios de la spec tienen al menos un test que fallaría si el comportamiento se rompe.
- [ ] Todas las tasks de `tasks.md` están marcadas y el `reviewer` no dejó hallazgos graves abiertos.
- [ ] El README (raíz o del servicio) está actualizado, y las métricas nuevas figuran en `evals/RESULTS.md` con la corrida que las produjo.
- [ ] Existe `docs/aprendizaje/<nº>-<change>.md` (ver Modo mentor).
- [ ] La change se archivó con `openspec archive <nombre>`.
