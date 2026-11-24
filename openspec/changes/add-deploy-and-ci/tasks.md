# Tasks

## 1. Versiones y esqueleto (puede arrancar en Tanda B)

- [ ] 1.1 Usar `docs-checker` para confirmar la sintaxis vigente de Compose (`depends_on.condition`, `--wait`, `env_file.required`), kind (`kind-config`, `kind load`), Helm 3 y las acciones (`setup-uv`, `setup-node`, `docker/build-push-action`, `helm/kind-action`, `actions/cache`), y resolver los SHA de cada acción y los digests de las imágenes base
- [ ] 1.2 Fijar las versiones de kind, kubectl y Helm en el `Makefile` y en la CI
- [ ] 1.3 Crear una imagen de ejemplo mínima con `/health` para construir el chart, `kind-up.sh`, `smoke.sh` y los jobs antes de que estén los servicios reales

## 2. Tests y chequeos primero

- [ ] 2.1 Usar `test-writer` para escribir los chequeos de los escenarios: UID distinto de 0, `FROM` con digest y tamaño de imágenes; chart renderizado con probes, recursos, `securityContext` y sin Secret con datos; acciones fijadas por SHA; paridad entre `verify.sh` y la CI
- [ ] 2.2 Escribir los tests del gate con resultados sintéticos: dentro de la tolerancia, regresión, mejora sin tocar la línea base, y falta del evaluador o de la línea base con `EVAL_REQUIRED=1`
- [ ] 2.3 Escribir `scripts/smoke.sh` y confirmar que falla contra un stack apagado y nombra el paso
- [ ] 2.4 Confirmar que todos los chequeos fallan por la razón correcta

## 3. Implementación

- [ ] 3.1 Endurecer los `Dockerfile` de `ai` y `gateway` (multi-stage, usuario no root, digest y `HEALTHCHECK`)
- [ ] 3.2 Completar `deploy/compose.yaml` (orden por healthchecks, `.env` opcional) y `make up` con `--wait`
- [ ] 3.3 Chart en `deploy/k8s/chart`, `kind-config.yaml`, `scripts/kind-up.sh` (Secret desde `.env`) y los targets `kind-up`, `kind-down` y `smoke`
- [ ] 3.4 Modo estricto `EVAL_REQUIRED=1` en `scripts/eval.sh` y perfil `ci` del gate (LLM `fake` y embeddings locales fijados), coordinado con `add-rag-core`
- [ ] 3.5 Reescribir `.github/workflows/ci.yml` por jobs (lint, test, build, eval, kind-smoke y publish), con caché, SHA, `permissions`, `concurrency` y `timeout-minutes`
- [ ] 3.6 `eval-full.yml` manual con juez real y `.github/dependabot.yml`
- [ ] 3.7 Rama `demo/eval-regression` con su PR rojo, y un PR verde de referencia

## 4. Cierre

- [ ] 4.1 Correr `/verify` en verde, más `make up && make smoke` y `make kind-up && make smoke` desde un clon limpio
- [ ] 4.2 Medir dos corridas del job `eval` sobre el mismo commit y la duración del pipeline con la caché caliente
- [ ] 4.3 Pasar `reviewer` sobre el diff y resolver los hallazgos
- [ ] 4.4 Actualizar `deploy/README.md` y el README raíz ("levantar en un comando", badge de CI y enlaces al PR verde y al PR rojo)
