# 01 · add-llm-client

Qué se construyó: un cliente LLM único (`services/ai/src/ai_doc_assistant/llm/`) y una interfaz de embeddings separada (`.../embeddings/`). El RAG, el agente y la evaluación van a hablar con estas dos interfaces y nunca con un SDK. Las rutas de abajo son relativas a `services/ai/`.

La change tuvo dos rondas: la implementación y una revisión. La revisión encontró un bug que los fakes no podían ver (sección 9), y de ahí salen varias de las ideas de esta nota.

## 1. Interfaces: `Protocol` en vez de clase abstracta

**Problema**: el RAG necesita "algo que complete texto". Si importa `anthropic` directo, testearlo sin red o cambiar de proveedor obliga a tocar el RAG.

**Qué se hizo**: `LLMClient` (`src/ai_doc_assistant/llm/client.py:11`) y `Embedder` (`src/ai_doc_assistant/embeddings/base.py:11`) son `typing.Protocol`. Un `Protocol` define un **tipado estructural** (*duck typing* verificado por mypy): cualquier clase que tenga esos métodos con esas firmas cumple el contrato, aunque no herede nada.

**Alternativa descartada**: una clase base abstracta (`abc.ABC`). Funciona, pero obliga a cada implementación, incluidos los fakes de los tests, a heredar de ella. Con `Protocol`, el `ScriptedProvider` de `tests/fakes/llm.py:77` cumple `LLMProvider` sin importar nada del módulo.

**Trade-off**: con un `Protocol` el error aparece en mypy y no en runtime. Si alguien no corre mypy, una implementación incompleta recién falla cuando se llama al método que falta. Para eso `make verify` corre `mypy --strict`.

Hay **dos** niveles de Protocol:

| Protocol | Quién lo implementa | Qué hace |
| --- | --- | --- |
| `LLMClient` (`llm/client.py`) | `ResilientLLMClient` | Lo que ven los consumidores: `complete`, `stream`, `complete_structured`, `aclose` |
| `LLMProvider` (`llm/provider.py:52`) | Un adaptador por proveedor (`fake`, `anthropic`, `openai`) | **Una** llamada al proveedor, con los errores traducidos a tipos propios |

Así el timeout, los reintentos y el log se escriben **una vez** (`llm/resilient.py`) y no una vez por proveedor. `aclose()` cierra el cliente HTTP del SDK al apagar el servicio. Sin eso, quedan conexiones abiertas y aparecen avisos de recursos sin cerrar.

> Pregunta: si mañana agregás Gemini, ¿qué archivos tocás y cuáles no deberías tocar?

## 2. Inyección de dependencias y fábricas

**Inyección de dependencias** significa que un objeto recibe sus colaboradores desde afuera en lugar de crearlos él. `ResilientLLMClient` recibe el `provider`, el `sleep` y el `clock` (`llm/resilient.py:64`). En producción son `asyncio.sleep` y `time.perf_counter`, y en los tests son un `FakeClock` (`tests/fakes/llm.py:27`) que "duerme" segundos virtuales. Por eso los tests de backoff verifican esperas de 0,5 s, 1 s y 2 s sin esperar de verdad.

La **fábrica** `build_llm_client` (`llm/factory.py`) es el único lugar que sabe qué clase concreta corresponde a cada `LLM_PROVIDER`. El registro `PROVIDERS` (`llm/factory.py:59`) es un diccionario: agregar un proveedor es un archivo nuevo en `providers/` y una línea en el registro. Los SDKs se importan adentro de cada builder (*import diferido*), así que importar `ai_doc_assistant.llm` no carga `anthropic` ni `openai`.

**Tests de punta a punta de la fábrica**: un test de `RetryPolicy` aislado no prueba que `LLM_MAX_RETRIES` llegue a la política. Los tests de `tests/llm/test_config.py` setean la variable de entorno, arman el cliente con la fábrica y cuentan los requests que recibe el servidor falso. Si alguien se olvida de pasar `settings.max_retries` en la fábrica, el test se rompe.

> Pregunta: ¿por qué el `FakeClock` también lo usa el proveedor falso para anotar la hora de cada intento? ¿Qué test sería imposible sin eso?

## 3. Configuración con pydantic-settings y *fail fast*

`LLMSettings` (`llm/settings.py`) lee `LLM_*` del entorno. Hay tres detalles no obvios:

