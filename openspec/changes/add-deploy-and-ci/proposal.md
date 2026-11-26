# Proposal

## Why

El POC tiene que poder levantarlo otra persona con un comando y tiene que defenderse solo de las regresiones. Hoy `deploy/compose.yaml` está vacío, `deploy/k8s/` no existe y la CI corre `make verify` en un único job donde el gate de evaluación pasa en verde aunque no haya evaluador. Sin un despliegue reproducible y un pipeline que falle cuando baja la calidad del RAG, los números del README no son creíbles.

## What Changes

- `make up` levanta todo el stack local con Compose desde un clon limpio, con orden de arranque por healthchecks y `.env` opcional (por defecto, `LLM_PROVIDER=fake`). `make down` lo baja.
- Endurecimiento de las imágenes de `services/ai` y `services/gateway`: multi-stage, usuario no root, imagen base fijada por digest y `HEALTHCHECK`.
- Cluster local con kind: `make kind-up` crea el cluster, carga las imágenes y despliega un chart en `deploy/k8s/` con probes, requests y limits, ConfigMap y Secret creados desde el entorno (ningún secreto en el repo). `make kind-down` lo borra.
- `scripts/smoke.sh <base_url>`: prueba de humo común a Compose y kind (health, ingesta de un documento ficticio y una consulta con el LLM `fake`).
- Pipeline de GitHub Actions separado en jobs: lint y tipos, tests, build de imágenes, gate de evaluación determinista y barato, y smoke test en kind. Acciones fijadas por SHA, permisos mínimos y caché de dependencias, imágenes y modelo de embeddings.
- Gate de evaluación: el PR falla si una métrica gateada cae por debajo de la línea base menos la tolerancia. Se demuestra con un PR verde y un PR rojo por una regresión intencional.
- Publicación opcional de imágenes en GHCR, solo en `main` y detrás de una variable del repo.

## Capabilities

### New Capabilities
- `deployment`: arranque local reproducible con Compose, imágenes endurecidas, despliegue en kind con probes y límites, configuración y secretos desde el entorno, y smoke test.
- `ci-pipeline`: pipeline de integración continua con jobs separados, gate de evaluación determinista contra la línea base, smoke test en kind, caché, acciones fijadas, permisos mínimos y publicación de imágenes condicionada.

### Modified Capabilities

## Impact

- Archivos nuevos: `deploy/k8s/` (chart y `kind-config.yaml`), `scripts/smoke.sh`, `scripts/kind-up.sh`, `.github/dependabot.yml` y `.github/workflows/eval-full.yml` (manual).
- Archivos modificados: `.github/workflows/ci.yml`, `Makefile` (`kind-up`, `kind-down`, `smoke`), `deploy/compose.yaml`, `deploy/README.md`, `scripts/eval.sh` (modo estricto `EVAL_REQUIRED=1`) y los `Dockerfile` que crea `add-api-and-gateway`.
- Depende de `add-api-and-gateway` (Dockerfiles, servicios y `/health`) y de `add-rag-core` (`evals/run_eval.py --check` y `evals/baseline.json`). El esqueleto puede arrancar antes (Tanda B) con un servicio de ejemplo (ver design).
- Herramientas fijadas: kind, kubectl y Helm (versiones en el Makefile y en la CI). No hay dependencias nuevas de Python ni de Node.

## Preguntas abiertas

1. ¿Helm o manifiestos planos con Kustomize en `deploy/k8s`? El design propone Helm por los `values` y por `helm lint`.
2. ~~¿Qué embeddings usa el gate de CI?~~ **Resuelta** en `add-llm-client`: el modelo local `multilingual-e5-small`, en CPU, con la caché del modelo en Actions.
3. ¿Qué tolerancia usamos? El design propone 0,02 absoluto sobre recall@5 y MRR. ¿Gateamos también fidelidad y relevancia (requieren juez real y clave) o las dejamos para el workflow manual?
4. ¿La línea base de CI (perfil `ci`, con LLM `fake`) vive en `evals/baseline.json` junto a la del perfil completo o en un archivo separado? Lo tiene que acordar `add-rag-core`.
5. **¿Fijamos la revisión del modelo de embeddings?** Hoy `LocalEmbedder.from_pretrained` carga `intfloat/multilingual-e5-small` sin `revision=`, o sea, la última versión del repo en Hugging Face. Además, la clave de la caché de CI (`hf-<os>-multilingual-e5-small-v1`) no depende de esa revisión. Si el autor del modelo publica pesos nuevos, cambian los vectores sin que cambie nada en este repo, y la CI podría seguir usando pesos viejos de la caché. La propuesta es agregar `EMBEDDINGS_MODEL_REVISION` (un SHA de commit del repo del modelo), pasarla como `revision=` y usarla en la clave de la caché. Surgió en la revisión de `add-llm-client`.
5. ¿Configuramos branch protection con checks requeridos? Es una acción manual fuera del repo.
6. ¿Activamos la publicación en GHCR para el portfolio o la dejamos apagada?
7. ¿`add-api-and-gateway` expone un endpoint de readiness que chequee Qdrant, o lo agregamos acá (`/ready`)? Sin eso, readiness y liveness quedan iguales.
8. ¿Escaneo de vulnerabilidades de imágenes (por ejemplo Trivy) acá o en `add-observability-security`?
