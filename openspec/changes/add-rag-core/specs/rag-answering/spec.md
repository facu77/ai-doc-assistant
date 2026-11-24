# Spec Delta

## Purpose

Responder preguntas sobre los documentos indexados con un texto basado solo en los fragmentos recuperados, citando documento y página de cada afirmación, absteniéndose cuando la evidencia no alcanza y entregando la respuesta también de forma incremental.

## ADDED Requirements

### Requirement: Respuesta basada en la evidencia recuperada
El sistema SHALL recuperar los `RAG_TOP_K` fragmentos más relevantes para la pregunta (por defecto 5) y MUST generar la respuesta usando solo esos fragmentos como contexto. La respuesta SHALL incluir el texto, las citas, si hubo abstención, los fragmentos recuperados con su score y la latencia en milisegundos.

#### Scenario: Pregunta con respuesta en el corpus
- **WHEN** se pregunta algo cuya respuesta está en la página 3 de un documento indexado
- **THEN** la respuesta no es una abstención, incluye al menos una cita a ese documento y página, y lista los fragmentos recuperados con su score

#### Scenario: Top-k configurable
- **WHEN** se responde con `RAG_TOP_K=3`
- **THEN** el contexto enviado al modelo contiene exactamente 3 fragmentos

### Requirement: Citas verificables
Cada afirmación de la respuesta SHALL llevar una cita con formato `[doc_id, p. N]`, y toda cita devuelta MUST corresponder a un fragmento recuperado para esa pregunta. Las citas que no correspondan MUST eliminarse de la respuesta y registrarse como inválidas.

#### Scenario: Cita a un fragmento recuperado
- **WHEN** el modelo cita `[doc-a, p. 2]` y ese fragmento estaba entre los recuperados
- **THEN** la cita aparece en la lista de citas con su `doc_id` y su página

#### Scenario: Cita inventada
- **WHEN** el modelo cita `[doc-z, p. 9]` y ningún fragmento recuperado corresponde a ese documento y página
- **THEN** la cita no aparece en la respuesta y se registra un evento de cita inválida

#### Scenario: Respuesta sin citas válidas
- **WHEN** después de validar las citas no queda ninguna
- **THEN** la respuesta se devuelve como abstención

### Requirement: Abstención ante evidencia insuficiente
Cuando la evidencia recuperada no alcance para responder, el sistema SHALL abstenerse con el texto "No encontré información suficiente" y MUST NOT inventar una respuesta. Si ningún fragmento supera el score mínimo `RAG_MIN_SCORE`, el sistema MUST abstenerse sin llamar al modelo de lenguaje.

#### Scenario: Nada relevante en el índice
- **WHEN** se pregunta algo ajeno al corpus y ningún fragmento supera `RAG_MIN_SCORE`
- **THEN** la respuesta es una abstención con el texto "No encontré información suficiente", sin citas, y no hubo ninguna llamada al modelo

#### Scenario: Contexto relacionado pero insuficiente
- **WHEN** hay fragmentos sobre el tema pero ninguno contiene el dato pedido y el modelo indica que no alcanza
- **THEN** la respuesta se marca como abstención con el texto "No encontré información suficiente"

### Requirement: Streaming de la respuesta
El sistema SHALL ofrecer una operación de respuesta en streaming que entregue los tokens en orden y, al final, las citas validadas y un evento de cierre. La concatenación de los tokens MUST ser igual al texto de la respuesta completa equivalente.

#### Scenario: Respuesta incremental
- **WHEN** se pide una respuesta en streaming con el proveedor de modelo determinista de pruebas
- **THEN** se reciben varios eventos de token, luego un evento con las citas y luego un evento de cierre, y el texto concatenado coincide con el de la respuesta no incremental

#### Scenario: Abstención en streaming
- **WHEN** se pide en streaming una pregunta que provoca abstención por score mínimo
- **THEN** se recibe el texto de abstención, una lista de citas vacía y el evento de cierre

### Requirement: Etapas intercambiables por variante
El pipeline SHALL permitir elegir por nombre de variante la estrategia de troceo, de recuperación (vectorial o híbrida léxica más vectorial), de reordenamiento y de reescritura de la consulta, sin cambios de código, y MUST rechazar una variante desconocida.

#### Scenario: Variante de línea base
- **WHEN** se responde con la variante `baseline`
- **THEN** se usa recuperación vectorial sin reordenamiento ni reescritura

#### Scenario: Variante con reordenamiento
- **WHEN** se responde con una variante que activa el reordenamiento con 20 candidatos
- **THEN** se recuperan 20 candidatos y el contexto contiene los `RAG_TOP_K` mejor puntuados por el reordenador

#### Scenario: Variante desconocida
- **WHEN** se pide la variante `no-existe`
- **THEN** la operación falla con un error de configuración que lista las variantes válidas

### Requirement: Fallas del modelo sin respuestas inventadas
Si la llamada al modelo de lenguaje falla después de sus reintentos, el sistema MUST devolver un error tipado y MUST NOT devolver un texto parcial como si fuera una respuesta completa.

#### Scenario: Proveedor caído
- **WHEN** el modelo falla con un error de proveedor en todos los intentos
- **THEN** el consumidor recibe un error tipado del RAG que conserva la causa, y no recibe una respuesta