- **Las claves son `SecretStr`**: su `repr` muestra `**********`. Si alguien loguea la configuración por accidente, la clave no sale.
- **`env_ignore_empty=True`** (`llm/settings.py:23`): `.env.example` trae `ANTHROPIC_API_KEY=` vacía, y una cadena vacía tiene que contar como "no definida", no como una clave válida.
- **El `ValidationError` de Pydantic incluye el valor recibido** (`input_value=...`). `load_llm_settings` arma un mensaje propio solo con el nombre de la variable y el motivo, y corta la cadena de causas con `from None` (`llm/settings.py:56`).

***Fail fast*** (fallar rápido) significa que un proveedor desconocido, una clave faltante u OpenAI sin `LLM_MODEL` revientan en `build_llm_client`, es decir, al arrancar el servicio. Para saber si `LLM_MODEL` vino del entorno o es el default, la fábrica mira `settings.model_fields_set` (`llm/factory.py:46`), que incluye los campos que llegaron del entorno.

> Pregunta: `LLM_PROVIDER` no tiene default. ¿Qué riesgo concreto evita eso frente a usar `fake` por defecto?

## 4. Errores transitorios y permanentes

Un error **transitorio** es uno en el que el mismo request, repetido, puede salir bien: timeout, 429 (límite de tasa), 5xx o un corte de conexión. Un error **permanente** da lo mismo al repetirlo: 400 (request mal armada), 401 (clave inválida), 404. Reintentar un 401 solo gasta tiempo y cuota.

- La clasificación vive en `is_transient` (`llm/retry.py:19`) y en `error_from_status` (`llm/providers/_http_errors.py:16`), que traduce el código HTTP.
- **El status HTTP no siempre alcanza**: en streaming, Anthropic responde 200, empieza a mandar eventos y, si se satura, manda un evento SSE `error` con `{"error": {"type": "overloaded_error"}}`. El SDK lo levanta como `APIStatusError` con `status_code=200`. Antes lo tratábamos como un error permanente "respondió 200". Ahora, si el status es menor que 400, se mira `body["error"]["type"]` (`llm/providers/anthropic_provider.py:54`, `_http_errors.py:59`).
- Los adaptadores levantan errores propios con `raise ... from exc`, y la excepción del SDK queda en `__cause__`.
- Una excepción que no sabemos clasificar se trata como **no** transitoria (`_as_llm_error`, `llm/resilient.py:45`).

**Los reintentos del SDK están apagados** (`max_retries=0`, `llm/providers/anthropic_provider.py:79`). Los SDKs reintentan 2 veces por defecto. Si encima reintentamos nosotros, 3 intentos nuestros por 3 del SDK son 9 requests. El test que lo cuida es `[503, ok]` con 1 intento: si el SDK reintentara por su cuenta, consumiría el `ok` y la llamada saldría bien. El test de 3 intentos solo no alcanzaba para verlo.

> Pregunta: un `overloaded_error` que llega **después** del primer token, ¿se reintenta? ¿Qué ve el consumidor?

## 5. Backoff exponencial con jitter, `Retry-After` y su tope

**Backoff exponencial**: cada reintento espera el doble que el anterior (0,5 s, 1 s, 2 s, 4 s, 8 s), con un tope de 8 s (`llm/retry.py:68`).

**Jitter** (ruido aleatorio) y ***thundering herd***: si mil clientes fallaron en el mismo segundo y todos esperan exactamente 0,5 s, vuelven todos juntos y tiran al proveedor otra vez. Es la "manada en estampida". Con *full jitter*, cada uno espera un valor al azar entre 0 y el techo, y la carga se reparte.

**`Retry-After`**: si el proveedor dice "esperá 2 segundos", se espera eso **más** un jitter acotado de hasta 0,5 s (`llm/retry.py:67`). El jitter importa también acá: todos los clientes que recibieron `Retry-After: 2` en el mismo instante volverían juntos. Es acotado porque el proveedor ya dio un número: no tiene sentido sumarle hasta 8 s.

**Tope de 30 s** (`max_retry_after`, `llm/retry.py:47`): si el proveedor pide 120 s, esperar dejaría al usuario mirando una ruedita dos minutos. `should_retry` (`llm/retry.py:55`) devuelve `False` y el consumidor recibe `LLMRateLimitError` enseguida, con `retry_after=120`, para decidir qué hacer (mostrar un mensaje, encolar).

`LLM_MAX_RETRIES` cuenta **intentos totales**, porque así lo dice la spec. Con `3` se hacen un intento y hasta dos reintentos.

> Pregunta: ¿por qué en `test_respeta_retry_after` el jitter se fija en 0? ¿Qué dejaría de probar el test si fuera 1?

## 6. Timeouts: el del SDK y `asyncio.timeout`

