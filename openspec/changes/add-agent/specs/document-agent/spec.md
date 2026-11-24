# Spec Delta

## Purpose

Resolver tareas de varios pasos sobre los documentos indexados con un agente que usa herramientas, respeta límites de ejecución, pide aprobación humana antes de cualquier acción con efectos, cita sus fuentes y cuya trayectoria se evalúa con métricas reproducibles.

## ADDED Requirements

### Requirement: Herramientas de consulta de documentos
El agente SHALL disponer de las herramientas de solo lectura `search_documents`, `get_document_page`, `summarize_document` y `compare_documents`, MUST validar sus argumentos antes de ejecutarlas y MUST devolver los errores de una herramienta al agente como una observación tipada, sin interrumpir la corrida.

#### Scenario: Búsqueda con filtro
- **WHEN** el agente llama a `search_documents` con una consulta y un filtro `doc_id = X`
- **THEN** la observación contiene solo fragmentos de X, cada uno con `doc_id`, `page` y `chunk_id`

#### Scenario: Página fuera de rango
- **WHEN** el agente llama a `get_document_page` con la página 99 de un documento de 5 páginas
- **THEN** recibe una observación de error que indica el rango válido (1 a 5) y la corrida sigue en estado `running`

#### Scenario: Argumentos inválidos
- **WHEN** el modelo propone `compare_documents` con un solo `doc_id`
- **THEN** la herramienta no se ejecuta, el agente recibe un error de validación como observación y la llamada cuenta para el límite de llamadas

### Requirement: Respuesta final con citas verificables
Toda respuesta final con contenido SHALL incluir al menos una cita `[doc_id, página]`, y cada cita MUST corresponder a una fuente que el agente observó en esa misma corrida. Si no hay evidencia suficiente, el agente MUST abstenerse en lugar de responder sin citas.

#### Scenario: Respuesta citada
- **WHEN** el agente responde una pregunta después de leer la página 3 del documento `contrato-a`
- **THEN** la respuesta incluye la cita `[contrato-a, 3]` y todas sus citas están entre las fuentes observadas

#### Scenario: Cita no observada
- **WHEN** el modelo produce una respuesta final que cita `[manual-z, 7]` y esa fuente no aparece en ninguna observación de la corrida
- **THEN** esa cita se descarta, y si no queda ninguna cita válida la respuesta final es una abstención

#### Scenario: Sin evidencia
- **WHEN** se pregunta por un tema que no aparece en ningún documento del corpus
- **THEN** la respuesta final es una abstención explícita, sin citas y con estado `completed`

### Requirement: Aprobación humana para acciones con efectos
Una herramienta marcada con efectos (`create_ticket`) MUST NOT ejecutarse sin una aprobación humana explícita. El agente SHALL pausar la corrida en estado `awaiting_approval` y mostrar la herramienta y los argumentos propuestos, y al reanudar MUST aplicar la decisión recibida: aprobar, rechazar o editar.

#### Scenario: Aprobación
- **WHEN** el agente propone `create_ticket` y la persona aprueba
- **THEN** el ticket se crea exactamente una vez en el destino falso con los argumentos propuestos, y la corrida continúa hasta su respuesta final

#### Scenario: Rechazo
- **WHEN** el agente propone `create_ticket` y la persona rechaza
- **THEN** el destino falso no recibe ningún ticket, el agente recibe el rechazo como observación y su respuesta final informa que la acción no se realizó

#### Scenario: Edición
- **WHEN** la persona responde con la decisión `edit` y un título distinto
- **THEN** el ticket se crea una sola vez con el título editado, y no con el propuesto por el modelo

#### Scenario: Edición inválida
- **WHEN** la persona edita los argumentos con un valor que no cumple el esquema de la herramienta
- **THEN** la decisión se rechaza con un error de validación, no se ejecuta nada y la corrida sigue en `awaiting_approval`

#### Scenario: Aprobación repetida
- **WHEN** llega dos veces la misma aprobación para la misma acción pendiente
- **THEN** el ticket se crea una sola vez y la segunda solicitud se rechaza por conflicto de estado

#### Scenario: Límite con acción pendiente
- **WHEN** una corrida se detiene por un límite mientras tiene una acción con efectos propuesta y no aprobada
- **THEN** la acción no se ejecuta

### Requirement: Estado persistido por hilo
El sistema SHALL persistir el estado de cada corrida por identificador de hilo, de forma que una corrida en `awaiting_approval` MUST poder reanudarse después de que terminó la request que la inició y después de un reinicio del servicio.

#### Scenario: Reanudación después de un reinicio
- **WHEN** una corrida queda en `awaiting_approval`, el servicio se reinicia y después llega la aprobación
- **THEN** la corrida se reanuda desde el punto de pausa, sin repetir las llamadas a herramientas ya hechas, y termina en `completed`

#### Scenario: Hilos aislados
- **WHEN** hay dos corridas en pausa al mismo tiempo y se aprueba solo una
- **THEN** solo esa corrida avanza y la otra sigue en `awaiting_approval` con su estado intacto

### Requirement: Límites de ejecución
Cada corrida SHALL respetar un máximo de pasos del agente (propuesto: 8), de llamadas a herramientas (propuesto: 12), de tokens (propuesto: 20 mil) y de tiempo activo (propuesto: 60 segundos, sin contar la espera de aprobación), configurables por entorno. Al alcanzar cualquiera, la corrida MUST detenerse con estado `stopped`, el motivo en `stop_reason` y una respuesta parcial que cite solo las fuentes observadas.

