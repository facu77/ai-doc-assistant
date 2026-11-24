# 01 · add-llm-client

Qué se construyó: un cliente LLM único (`services/ai/src/ai_doc_assistant/llm/`) y una interfaz de embeddings separada (`.../embeddings/`). El RAG, el agente y la evaluación van a hablar con estas dos interfaces y nunca con un SDK. Las rutas de abajo son relativas a `services/ai/`.

## 1. Interfaces: `Protocol` en vez de clase abstracta

**Problema**: el RAG necesita "algo que complete texto". Si importa `anthropic` directo, testearlo sin red o cambiar de proveedor obliga a tocar el RAG.

**Qué se hizo**: `LLMClient` (`src/ai_doc_assistant/llm/client.py:15`) y `Embedder` (`src/ai_doc_assistant/embeddings/base.py:11`) son `typing.Protocol`. Un `Protocol` define un **tipado estructural** (*duck typing* verificado por mypy): cualquier clase que tenga esos métodos con esas firmas cumple el contrato, aunque no herede nada.

**Alternativa descartada**: una clase base abstracta (`abc.ABC`). Funciona, pero obliga a cada implementación, incluidos los fakes de los tests, a heredar de ella. Con `Protocol`, el `ScriptedProvider` de `tests/fakes/llm.py:77` cumple `LLMProvider` sin importar nada del módulo.

**Trade-off**: con un `Protocol` el error aparece en mypy y no en runtime. Si alguien no corre mypy, una implementación incompleta recién falla cuando se llama al método que falta. Para eso `make verify` corre `mypy --strict`.

Hay **dos** niveles de Protocol:

| Protocol | Quién lo implementa | Qué hace |
| --- | --- | --- |
| `LLMClient` (`llm/client.py`) | `ResilientLLMClient` | Lo que ven los consumidores: `complete`, `stream`, `complete_structured` |
| `LLMProvider` (`llm/provider.py:52`) | Un adaptador por proveedor (`fake`, `anthropic`, `openai`) | **Una** llamada al proveedor, con los errores traducidos a tipos propios |

Así el timeout, los reintentos y el log se escriben **una vez** (`llm/resilient.py`) y no una vez por proveedor.

> Pregunta: si mañana agregás Gemini, ¿qué archivos tocás y cuáles no deberías tocar?

## 2. Inyección de dependencias y fábricas

**Inyección de dependencias** significa que un objeto recibe sus colaboradores desde afuera en lugar de crearlos él. `ResilientLLMClient` recibe el `provider`, el `sleep` y el `clock` (`llm/resilient.py:58`). En producción son `asyncio.sleep` y `time.perf_counter`, y en los tests son un `FakeClock` (`tests/fakes/llm.py:27`) que "duerme" segundos virtuales. Por eso los tests de backoff verifican esperas de 0,5 s, 1 s y 2 s sin esperar de verdad, y la suite entera corre en unos 4 segundos.

La **fábrica** `build_llm_client` (`llm/factory.py`) es el único lugar que sabe qué clase concreta corresponde a cada `LLM_PROVIDER`. El registro `PROVIDERS` (`llm/factory.py:52`) es un diccionario: agregar un proveedor es un archivo nuevo en `providers/` y una línea en el registro. Los SDKs se importan adentro de cada builder (*import diferido*), así que importar `ai_doc_assistant.llm` no carga `anthropic` ni `openai`.

> Pregunta: ¿por qué el `FakeClock` también lo usa el proveedor falso para anotar la hora de cada intento? ¿Qué test sería imposible sin eso?

## 3. Configuración con pydantic-settings y *fail fast*

`LLMSettings` (`llm/settings.py`) lee `LLM_*` del entorno. Hay tres detalles no obvios:

- **Las claves son `SecretStr`**: su `repr` muestra `**********`. Si alguien loguea la configuración por accidente, la clave no sale.
- **`env_ignore_empty=True`** (`llm/settings.py:23`): `.env.example` trae `ANTHROPIC_API_KEY=` vacía, y una cadena vacía tiene que contar como "no definida", no como una clave válida.
- **El `ValidationError` de Pydantic incluye el valor recibido** (`input_value=...`). `load_llm_settings` arma un mensaje propio solo con el nombre de la variable y el motivo, y corta la cadena de causas con `from None` (`llm/settings.py:56`). El test `test_valor_invalido_nombra_la_variable_sin_mostrar_el_valor` lo verifica.

***Fail fast*** (fallar rápido) significa que un proveedor desconocido o una clave faltante revientan en `build_llm_client`, es decir, al arrancar el servicio. La alternativa es que reviente en la primera request de un usuario, minutos u horas después del deploy, cuando ya es más difícil relacionar el error con la configuración.

