# Spec Delta

## Purpose

Brindar a todo el servicio de IA un acceso a modelos de lenguaje y de embeddings que no dependa del proveedor, que sea configurable por entorno y que falle de forma acotada y predecible.

## ADDED Requirements

### Requirement: Selección de proveedor por configuración
El sistema SHALL elegir el proveedor y el modelo de LLM a partir de las variables de entorno `LLM_PROVIDER` y `LLM_MODEL`, sin cambios de código, y MUST validar la configuración al arrancar.

#### Scenario: Cambio de proveedor por variable de entorno
- **WHEN** el servicio arranca con `LLM_PROVIDER=fake` y después con `LLM_PROVIDER=anthropic` y una clave válida
- **THEN** cada instancia usa el adaptador del proveedor indicado y los consumidores no requieren cambios

#### Scenario: Proveedor desconocido
- **WHEN** el servicio arranca con `LLM_PROVIDER=desconocido`
- **THEN** el arranque falla con un error de configuración que lista los proveedores válidos

#### Scenario: Falta la clave del proveedor
- **WHEN** `LLM_PROVIDER=openai` y `OPENAI_API_KEY` no está definida
- **THEN** el arranque falla con un error de configuración que nombra la variable faltante, sin mostrar otros valores de configuración

#### Scenario: Proveedor sin modelo por defecto
- **WHEN** `LLM_PROVIDER=openai`, con su clave, y `LLM_MODEL` no está definida
- **THEN** el arranque falla con un error de configuración que nombra `LLM_MODEL`

### Requirement: Completado y streaming
El cliente SHALL ofrecer una operación que devuelve la respuesta completa con su uso de tokens y su latencia, y una operación de streaming que entrega el texto de forma incremental.

#### Scenario: Respuesta completa
- **WHEN** se pide un completado con el proveedor `fake`
- **THEN** se obtiene el texto, los tokens de entrada y salida, la latencia en milisegundos, el proveedor y el modelo

#### Scenario: Streaming
- **WHEN** se pide un completado en streaming
- **THEN** se reciben fragmentos en orden, y su concatenación es igual al texto de la respuesta completa equivalente

### Requirement: Reintentos acotados ante errores transitorios
El cliente SHALL reintentar solo los errores transitorios (timeout, límite de tasa y error del servidor) con backoff exponencial y jitter, hasta `LLM_MAX_RETRIES` intentos, y MUST NOT reintentar errores de validación ni de autenticación.

#### Scenario: Error transitorio que se recupera
- **WHEN** el proveedor falla 2 veces con un error 503 y después responde, con `LLM_MAX_RETRIES=3`
- **THEN** la llamada devuelve la respuesta y se registraron exactamente 3 intentos

#### Scenario: Reintentos agotados
- **WHEN** el proveedor falla con un error 503 en todos los intentos
- **THEN** la llamada falla con un error de proveedor tipado después de `LLM_MAX_RETRIES` intentos

#### Scenario: Error no reintentable
- **WHEN** el proveedor responde con un error 401 o 400
- **THEN** la llamada falla después de 1 intento con un error tipado y no se reintenta

#### Scenario: Respeto de Retry-After
- **WHEN** el proveedor responde 429 con `Retry-After: 2`
- **THEN** el siguiente intento ocurre como mínimo 2 segundos después

#### Scenario: Retry-After mayor que el tope
- **WHEN** el proveedor responde 429 con un `Retry-After` mayor que 30 segundos
- **THEN** la llamada falla enseguida, sin esperar, con un error de límite de tasa tipado que conserva el `Retry-After` recibido

### Requirement: Timeout por llamada
Cada llamada al proveedor MUST tener un timeout explícito configurado por `LLM_TIMEOUT_SECONDS`.

#### Scenario: Proveedor que no responde
- **WHEN** el proveedor no responde y `LLM_TIMEOUT_SECONDS=1`, con los reintentos desactivados
- **THEN** la llamada falla con un error de timeout tipado en menos de 1,5 segundos

### Requirement: Errores tipados y aislamiento del SDK
El cliente SHALL exponer solo sus propios tipos de error, y MUST NOT dejar salir las excepciones de los SDKs de los proveedores.

#### Scenario: Excepción del SDK
- **WHEN** el SDK de un proveedor lanza una excepción propia
- **THEN** el consumidor recibe un error del cliente que conserva la causa original como contexto

### Requirement: Registro de uso sin contenido sensible
El cliente SHALL registrar por cada llamada el proveedor, el modelo, los tokens, la latencia, la cantidad de intentos y el resultado, y MUST NOT registrar el texto del prompt ni el de la respuesta.

#### Scenario: Log de una llamada
- **WHEN** se completa una llamada cuyo prompt contiene `secreto-de-prueba`
- **THEN** se emite un log estructurado con los campos de uso, y la cadena `secreto-de-prueba` no aparece en ningún log

### Requirement: Salida estructurada
El cliente SHALL permitir pedir una respuesta que cumpla un esquema declarado y devolverla ya validada como un objeto tipado, junto con el uso de tokens sumado de todos los intentos, la cantidad de intentos, la latencia, el proveedor y el modelo. Si después de los reintentos configurados la respuesta no cumple el esquema, el cliente MUST fallar con un error tipado de validación.

#### Scenario: Respuesta válida
- **WHEN** se pide una salida estructurada con la unión discriminada `BuscarDocumentos(herramienta: "buscar_documentos", query: str, top_k: int)` | `ObtenerPagina(herramienta: "obtener_pagina", doc_id: str, pagina: int)` y el proveedor devuelve un JSON que cumple `ObtenerPagina`
- **THEN** el consumidor recibe un objeto `ObtenerPagina` tipado con esos campos, junto con el uso de tokens, los intentos, la latencia, el proveedor y el modelo

#### Scenario: Respuesta inválida
- **WHEN** el proveedor devuelve un texto que no es JSON válido para el esquema en todos los intentos
- **THEN** la llamada falla con un error de validación tipado, que incluye la cantidad de intentos y no incluye el contenido del prompt, y se registra la llamada con resultado de error

### Requirement: Esquemas cerrados
El cliente MUST aceptar solo esquemas cerrados: la raíz es un objeto y todo objeto declara sus propiedades. Los argumentos de cada herramienta se declaran con un modelo propio, y la llamada es una unión discriminada por el nombre de la herramienta.

#### Scenario: Esquema con objetos sin propiedades
- **WHEN** se pide una salida estructurada con un esquema que tiene un objeto sin propiedades declaradas (por ejemplo, `argumentos: dict[str, object]`), con cualquier proveedor
- **THEN** la llamada falla con un error de esquema tipado antes de llamar al proveedor