#### Scenario: Máximo de pasos
- **WHEN** el modelo pide herramientas sin parar y `AGENT_MAX_STEPS=8`
- **THEN** la corrida termina con `stopped`, `stop_reason=max_steps`, como mucho 8 pasos registrados y una respuesta parcial

#### Scenario: Presupuesto de tokens
- **WHEN** el uso acumulado de tokens de la corrida supera `AGENT_MAX_TOKENS`
- **THEN** no se hace ninguna llamada más al modelo y la corrida termina con `stop_reason=max_tokens`

#### Scenario: Presupuesto de tiempo
- **WHEN** el tiempo activo de la corrida supera `AGENT_MAX_SECONDS`
- **THEN** la corrida termina con `stop_reason=max_time`, y el tiempo que pasó en `awaiting_approval` no se descontó del presupuesto

### Requirement: Detección de bucles
El agente MUST NOT reejecutar una llamada idéntica (misma herramienta y mismos argumentos) dentro de una corrida, y SHALL detener la corrida con `stop_reason=loop_detected` cuando el modelo propone la misma llamada por tercera vez (propuesto).

#### Scenario: Llamada repetida
- **WHEN** el modelo propone dos veces `get_document_page(doc_id="manual-b", page=2)`
- **THEN** la herramienta se ejecuta una sola vez y la segunda observación repite el resultado con una advertencia de repetición

#### Scenario: Bucle
- **WHEN** el modelo propone la misma llamada por tercera vez
- **THEN** la corrida termina con `stopped`, `stop_reason=loop_detected` y una respuesta parcial

### Requirement: Trayectoria registrada sin contenido sensible
El sistema SHALL registrar por cada corrida la trayectoria ordenada (herramienta, argumentos validados, resultado resumido, tokens, latencia y decisiones de aprobación), y MUST NOT registrar en los logs el texto completo de los prompts ni de los documentos.

#### Scenario: Consulta de la trayectoria
- **WHEN** termina una corrida con 3 llamadas a herramientas
- **THEN** su estado expone las 3 llamadas en orden, con su resultado resumido y sus métricas

#### Scenario: Logs sin contenido
- **WHEN** se completa una corrida cuya pregunta contiene `secreto-de-prueba`
- **THEN** la cadena `secreto-de-prueba` no aparece en ningún log

### Requirement: API de corridas del agente
El servicio SHALL exponer la creación de corridas (`POST /agent/runs`), la consulta de estado (`GET /agent/runs/{run_id}`) y el envío de decisiones de aprobación (`POST /agent/runs/{run_id}/approval`), con entradas y salidas validadas, y MUST responder con errores tipados ante corridas inexistentes o decisiones fuera de estado.

#### Scenario: Creación de una corrida
- **WHEN** se envía `POST /agent/runs` con una pregunta válida
- **THEN** se responde 202 con `run_id` y estado `running`, sin esperar a que la corrida termine

#### Scenario: Consulta de una corrida en pausa
- **WHEN** se consulta una corrida en `awaiting_approval`
- **THEN** la respuesta incluye la herramienta y los argumentos pendientes de aprobación

#### Scenario: Corrida inexistente
- **WHEN** se consulta o se aprueba un `run_id` que no existe
- **THEN** se responde 404 con un error tipado

#### Scenario: Decisión fuera de estado
- **WHEN** se envía una decisión de aprobación a una corrida que no está en `awaiting_approval`
- **THEN** se responde 409 y el estado de la corrida no cambia

### Requirement: Ejecución determinista sin red
El agente SHALL poder ejecutarse con un modelo falso que emite decisiones guionadas (llamadas a herramientas y respuesta final), sin acceso a red, y MUST producir la misma trayectoria para el mismo guion.

#### Scenario: Guion reproducible
- **WHEN** se corre dos veces la misma pregunta con el mismo guion del modelo falso
- **THEN** ambas corridas tienen la misma secuencia de herramientas, los mismos argumentos y la misma respuesta final

### Requirement: Evaluación de trayectorias
El repositorio SHALL incluir `evals/agent/cases.jsonl` con entre 15 y 20 casos ficticios y un script que, por cada caso, compare la trayectoria con la esperada y MUST reportar la tasa de éxito de tarea, la coincidencia de trayectoria (exacta y por subsecuencia), la precisión de llamadas a herramientas, los pasos por tarea (media y p95) y la tasa de aprobación pedida correctamente, en un archivo versionable.

#### Scenario: Composición del set de casos
- **WHEN** se valida `evals/agent/cases.jsonl`
- **THEN** tiene entre 15 y 20 casos, cada uno con la secuencia o el conjunto de herramientas esperado, el modo de comparación, las propiedades finales esperadas y si se espera aprobación, e incluye al menos 3 casos con aprobación (con aprobación, rechazo y edición), 2 de abstención y 2 que tocan un límite

#### Scenario: Corrida determinista
- **WHEN** se corre la evaluación en modo determinista con el modelo falso
- **THEN** se genera un JSON y una tabla Markdown con las métricas, y dos corridas seguidas dan los mismos números

#### Scenario: Ninguna acción sin aprobación
- **WHEN** se corre la evaluación en cualquier modo
- **THEN** la cantidad de acciones con efectos ejecutadas sin aprobación es 0, y si no lo es la evaluación falla

#### Scenario: Umbrales de aceptación
- **WHEN** se corre la evaluación con el modelo real acordado
- **THEN** se cumplen los umbrales acordados (propuestos: éxito de tarea de 0,80 o más, coincidencia por subsecuencia de 0,80 o más, precisión de herramientas de 0,85 o más, aprobación correcta de 1,00 y media de 5 pasos o menos), y la corrida queda registrada en `evals/RESULTS.md`
