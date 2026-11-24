---
name: verify
description: Corre la verificación completa del repo (lint, formato, tipos, tests, validación de OpenSpec y evaluación RAG) y resume qué falló. Úsalo antes de dar por terminada una tarea, después de cada merge y cuando el usuario pida verificar.
argument-hint: "[--skip-eval]"
allowed-tools: Bash(make verify) Bash(./scripts/verify.sh *) Bash(SKIP_EVAL=1 ./scripts/verify.sh)
---

Corré la verificación completa desde la raíz del repo:

- Si los argumentos (`$ARGUMENTS`) incluyen `--skip-eval`, usá `SKIP_EVAL=1 ./scripts/verify.sh`.
- Si no, usá `./scripts/verify.sh`.

Después:

1. Mostrá el bloque "Resumen de verificación" tal cual lo imprime el script.
2. Si algo falló, explicá cada fallo: el paso, el archivo y la línea, la causa probable y la corrección propuesta. Agrupá los errores repetidos.
3. **No arregles nada automáticamente** salvo que el usuario lo haya pedido en esta tarea. Si estás aplicando una change, corregí y volvé a correr la verificación hasta que pase, sin modificar los tests salvo que el test esté mal (en ese caso, explicalo).
4. No digas que algo pasa si el script no lo mostró en verde.