1. **El timeout HTTP del SDK** (`timeout=settings.timeout_seconds`). Un test de la fábrica comprueba que `LLM_TIMEOUT_SECONDS=4.5` llega a la request real (`request.extensions["timeout"]`).
2. **`asyncio.timeout` como red de seguridad** (`llm/resilient.py:226`). Acota todo lo que pase fuera del cliente HTTP. Cuando vence, cancela la tarea y levanta `TimeoutError`, que traducimos a `LLMTimeoutError`.

En **streaming**, el timeout se aplica **entre fragmentos** (`llm/resilient.py:129`), no a la respuesta completa.

**Guardia en los tests de timeout**: el proveedor falso `Hang` duerme una hora. Si el timeout bajo prueba se rompiera, el test se colgaría una hora en CI. Por eso cada test de timeout va envuelto en `asyncio.wait_for(..., 5)`: si el código falla, el test falla en 5 s con `TimeoutError`.

> Pregunta: si el timeout en streaming fuera sobre la respuesta completa, ¿qué respuestas legítimas cortarías?

## 7. Streaming: no reintentar después del primer token

El consumidor del streaming ya recibió texto (y quizás ya se lo mostró al usuario por SSE). Si el stream falla a mitad de camino y reintentamos, el modelo genera **otra** respuesta, y el usuario vería texto duplicado o mezclado. Por eso se reintenta solo si no se emitió nada: `if not emitted and await self._backoff(...)` (`llm/resilient.py:144`).

`stream` es un **generador asíncrono** (`async def` con `yield`). En el `Protocol` se declara como `def stream(...) -> AsyncIterator[str]` (sin `async`), porque llamar a un generador asíncrono no se espera: devuelve el iterador directamente.

## 8. Salida estructurada con esquemas cerrados y uniones discriminadas

`complete_structured(prompt, Esquema)` devuelve un `StructuredResponse[Esquema]`: `value` (el objeto validado), más `usage` sumado de todas las rondas, `attempts` (todas las requests, reintentos incluidos), `latency_ms`, `provider` y `model`. Antes devolvía solo el objeto, y el costo de la llamada se perdía para quien la hacía.

**Esquema cerrado**: la raíz es un objeto y todo objeto declara sus propiedades. Para las herramientas del agente:

- Cada herramienta tiene **su** modelo (`BuscarDocumentos`, `ObtenerPagina`), con un campo `herramienta: Literal["..."]`.
- La llamada es una **unión discriminada**: `BuscarDocumentos | ObtenerPagina` con `Field(discriminator="herramienta")`. Pydantic lee el campo `herramienta` y valida contra la variante que corresponde. Si viene `"borrar_todo"`, la respuesta no valida.
- La unión va **dentro de un modelo contenedor** (`LlamadaHerramienta(llamada: ...)`), porque una unión en la raíz no es un objeto: `transform_schema` la devuelve como `anyOf`, sin `type: object`.

`ensure_closed_schema` (`llm/schema.py:72`) recorre el JSON Schema y rechaza con `LLMSchemaError`, **antes de gastar una request**, los objetos sin propiedades, los que admiten propiedades libres (`extra="allow"`), los campos `Any`, los arrays sin `items` y las raíces que no son objeto. Una tupla (`tuple[int, str]`) sale como `prefixItems`, que `transform_schema` no entiende y deja como texto en la descripción, así que el array queda sin tipo de elemento. Lo seguro es usar una lista de un modelo. Si la respuesta no valida, se reintenta una vez con el error resumido como contexto (`_summarize`, `llm/resilient.py:55`). Si vuelve a fallar, se levanta `LLMValidationError` y se loguea la llamada con `outcome=error`.

**Lo que hace `anthropic.transform_schema` con una unión** (leído en el código instalado, `anthropic/lib/_parse/_transform.py`): convierte `oneOf` en `anyOf`, resuelve las `$defs` y pone `additionalProperties: false` en cada objeto. El `discriminator` de Pydantic no lo entiende y lo deja como texto en la `description`. No pasa nada, porque cada variante tiene su `const` y el `anyOf` sigue siendo cerrado.

> Pregunta: ¿por qué conviene que el error de esquema salga antes de llamar al proveedor y no como un `LLMValidationError` después de dos intentos?

## 9. Tests de contrato frente a fakes

En la primera ronda, el escenario de la spec pedía `argumentos: dict[str, object]`, y todos los tests pasaban. Pero `anthropic.transform_schema` convierte ese campo en `{"type": "object", "properties": {}, "additionalProperties": false}`: un objeto vacío y cerrado. Con Claude real, `argumentos` iba a volver **siempre** vacío.