> Pregunta: `LLM_PROVIDER` no tiene default. ¿Qué riesgo concreto evita eso frente a usar `fake` por defecto?

## 4. Errores transitorios y permanentes

Un error **transitorio** es uno en el que el mismo request, repetido, puede salir bien: timeout, 429 (límite de tasa), 5xx o un corte de conexión. Un error **permanente** da lo mismo al repetirlo: 400 (request mal armada), 401 (clave inválida), 404. Reintentar un 401 solo gasta tiempo y cuota.

- La clasificación vive en un solo lugar: `is_transient` (`llm/retry.py:19`), más `error_from_status` (`llm/providers/_http_errors.py:16`), que traduce el código HTTP.
- Los adaptadores capturan las excepciones del SDK y levantan las propias con `raise ... from exc`. El consumidor ve `LLMProviderError` y la excepción original queda en `__cause__` para depurar (test `test_excepcion_del_sdk_queda_como_causa`).
- Una excepción que no sabemos clasificar (por ejemplo, un bug en un adaptador) se trata como **no** transitoria (`_as_llm_error`, `llm/resilient.py:39`). Ante la duda, conviene fallar rápido y no reintentar a ciegas.

**Los reintentos del SDK están apagados** (`max_retries=0`, `llm/providers/anthropic_provider.py:73`). Los SDKs de Anthropic y OpenAI reintentan 2 veces por defecto. Si encima reintentamos nosotros, 3 intentos nuestros por 3 del SDK son 9 requests, y el test "exactamente 3 intentos" mentiría. `test_los_reintentos_del_sdk_estan_desactivados` lo cubre con el SDK real.

> Pregunta: un 529 (`overloaded`) de Anthropic, ¿es transitorio o permanente? ¿En qué línea del código se decide?

## 5. Backoff exponencial con jitter y `Retry-After`

**Backoff exponencial**: cada reintento espera el doble que el anterior (0,5 s, 1 s, 2 s, 4 s, 8 s), con un tope de 8 s (`llm/retry.py:51`). Así un proveedor saturado tiene tiempo de recuperarse.

**Jitter** (ruido aleatorio): se usa *full jitter*, que espera un valor al azar entre 0 y ese techo. Sin jitter, mil clientes que fallaron en el mismo segundo reintentan todos juntos en el segundo 0,5, después en el 1,5, y así siguen. Es el efecto *thundering herd* (manada en estampida). El `random` se inyecta, y los tests lo fijan en 1,0 o 0,25 para que sean reproducibles.

**`Retry-After`**: si el proveedor dice "esperá 2 segundos", la espera es `max(jitter, retry_after)` (`llm/retry.py:55`). El header se lee como `retry-after-ms`, como segundos o como fecha HTTP (`parse_retry_after`).

`LLM_MAX_RETRIES` cuenta **intentos totales**, porque así lo dice la spec ("hasta `LLM_MAX_RETRIES` intentos"). Con `3` se hacen un intento y hasta dos reintentos.

> Pregunta: ¿por qué en `test_respeta_retry_after` el jitter se fija en 0? ¿Qué dejaría de probar el test si fuera 1?

## 6. Timeouts: el del SDK y `asyncio.timeout`

Hay dos capas:

1. **El timeout HTTP del SDK** (`timeout=settings.timeout_seconds`). Corta conexiones lentas. El test `test_timeout_explicito_llega_al_cliente_http` comprueba que llega a la request (`request.extensions["timeout"]`).
2. **`asyncio.timeout` como red de seguridad** (`llm/resilient.py:171`). Acota todo lo que pase fuera del cliente HTTP, como un adaptador colgado o un DNS que no responde. Cuando vence, cancela la tarea y levanta `TimeoutError`, que traducimos a `LLMTimeoutError`.

El test `test_proveedor_que_no_responde` usa el reloj real: un proveedor que nunca responde, con `timeout=1`, tiene que fallar entre 0,9 s y 1,5 s.

En **streaming**, el timeout se aplica **entre fragmentos** (`llm/resilient.py:110`), no a la respuesta completa. Una respuesta larga que va llegando es válida. Un stream que se traba no lo es.

> Pregunta: si el timeout en streaming fuera sobre la respuesta completa, ¿qué respuestas legítimas cortarías?

## 7. Streaming: no reintentar después del primer token

