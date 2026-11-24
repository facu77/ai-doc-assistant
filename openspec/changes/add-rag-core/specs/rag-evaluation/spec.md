# Spec Delta

## Purpose

Medir la calidad de recuperación y de respuesta del RAG contra un set de oro de solo lectura, registrar cada corrida, comparar variantes de a una variable y bloquear las regresiones contra una línea base versionada.

## ADDED Requirements

### Requirement: Formato del set de oro
El set de oro SHALL vivir en `evals/golden/questions.jsonl`, con una pregunta por línea y los campos `id`, `question`, `expected_answer`, `expected_sources` (lista de `doc_id` y página) y `tags`. Las preguntas sin respuesta en el corpus MUST llevar el tag `unanswerable` y una lista `expected_sources` vacía. El evaluador MUST rechazar un archivo con líneas inválidas o `id` repetidos.

#### Scenario: Línea inválida
- **WHEN** la línea 12 del archivo no tiene el campo `question`
- **THEN** la evaluación falla antes de llamar al RAG con un error que indica la línea 12 y el campo faltante

#### Scenario: Composición del set
- **WHEN** se valida el set de oro versionado
- **THEN** tiene entre 40 y 60 preguntas ficticias, y entre el 15% y el 20% llevan el tag `unanswerable` (propuesto)

### Requirement: Set de oro de solo lectura
La evaluación MUST NOT modificar ningún archivo de `evals/golden/`, y SHALL aceptar otro archivo con el mismo formato (`--golden <ruta>`) para evaluar contra un set externo al repositorio.

#### Scenario: Corrida sin efectos sobre el set
- **WHEN** se corre la evaluación completa
- **THEN** el hash de cada archivo de `evals/golden/` es el mismo antes y después

#### Scenario: Set externo
- **WHEN** se corre con `--golden` apuntando a un archivo fuera del repositorio
- **THEN** la corrida registra el hash del set y la cantidad de preguntas, y no copia el texto de las preguntas a `evals/runs/`

### Requirement: Métricas de recuperación
La evaluación SHALL calcular recall@5 y MRR sobre las preguntas con respuesta, comparando el top-5 recuperado con `expected_sources` por `doc_id` y página.

#### Scenario: Cálculo sobre un set de ejemplo
- **WHEN** se evalúan 2 preguntas con respuesta, la primera con su única fuente esperada en el rango 1 y la segunda con su única fuente esperada en el rango 4
- **THEN** recall@5 es 1,0 y MRR es 0,625

#### Scenario: Preguntas sin respuesta excluidas
- **WHEN** el set incluye preguntas con el tag `unanswerable`
- **THEN** esas preguntas no participan en recall@5 ni en MRR

### Requirement: Métricas de generación con juez
La evaluación SHALL calcular la fidelidad (proporción de afirmaciones sustentadas por los fragmentos citados) y la relevancia de la respuesta (de 0 a 1) usando un modelo juez configurable por separado del generador. Una evaluación del juez que no se pueda interpretar MUST contarse como error del juez y MUST NOT contarse como puntaje 0.

#### Scenario: Respuesta fiel
- **WHEN** el juez marca como sustentadas 4 de las 5 afirmaciones de una respuesta
- **THEN** la fidelidad de esa pregunta es 0,8

#### Scenario: Salida inválida del juez
- **WHEN** el juez devuelve dos veces una salida que no cumple el esquema
- **THEN** la pregunta queda marcada como error del juez, se excluye del promedio y el reporte informa la cantidad de errores del juez

### Requirement: Citas, abstención y latencia
La evaluación SHALL reportar la corrección de citas (proporción de citas que apuntan a una fuente esperada), la precisión de abstención en las preguntas `unanswerable`, la tasa de abstenciones indebidas en las preguntas con respuesta y la latencia p50 y p95 de punta a punta, descartando 3 preguntas de calentamiento.

#### Scenario: Abstención correcta
- **WHEN** el sistema se abstiene en 9 de 10 preguntas `unanswerable` y en 1 de 40 preguntas con respuesta
- **THEN** la precisión de abstención es 0,9 y la tasa de abstenciones indebidas es 0,025

### Requirement: Umbrales de la línea base
La variante `baseline` MUST cumplir los umbrales acordados sobre el set de oro (propuesto: recall@5 de 0,80 o más, fidelidad de 0,85 o más, corrección de citas de 0,90 o más, precisión de abstención de 0,80 o más y p95 de 4 s o menos en local).

#### Scenario: Corrida de la línea base
- **WHEN** se corre la evaluación de `baseline` con el proveedor acordado
- **THEN** todas las métricas cumplen sus umbrales y el resultado se guarda como `evals/baseline.json`

### Requirement: Registro de cada corrida
Cada corrida SHALL escribir un JSON en `evals/runs/` con fecha, commit, variante, configuración, hash del set, métricas agregadas y resultados por pregunta. Si `MLFLOW_TRACKING_URI` está definida, la corrida MUST registrarse además en MLflow con sus parámetros, métricas y el JSON como artefacto.

#### Scenario: Corrida sin MLflow
- **WHEN** se corre la evaluación sin `MLFLOW_TRACKING_URI`
- **THEN** se genera el JSON en `evals/runs/` y la corrida termina sin errores

#### Scenario: Corrida con MLflow
- **WHEN** se corre con `MLFLOW_TRACKING_URI` apuntando a un servidor disponible
- **THEN** existe un run con el nombre de la variante, las mismas métricas que el JSON y el JSON adjunto como artefacto

### Requirement: Gate de regresión
Con `--check`, la evaluación SHALL comparar cada métrica con `evals/baseline.json` y MUST terminar con código de salida distinto de 0 si alguna empeora más que su tolerancia (propuesto: 0,02 absoluto en las métricas de calidad y 20% relativo en el p95).

#### Scenario: Regresión
- **WHEN** recall@5 baja de 0,84 en la línea base a 0,79
- **THEN** la corrida termina con código 1 e informa la métrica, el valor de base, el valor nuevo y la tolerancia

#### Scenario: Variación dentro de la tolerancia
- **WHEN** recall@5 baja de 0,84 a 0,83 y las demás métricas no empeoran
- **THEN** la corrida termina con código 0

#### Scenario: Falta la línea base
- **WHEN** se corre con `--check` y `evals/baseline.json` no existe
- **THEN** la corrida termina con código distinto de 0 y un mensaje que indica cómo generar la línea base

### Requirement: Comparación de variantes
La evaluación SHALL aceptar `--variant <nombre>` para correr una variante del pipeline, y cada variante distinta de `baseline` MUST diferir de ella en una sola etapa.

#### Scenario: Corrida de una variante
- **WHEN** se corre con `--variant hybrid_rrf`
- **THEN** el JSON de la corrida registra la variante y la etapa que difiere de `baseline`

#### Scenario: Reproducibilidad de las métricas deterministas
- **WHEN** se corre dos veces la misma variante con el proveedor de modelo determinista de pruebas
- **THEN** recall@5, MRR, corrección de citas y precisión de abstención son idénticas en ambas corridas
