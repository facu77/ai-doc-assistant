# Design

## Context

`add-api-and-gateway` crea los Dockerfiles de `services/ai` y `services/gateway` y suma `ai`, `gateway` y `qdrant` a `deploy/compose.yaml` con healthchecks. `add-rag-core` agrega `evals/run_eval.py --check` contra `evals/baseline.json`. Hoy la CI es un único job que corre `make verify`, con acciones fijadas por tag, y `scripts/eval.sh` sale en verde si no hay evaluador. Las métricas de `evals/RESULTS.md` son recall@5, MRR, fidelidad, relevancia y p95.

## Goals / Non-Goals

**Goals:**
- Un comando para levantar el stack (`make up`) y otro para el cluster (`make kind-up`), desde un clon limpio y sin claves.
- Un gate de evaluación determinista: dos corridas sobre el mismo commit dan las mismas métricas y no gastan tokens.
- PR en verde en 15 minutos o menos (propuesto), con caché caliente.
- Un PR rojo reproducible por una regresión de calidad, enlazado desde el README.

**Non-Goals:**
- Despliegue en una nube real, Ingress con TLS, autoscaling, GitOps.
- Observabilidad (MLflow, Grafana) y escaneo de seguridad: van en `add-observability-security`.
- Gatear latencia en CI: el runner compartido es demasiado ruidoso.

## Decisions

- **Imágenes**: build multi-stage (en `ai`, `uv sync --frozen --no-dev` en la etapa de build y solo el venv en runtime; en `gateway`, `npm ci` y `tsc` en build y `npm ci --omit=dev` en runtime). Base fijada por `tag@sha256`, `USER` con UID 10001, `HEALTHCHECK` contra `/health`. Tamaño máximo propuesto: `ai` ≤ 1,2 GB (por OCR) y `gateway` ≤ 250 MB, chequeado en CI.
- **Compose**: `depends_on` con `condition: service_healthy` (qdrant → ai → gateway). `make up` usa `docker compose up -d --build --wait --wait-timeout 120` y `.env` es opcional (`env_file` con `required: false`), así que sin `.env` arranca con los valores de `.env.example`, es decir, `LLM_PROVIDER=fake`.
- **kind**: `deploy/k8s/kind-config.yaml` con la imagen de nodo fijada por digest y `extraPortMappings` para exponer el gateway en `localhost:8080` sin `port-forward`. `scripts/kind-up.sh` es idempotente: crea el cluster si no existe, hace `kind load docker-image` y `helm upgrade --install --wait --timeout 5m`.
- **Chart Helm** en `deploy/k8s/chart` (pendiente de la pregunta 1): Deployments de `ai` y `gateway` y StatefulSet de Qdrant con PVC. Cada contenedor tiene requests y limits, `runAsNonRoot`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]` y `readOnlyRootFilesystem` con un `emptyDir` en `/tmp`. La readiness chequea las dependencias y la liveness solo el proceso, para que una caída de Qdrant saque al pod del Service sin reiniciarlo en bucle.
- **Config y secretos**: la configuración no sensible va a un ConfigMap desde `values.yaml`. El Secret lo crea `kind-up.sh` con `kubectl create secret generic --from-env-file` filtrando solo las claves `*_API_KEY` de `.env`. El chart nunca renderiza un Secret con datos: solo lo referencia por nombre.
- **Smoke**: `scripts/smoke.sh <base_url>` es el mismo para Compose y kind. Espera `/health` hasta 60 s, sube un documento ficticio de `deploy/smoke/`, hace una consulta y verifica que la respuesta tenga al menos una cita. Sale con código distinto de 0 e imprime qué paso falló.
- **Jobs de CI**: `lint` (ruff, mypy, eslint, prettier, tsc y `openspec validate`), `test` (pytest y vitest), `build` (buildx con `cache-from/to: type=gha`, exporta las imágenes como artefacto), `eval` (gate) y `kind-smoke` (descarga las imágenes de `build`). `verify.sh` sigue siendo la fuente local; la CI llama a los mismos comandos por paso.
- **Gate determinista y barato**: perfil `ci` con `LLM_PROVIDER=fake` y embeddings de un modelo local chico con revisión fijada, en CPU y con `torch` y BLAS en un solo hilo. Solo se gatean métricas de recuperación (recall@5 y MRR), que no dependen del LLM. El modelo se cachea con `actions/cache` usando como clave el nombre y la revisión. Fidelidad y relevancia (juez real) corren en `eval-full.yml`, que se dispara a mano y usa la clave como secreto del repo.
- **Regla del gate**: falla si alguna métrica gateada es menor que `baseline − tolerancia`, con tolerancia propuesta de 0,02 absoluta. Una mejora no actualiza la línea base sola: hay que commitearla con la corrida que la produjo. En CI se exporta `EVAL_REQUIRED=1`, y en ese modo `eval.sh` falla si faltan `run_eval.py` o la línea base, en vez de salir en verde.
- **Demostración**: la rama `demo/eval-regression` baja `top_k` de recuperación a 1. Su PR queda rojo en el job `eval` y el README enlaza ese PR y uno verde.
- **Seguridad del workflow**: `permissions: contents: read` a nivel workflow. Acciones fijadas por SHA completo, con el tag en un comentario, y Dependabot semanal para `github-actions` y `docker`. `concurrency` cancela corridas viejas del mismo PR. `timeout-minutes` en cada job.
- **GHCR**: el job `publish` corre solo en `push` a `main`, si `vars.PUBLISH_IMAGES == 'true'` y si todos los jobs pasaron. Es el único con `packages: write`. Publica con los tags `sha-<corto>` y `main`. Nunca corre en PRs.
- **Arranque temprano (Tanda B)**: el esqueleto (workflow por jobs, chart, `kind-up.sh` y `smoke.sh`) se puede construir con una imagen de ejemplo mínima con `/health`. Cuando llegan `add-api-and-gateway` y `add-rag-core`, se reemplaza por los servicios reales y se activan los pasos de ingesta, consulta y gate.

## Risks / Trade-offs

- **Gate solo de recuperación**: no detecta regresiones de generación. Se compensa con `eval-full.yml` antes de actualizar números del README.
- **Determinismo de embeddings en CPU**: puede haber diferencias mínimas entre versiones de BLAS. Se fijan las versiones en `uv.lock`, y la tolerancia absorbe ruido menor que 0,02.
- **Tiempo del job de kind** (de 5 a 8 minutos): se cachea la imagen de nodo y se reusan las imágenes de `build` en vez de reconstruirlas.
- **Duplicación entre `verify.sh` y los jobs**: se acepta a cambio de feedback paralelo. Un test chequea que la CI corra los mismos comandos.