El consumidor del streaming ya recibió texto (y quizás ya se lo mostró al usuario por SSE). Si el stream falla a mitad de camino y reintentamos, el modelo genera **otra** respuesta, y el usuario vería "La licencia anual es deLa licencia anual corresponde a...". Por eso se reintenta solo si no se emitió nada: `if not emitted and await self._backoff(...)` (`llm/resilient.py:125`). Los dos casos están testeados en `test_streaming_reintenta_si_falla_antes_del_primer_token` y `test_streaming_no_reintenta_despues_del_primer_token`.

`stream` es un **generador asíncrono** (`async def` con `yield`). En el `Protocol` se declara como `def stream(...) -> AsyncIterator[str]` (sin `async`), porque llamar a un generador asíncrono no se espera: devuelve el iterador directamente.

## 8. Salida estructurada

`complete_structured(prompt, Esquema)` devuelve una instancia ya validada de un modelo Pydantic.

- **Anthropic**: se usa `output_config={"format": {"type": "json_schema", "schema": ...}}` con el esquema adaptado por `anthropic.transform_schema` (`llm/providers/anthropic_provider.py:84`). Se descartó `messages.parse()`, porque valida adentro del SDK, y queríamos que la validación y el reintento fueran iguales para todos los proveedores.
- **OpenAI**: `response_format` con `json_schema` y `strict: False`. El modo estricto exige `additionalProperties: false` en todo el esquema, y eso rompe campos libres como `argumentos: dict[str, object]`.
- **Validación propia**: si el JSON no valida, se reintenta **una** vez y se le pasa al modelo el error resumido (`_summarize`, `llm/resilient.py:49`), por ejemplo `argumentos: Field required`. El resumen usa `errors(include_input=False)`, así que no repite lo que respondió el modelo, que podría contener el prompt. Si vuelve a fallar, se levanta `LLMValidationError` con `attempts=2`.

**Ojo con `transform_schema`**: para `dict[str, object]` genera `{"type": "object", "properties": {}, "additionalProperties": false}`. Con Anthropic, entonces, un campo de argumentos libres va a volver siempre vacío. El agente (`add-agent`) va a necesitar esquemas explícitos por herramienta.

> Pregunta: la validación de estructura y los errores 503 tienen reintentos separados. ¿Cuántos requests como máximo puede hacer un `complete_structured` con `LLM_MAX_RETRIES=3`?

## 9. Logs sin el prompt

Cada llamada emite **un** evento `llm_call` (`llm/resilient.py:224`) con proveedor, modelo, operación, tokens, latencia, intentos y resultado. El prompt y la respuesta no aparecen, solo sus tamaños en tokens.

Hubo una trampa: en nivel `DEBUG`, los SDKs de Anthropic y OpenAI loguean las opciones de cada request, **con el cuerpo**, o sea, con el prompt. Un `LOG_LEVEL=DEBUG` global habría filtrado datos de usuarios. Los adaptadores fijan esos loggers en `WARNING` (`llm/providers/anthropic_provider.py:42`). El test `test_los_logs_del_sdk_no_filtran_el_prompt` lo verifica, y se comprobó que falla si se quita esa línea.

## 10. Embeddings: prefijos, normalización, determinismo, lotes

- **Prefijos `query:` y `passage:`**: la familia e5 se entrenó así, con un rol para la pregunta y otro para el documento. La interfaz obliga a elegir (`embed_queries` o `embed_passages`) y por eso es imposible olvidarse del prefijo.
- **Normalización**: `normalize_embeddings=True` (`embeddings/local.py:71`) deja cada vector con norma 1. Con norma 1, la similitud coseno `cos(a, b) = a·b / (|a||b|)` se reduce a `a·b`, el producto interno, que es más barato y es lo que optimizan FAISS y Qdrant.
- **Determinismo**: en CPU, el mismo texto da el mismo vector (con coseno ≥ 0,9999 entre corridas, test `test_dos_corridas`). Hace falta para que la evaluación sea reproducible.
- **Lotes**: `_embed` parte la lista en lotes de `EMBEDDINGS_BATCH_SIZE` (`embeddings/local.py:100`) y concatena en orden. Así se acota la memoria, y entre lote y lote el event loop puede atender otras tareas.
- **Medido en este entorno (4 CPU)**: dimensión 384, carga del modelo en frío de unos 8 s, y 250 pasajes cortos en 0,9 s con lotes de 64. Es una corrida a mano, no un script del repo, así que no va al README.

## 11. `asyncio.to_thread` para trabajo de CPU

