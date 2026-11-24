# 00 · Preparación del repo

Qué se hizo en el día 1 y qué conceptos hay detrás. El objetivo es que puedas explicar cada pieza sin mirar el código.

## 1. Desarrollo guiado por specs (OpenSpec)

**Qué es**: antes de escribir código se escribe un contrato de comportamiento. Cada *change* tiene cuatro archivos:

| Archivo | Responde | Ejemplo en el repo |
| --- | --- | --- |
| `proposal.md` | ¿**Por qué** y **qué** cambia? | `openspec/changes/add-llm-client/proposal.md` |
| `specs/<capability>/spec.md` | ¿**Qué** debe hacer el sistema, de forma observable? | Requisitos con `SHALL`/`MUST` y escenarios `WHEN`/`THEN` |
| `design.md` | ¿**Cómo** lo hacemos y qué alternativas descartamos? | Protocol vs. clase abstracta, política de reintentos |
| `tasks.md` | ¿En qué **pasos** lo hacemos? | Checklist que se va tildando |

**Por qué importa con un agente**: un agente de código es muy bueno para *hacer* y malo para saber *cuándo terminó*. Un escenario como "falla 2 veces con 503, después responde → exactamente 3 intentos" es un criterio de aceptación sin ambigüedad. Se convierte directamente en un test.

**Spec ≠ diseño**: la spec no nombra librerías ni clases. Así podés cambiar la implementación (por ejemplo, de `tenacity` a reintentos propios) sin tocar el contrato. Regla rápida: *si la implementación puede cambiar sin que lo note quien usa el sistema, eso no va en la spec*.

**Capability vs. change**: una *capability* (`llm-client`) es un comportamiento duradero del sistema. Una *change* (`add-llm-client`) es el trabajo que la crea o la modifica. Cuando se archiva la change, sus specs pasan a `openspec/specs/` y forman la documentación viva del sistema.

## 2. Gestión de dependencias reproducible

- **`uv`**: gestor de proyectos Python. Crea el entorno virtual (`.venv`), instala dependencias y escribe `uv.lock`.
- **Lockfile** (`uv.lock`, `package-lock.json`): fija la versión **exacta** de cada dependencia, incluidas las transitivas. En `pyproject.toml` declarás `ruff>=0.17.6` (un rango). El lockfile dice "exactamente 0.17.6 con este hash". Sin lockfile, dos personas o la CI pueden instalar versiones distintas, y aparece el clásico "en mi máquina anda".
- **Relación con los agentes**: la regla de CLAUDE.md "leer la documentación de la versión instalada" solo tiene sentido si la versión está fijada. Para eso existe el subagente `docs-checker`.

## 3. Calidad estática: lint, formato y tipos

| Herramienta | Qué detecta | Ejemplo |
| --- | --- | --- |
| `ruff check` (linter) | Errores probables y malas prácticas | Regla `ASYNC`: `time.sleep` dentro de `async def`. Regla `S`: secretos hardcodeados |
| `ruff format` / Prettier (formateador) | Nada: solo uniforma el estilo | Elimina las discusiones de estilo en las revisiones |
| `mypy --strict` / `tsc --strict` (chequeador de tipos) | Inconsistencias de tipos sin ejecutar el código | Pasar `str | None` donde se espera `str` |

`noUncheckedIndexedAccess` (TypeScript) hace que `arr[0]` tenga tipo `T | undefined`. Te obliga a manejar el caso vacío, que es una fuente muy común de errores en producción.

## 4. Tests y "tests primero" (TDD)

El ciclo es **rojo → verde → refactor**: escribís un test que falla, implementás lo mínimo para que pase y después mejorás el código.

**Por qué el test tiene que fallar primero**: un test que nunca viste fallar puede no estar probando nada. Por eso `test-writer` confirma que los tests fallan *por la razón correcta* (falta el comportamiento) y no por un error de sintaxis.

**Fake vs. mock**: un *mock* devuelve lo que vos le decís, y es fácil escribir un test que solo verifica el mock. Un *fake* es una implementación simple pero real. Por ejemplo, un proveedor LLM falso que falla N veces y después responde: ejercita la lógica de verdad.

## 5. Claude Code como herramienta de ingeniería

| Pieza | Concepto | Archivo |
| --- | --- | --- |
| `CLAUDE.md` | Memoria del proyecto: se carga en cada sesión. El estado vive en el repo, no en la conversación | `CLAUDE.md` |
| Subagentes | Un agente con **contexto limpio** y herramientas limitadas. El revisor no escribió el código, así que no comparte sus supuestos | `.claude/agents/*.md` |
| Skills | Procedimientos reutilizables que se invocan como `/verify` | `.claude/skills/*/SKILL.md` |
| Hooks | Código que **el harness** ejecuta ante eventos (antes o después de usar una herramienta). No depende de que el modelo "se acuerde" | `.claude/hooks/` |
| Permisos | `allow` / `ask` / `deny`. Se evalúa primero `deny`, después `ask` y por último `allow` | `.claude/settings.json` |

**Hook vs. instrucción**: "no escribas secretos" en CLAUDE.md es una instrucción que el modelo puede ignorar. `guard_secrets.py` es un control: si detecta una clave, sale con código 2 y Claude Code **bloquea** la escritura. Para las cosas importantes, preferí controles antes que instrucciones.

## 6. Integración continua (CI)

`.github/workflows/ci.yml` corre `make verify` en cada push y en cada PR, en una máquina limpia. Esa máquina limpia es lo que demuestra que el proyecto no depende de algo instalado a mano en tu máquina. CI y local usan **el mismo script** (`scripts/verify.sh`), así que no puede pasar que algo esté verde local y rojo en CI por correr comandos distintos.

Con `permissions: contents: read`, el workflow tiene solo los permisos que necesita. Es el **principio de mínimo privilegio**.

## Errores típicos

- Specs con detalles de implementación, que te atan a una librería.
- Criterios sin número ("rápido", "preciso"), que no se pueden verificar.
- Rangos de versión sin lockfile, que llevan a builds no reproducibles.
- Confiar en instrucciones del prompt para controles de seguridad, en vez de usar hooks o permisos.

## Preguntas de entrevista

1. **¿Por qué separar spec y design?** Para que el contrato de comportamiento sea estable aunque cambie la implementación. Además, la spec es testeable y el design es discutible.
2. **¿Qué problema resuelve un lockfile?** La reproducibilidad: la misma versión exacta de cada dependencia, incluidas las transitivas, en todas las máquinas y en CI.
3. **¿Por qué un subagente revisor distinto del que escribió el código?** Porque el contexto limpio evita el sesgo de confirmación: no hereda los supuestos del autor.
4. **¿Fake o mock para testear reintentos?** Un fake con comportamiento programable. Con un mock es fácil terminar testeando el mock en lugar de la lógica.
5. **¿Por qué CI y local corren el mismo script?** Para eliminar la deriva entre entornos: si pasa local, pasa en CI por las mismas razones.