¿Por qué no lo vio ningún test? Porque el `ScriptedProvider` y el `FakeServer` devuelven el JSON que el test les dice: nunca pasan por el `transform_schema` real. Un **fake** prueba tu lógica contra lo que *creés* que hace la dependencia. Un **test de contrato** prueba lo que la dependencia *hace de verdad*:

- `test_transform_schema_de_anthropic_conserva_la_union_cerrada` (`tests/llm/test_schema_contract.py:40`) llama al `transform_schema` real con `LlamadaHerramienta` y verifica que las propiedades y los `required` de cada variante sobreviven.
- `test_transform_schema_vacia_un_dict_libre` (`tests/llm/test_schema_contract.py:53`) deja documentado el bug: si una versión futura del SDK cambia ese comportamiento, el test avisa.
- Otros dos tests miran el **cuerpo** que serializa cada SDK real (Anthropic y OpenAI) con el esquema cerrado.

Siguen sin red ni clave, y son rápidos. La regla que queda: **cada vez que tu código le pasa datos a una función de un SDK que los transforma, tiene que haber un test que llame a esa función real**.

## 10. Logs sin el prompt

Cada llamada emite **un** evento `llm_call` (`llm/resilient.py:268`) con proveedor, modelo, operación, tokens, latencia, intentos y resultado. En `complete_structured` también es uno solo, con el uso sumado, aunque haya hecho dos rondas.

En `DEBUG`, el SDK de Anthropic loguea las opciones de cada request **con el cuerpo**, o sea, con el prompt. El adaptador fija su logger en `WARNING` (`llm/providers/anthropic_provider.py:44`), y `test_los_logs_del_sdk_no_filtran_el_prompt` falla si se quita esa línea. El SDK de OpenAI 3.59 ya no loguea el cuerpo, solo el método y los reintentos (`openai/_base_client.py:606`). Su logger se fija igual en `WARNING` por defensa en profundidad, por si otra versión vuelve a hacerlo. La política central de logging de terceros queda para `add-observability-security`.

## 11. Embeddings: prefijos, normalización, determinismo, lotes

- **Prefijos `query:` y `passage:`**: la familia e5 se entrenó así. La interfaz obliga a elegir el rol (`embed_queries` o `embed_passages`). Los prefijos se deciden por el id del modelo (`e5_prefixes`, `embeddings/local.py:34`): si el último segmento empieza con `e5-` o `multilingual-e5-`, se usan, también cuando se construye `LocalEmbedder` a mano. Cualquier otro modelo va sin prefijo: a `all-MiniLM-L6-v2` un `"query: "` le metería ruido. Los e5 `-instruct` esperan otro formato (`Instruct: ...\nQuery: `). Embeberlos con `query: ` no da error, pero baja la calidad sin que nadie se entere. Por eso se rechazan con `EmbeddingsConfigError` antes de cargar el modelo: **ante una configuración que sabemos que está mal, mejor un error ruidoso que un resultado silenciosamente peor**.
- **Normalización**: `normalize_embeddings=True` (`embeddings/local.py:108`) deja cada vector con norma 1, y entonces la similitud coseno `a·b / (|a||b|)` se reduce a `a·b`, el producto interno.
- **Determinismo**: en CPU, el mismo texto da el mismo vector (coseno ≥ 0,9999 entre corridas, test `test_dos_corridas`).
- **Lotes**: `_embed` parte la lista en lotes de `EMBEDDINGS_BATCH_SIZE` (`embeddings/local.py:137`) y concatena en orden. Un test de la fábrica comprueba que `EMBEDDINGS_BATCH_SIZE=7` produce lotes de 7, 7 y 6.

## 12. `asyncio.to_thread` para trabajo de CPU

`SentenceTransformer.encode` es síncrono y usa la CPU a fondo. Si se llamara directo dentro de un `async def`, el event loop quedaría bloqueado y FastAPI dejaría de atender **todas** las requests. `asyncio.to_thread` (`embeddings/local.py:140`) lo corre en un hilo aparte. PyTorch libera el GIL (*Global Interpreter Lock*) mientras calcula, así que el loop sigue vivo. `test_el_modelo_corre_fuera_del_event_loop` (`tests/embeddings/test_embedder.py:137`) lo prueba con un "latido": una tarea que suma 1 cada 10 ms tiene que seguir sumando mientras el encoder bloquea 0,3 s.

## 13. Tests de integración visibles

Un test marcado `integration` que nadie corre es casi lo mismo que no tenerlo. `scripts/verify.sh` acepta `INTEGRATION=auto|1|0`:

- En **`auto`**, local, corre los de `services/ai` solo si el modelo e5 ya está en la caché de Hugging Face. El criterio es simple: existe un `model.safetensors` en `models--intfloat--multilingual-e5-small/snapshots/`. Una corrida local nunca baja 470 MB sin avisar. Si no corren, el resumen dice `SKIP` y por qué.
- En **`1`**, que usa CI, corren siempre, y la falta de una dependencia es un `FALLO`, no un `SKIP` silencioso. Lo mismo pasa si pytest no recolecta ningún test de integración (código de salida 5): si se pidió correrlos y no corrió ninguno, algo está mal. CI instala Tesseract y cachea `~/.cache/huggingface` con `actions/cache`, así el modelo se baja una sola vez.
- Las actions de CI se fijan por **SHA completo** (con un comentario de la versión), porque un tag como `v6` se puede mover y un commit no. Es una defensa contra que una action comprometida cambie lo que corre en tu CI.

## Decisiones y su porqué

| Decisión | Por qué |
| --- | --- |
| PyTorch CPU desde `download.pytorch.org/whl/cpu` con `explicit = true` | Las ruedas de PyPI traen CUDA (varios GB) y en el POC no hay GPU |
| `httpx2` en vez de `httpx` | Los SDKs instalados (anthropic 2.14, openai 3.59) migraron a `httpx2` |
| Esquemas cerrados y uniones discriminadas (decisión del autor) | Un dict libre se vacía en `transform_schema`. Un modelo por herramienta deja que el proveedor y Pydantic validen cada argumento |
| Tope de `Retry-After` de 30 s (decisión del autor) | Más que eso es peor que fallar rápido con un error claro |
| `StructuredResponse[T]` (decisión del autor) | El consumidor necesita el costo y los intentos de la operación completa |
| OpenAI con `strict: false` (decisión del autor) | `strict: true` necesita un helper privado del SDK. El esquema ya es cerrado y Pydantic valida la respuesta |
| Errores a mitad de stream de OpenAI = permanentes (decisión del autor) | Limitación conocida y aceptada: OpenAI no es el proveedor por defecto |
| e5 `-instruct` se rechaza (decisión del autor) | Un error al arrancar es mejor que vectores peores sin aviso |
| Corte de conexión = transitorio (aceptado) | Es un fallo de red y no un rechazo del proveedor |
| `make install` con `uv sync --locked` | Si `uv.lock` no coincide con `pyproject.toml`, falla en vez de reescribirlo en silencio |

## Errores típicos

- **Doble reintento**: dejar el `max_retries` del SDK en su default y encima reintentar por fuera.
- **Confiar solo en el status HTTP**: un error en mitad de un stream llega con 200.
- **Backoff sin jitter**, o `Retry-After` sin jitter: los clientes vuelven todos juntos.
- **Respetar cualquier `Retry-After`**: el usuario espera minutos sin saber por qué.
- **Esquemas con `dict` libre para salida estructurada**: el proveedor los cierra y el modelo devuelve `{}`.
- **Testear una integración solo con fakes**: el fake repite lo que vos creés que hace el SDK.
- **Tests de timeout sin guardia**: si el código se rompe, CI se cuelga en vez de fallar.
- **Llamar a `encode` dentro de `async def` sin `to_thread`**: congela el servicio entero.
- **Caché de ruff desactualizada**: los tests se escribieron antes de que existiera `ai_doc_assistant.llm`, y ruff clasificó ese import como de terceros. `ruff check .` siguió en verde por la caché, y con `--no-cache` aparecieron 11 imports mal ordenados.

## Preguntas de entrevista

1. **¿`Protocol` o `ABC` para una interfaz de proveedor?** `Protocol`: tipado estructural, los fakes no heredan nada y mypy verifica el contrato.
2. **¿Qué errores reintentás al llamar a un LLM?** Los transitorios: timeout, 429 (respetando `Retry-After` hasta un tope), 5xx y cortes de red. Nunca 400 ni 401.
3. **¿Qué es el *thundering herd* y cómo lo evitás?** Muchos clientes que reintentan en el mismo instante y vuelven a saturar al servicio. Se evita con jitter, también sobre el `Retry-After`.
4. **¿Fake o test de contrato?** Los dos. El fake prueba tu lógica rápido y sin red. El test de contrato llama al código real de la dependencia (por ejemplo, el `transform_schema` del SDK) y detecta cuando tu suposición sobre ella es falsa.
5. **¿Cómo modelás la salida estructurada de un agente con varias herramientas?** Un modelo por herramienta, con un `Literal` que la nombra, y una unión discriminada por ese campo dentro de un modelo contenedor. Nada de dicts libres.

> Pregunta final: con una unión discriminada, ¿qué pasa si el modelo inventa una herramienta que no existe? ¿En qué paso del flujo se detecta y qué recibe el agente?