`SentenceTransformer.encode` es síncrono y usa la CPU a fondo. Si se llamara directo dentro de un `async def`, el event loop quedaría bloqueado y FastAPI dejaría de atender **todas** las requests mientras tanto. `asyncio.to_thread` (`embeddings/local.py:103`) lo corre en un hilo aparte. PyTorch libera el GIL (el *Global Interpreter Lock* de Python) durante el cálculo, así que el loop sigue vivo. `test_el_modelo_corre_fuera_del_event_loop` (`tests/embeddings/test_embedder.py:134`) lo prueba con un "latido": una tarea que suma 1 cada 10 ms tiene que seguir sumando mientras el encoder bloquea 0,3 s.

## 12. Fakes, no mocks

- `ScriptedProvider` (`tests/fakes/llm.py:77`) sigue un guion de pasos `Reply`, `Fail` y `Hang`. El cliente tiene que reintentar, esperar y medir de verdad para que el test pase.
- `FakeServer` (`tests/fakes/http.py:20`) va más lejos: es un `httpx2.MockTransport` (un transporte HTTP de mentira). Los SDKs **reales** arman la request, reciben un 503 o un 429 con `Retry-After` y levantan **sus** excepciones. Así se prueba la traducción de errores sin red y sin clave. Un `MagicMock` del SDK solo habría probado lo que el mock decía que el SDK hace.

## Decisiones y su porqué

| Decisión | Por qué |
| --- | --- |
| PyTorch CPU desde `download.pytorch.org/whl/cpu` con `explicit = true` | Las ruedas de PyPI traen CUDA (varios GB) y en el POC no hay GPU. `explicit` hace que ese índice se use solo para `torch` |
| `httpx2` en vez de `httpx` | Los SDKs instalados (anthropic 2.14, openai 3.59) migraron a `httpx2`. `httpx` no lo usaba nadie |
| Corte de conexión = transitorio | Es un fallo de red y no un rechazo del proveedor. La spec nombra timeout, 429 y 5xx: esto es una extensión, anotada en "Preguntas abiertas" |
| 408 = timeout | Es un timeout del lado del servidor |
| `latency_ms` incluye reintentos | Es lo que espera el consumidor |
| `complete` y `stream` aceptan `system` y `max_tokens` | Anthropic exige `max_tokens`, y el RAG va a necesitar un *system prompt*. Anotado en "Preguntas abiertas" |
| `fake` reporta el modelo `fake-llm` | Que un log diga `claude-haiku-5-5` cuando no se llamó a Claude confunde |
| El Embedder devuelve `list[list[float]]` | Es un tipo simple adentro, como pide CLAUDE.md. Pasarlo a `numpy` para FAISS es trivial |

## Errores típicos

- **Doble reintento**: dejar el `max_retries` del SDK en su default y encima reintentar por fuera.
- **Reintentar un 401**: gasta tiempo y puede bloquear la cuenta por abuso.
- **Backoff sin jitter**: todos los clientes reintentan en sincronía.
- **Reintentar un stream ya empezado**: el usuario ve texto duplicado.
- **Llamar a `encode` dentro de `async def` sin `to_thread`**: congela el servicio entero.
- **Olvidar los prefijos de e5**: baja la calidad de recuperación sin ningún error visible.
- **Loguear el `ValidationError` de Pydantic tal cual**: incluye el valor de entrada.
- **Caché de ruff desactualizada**: los tests se escribieron antes de que existiera `ai_doc_assistant.llm`, y ruff clasificó ese import como de terceros. Al crear el paquete, `ruff check .` seguía en verde porque leía la caché. Con `--no-cache` aparecieron 11 imports mal ordenados. Una CI limpia lo habría marcado.

## Preguntas de entrevista

1. **¿`Protocol` o `ABC` para una interfaz de proveedor?** `Protocol`: tipado estructural, los fakes no heredan nada y mypy verifica el contrato. Una `ABC` agrega la verificación en runtime a cambio de acoplar a todos a la clase base.
2. **¿Qué errores reintentás al llamar a un LLM?** Los transitorios: timeout, 429 (respetando `Retry-After`), 5xx y cortes de red. Nunca 400 ni 401, porque repetir da el mismo resultado.
3. **¿Por qué jitter en el backoff?** Para desincronizar a los clientes que fallaron juntos y no volver a saturar al proveedor en el mismo instante.
4. **¿Cómo reintentás un streaming?** Solo si falló antes del primer token. Después ya no, porque el consumidor tiene texto parcial y un segundo intento genera otra respuesta.
5. **¿Por qué normalizar los embeddings?** Con norma 1, coseno = producto interno: es más barato y es la métrica nativa de los índices vectoriales.

> Pregunta final: el agente va a pedir `{herramienta, argumentos}` con Anthropic. Por lo que viste de `transform_schema`, ¿qué le pasaría a `argumentos`, y cómo lo resolverías sin tocar el cliente?
