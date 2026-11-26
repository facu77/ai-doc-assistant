# 02 · add-ingest-pipeline: de PDFs y escaneos a texto medido

Qué se construyó en esta change y qué conceptos hay detrás. El RAG solo puede ser tan bueno como el texto que recibe, y esta change produce ese texto: un JSONL por documento, con el texto por página, el método de extracción y una medida de calidad (el CER). Todo lo que sigue apunta a código real del repo y a números de corridas versionadas en `evals/runs/ingest/` (resumidas en `pipelines/ingest/REPORT.md`). La nota cubre las dos rondas: la implementación y las correcciones posteriores a la revisión.

## 1. PDF nativo y PDF escaneado: la capa de texto

**Qué es**: un PDF puede guardar texto de dos maneras.

- **Nativo**: cada carácter está guardado como carácter, con su fuente y su posición. Esa información forma la *capa de texto*, y se lee sin OCR. Por ejemplo, `data/corpus/01-politica-licencias.pdf`.
- **Escaneado**: la página es una foto. No hay caracteres, solo píxeles. Por ejemplo, `data/corpus/09-formulario-solicitud-vacaciones.pdf`.

La capa de texto se lee con `page.get_text("text")`, en `src/ingest/pdf.py:59`.

**El problema**: un mismo PDF puede mezclar los dos tipos. `19-manual-evaluacion-desempeno.pdf` tiene las páginas 1 y 3 nativas y la 2 escaneada. Por eso se decide **por página** y no por documento.

**La regla** está en `src/ingest/detection.py:41`. Una página es nativa si tiene al menos 50 caracteres no blancos y al menos el 90 % de ellos son imprimibles. El ratio sirve para atrapar capas de texto rotas. Un caso típico son las fuentes sin tabla `ToUnicode`, que se extraen como `U+FFFD` (el carácter de reemplazo). Esa página "tiene texto", pero el texto es basura.

**El caso borde del sello**: la página 2 de `20-constancia-capacitacion.pdf` es una imagen con un sello que tiene capa de texto: "RECIBIDO RRHH 02/11/2026". Son 24 caracteres con los espacios, pero la regla cuenta los **no blancos**, que son 22. Como no llega a 50, la página va a OCR. Además se rasteriza la página **completa** (`src/ingest/pipeline.py:196`), así que el OCR lee la imagen y el sello juntos.

El test `test_los_umbrales_de_deteccion_son_configurables` muestra qué pasa con un umbral demasiado bajo (10): la página se toma como nativa y su texto queda reducido al sello. Todo el contenido de la imagen se pierde **sin ningún error**.

**Trade-off**: los dos errores no cuestan lo mismo.

| Error | Costo |
| --- | --- |
| Mandar a OCR una página nativa | Unos 2 s más y algún carácter mal leído |
| Tomar como nativa una página escaneada | Se pierde el contenido en silencio |

Por eso conviene que el umbral sea conservador.

**Alternativas descartadas**:

- Hacer OCR de todo: es más simple, pero cuesta unos 2 s por página en lugar de milisegundos y mete errores en texto que ya era perfecto. Los 8 nativos dan CER 0,00 % justamente porque no pasan por OCR.
- Decidir por documento: falla con los PDFs mixtos.

> **Pregunta**: un PDF nativo tiene una página que solo dice "Anexo B" (6 caracteres). ¿Qué método le asigna el pipeline? ¿Se pierde algo?

## 2. Rasterizar y dpi

**Rasterizar** es convertir una página (vectores, texto, imágenes) en una matriz de píxeles. Los **dpi** (*dots per inch*, puntos por pulgada) dicen cuántos píxeles entran en una pulgada. Una hoja A4 (8,27 pulgadas de ancho) a 300 dpi tiene 2480 × 3508 píxeles. El test `test_la_pagina_escaneada_se_rasteriza_a_300_dpi` verifica justamente ese ancho de 2480 en la imagen que recibe el OCR.

¿Por qué 300 dpi? Con 300 dpi, el cuerpo de una letra de 11 puntos ocupa unos 46 píxeles (11/72 × 300) y una minúscula de Helvetica mide unos 24 de alto. La documentación de Tesseract recomienda al menos 300 dpi, porque con letras de pocos píxeles los trazos se empastan y la precisión cae. Con mucha más resolución, el OCR tarda más sin ganar precisión.

El rasterizado está en `src/ingest/pdf.py:72` (`get_pixmap(dpi=..., colorspace=GRAY)`). Las imágenes sueltas que declaran otra resolución en sus metadatos (por ejemplo, los `.jpg` del corpus vienen a 200 dpi) se reescalan a 300 dpi (`src/ingest/pipeline.py:240`). Así todas las páginas llegan al OCR con el mismo criterio.

**No le creas siempre al metadato.** En la revisión aparecieron tres problemas (`_image_dpi`, `src/ingest/pipeline.py:212`):

- **Valores implausibles**: muchas aplicaciones guardan 72 dpi por defecto, aunque la imagen se haya escaneado a 300. Si le creés, reescalás la imagen ×4 sin motivo. Por eso el dpi declarado solo se usa si está entre 100 y 600.
- **El tipo**: los TIFF dan el dpi como `IFDRational`, que no es `float` pero sí `numbers.Real`.
- **El redondeo**: un PNG guarda píxeles por metro, así que 100 dpi vuelve como 99,9998, y por eso la comparación se hace sobre el valor redondeado.

Además hay un tope de píxeles por página, `MAX_OCR_PIXELS` (`src/ingest/pipeline.py:74`). Un plano A0 a 300 dpi tendría 139 Mpx. Si una página supera el tope, se baja la resolución y se le informa al motor el dpi efectivo.

> **Pregunta**: si escaneás un formulario a 72 dpi y lo reescalás a 300, ¿recuperás calidad? ¿Por qué el pipeline igual reescala?

## 3. OCR y Tesseract, lo básico

**OCR** (*Optical Character Recognition*) es pasar de píxeles a caracteres. Tesseract lo hace en tres etapas:

1. **Binarización**: separa la tinta del fondo (blanco y negro).
2. **Análisis de página**: segmenta la página en bloques, líneas y palabras. Cómo lo hace lo controla el **psm** (*page segmentation mode*).
3. **Reconocimiento**: una red LSTM lee cada línea, ayudada por el modelo de idioma (`-l spa+eng`).

Los modos de segmentación que importan acá:

| psm | Qué supone | Cuándo conviene |
| --- | --- | --- |
| 3 (por defecto) | Nada: detecta los bloques solo | Páginas con varias columnas |
| 4 | Una sola columna de texto con tamaños variables | Formularios y tablas simples |
| 6 | Un único bloque uniforme | Texto corrido sin estructura |

`pytesseract` no es una librería de OCR: es un envoltorio del programa `tesseract`. Guarda la imagen en un archivo temporal, lanza el proceso y lee el resultado. Al leer su código instalado aparecieron dos sorpresas:

- **El timeout** lanza un `RuntimeError` genérico, no una excepción propia. Hay que atraparlo aparte (`src/ingest/tesseract.py:49`).
- **Las imágenes abiertas desde un JPEG** se vuelven a guardar en JPEG antes de pasarlas a Tesseract, o sea que pierden calidad otra vez. `image.convert("L")` devuelve una imagen sin formato, y entonces pytesseract la guarda en PNG, sin pérdida (`src/ingest/tesseract.py:39`).

> **Pregunta**: ¿qué psm elegirías para un boletín a dos columnas? ¿Qué le pasaría al texto con psm 6?

## 4. CER: la métrica de calidad

**Definición**:

CER = (S + D + I) / N

- S: sustituciones (un carácter cambiado por otro).
- D: borrados (caracteres de la referencia que faltan).
- I: inserciones (caracteres de más).
- N: cantidad de caracteres de la referencia.

El numerador es la distancia de Levenshtein a nivel de caracteres: la mínima cantidad de ediciones para pasar de un texto al otro. Está en `src/ingest/quality.py:15`, que usa `jiwer.cer(reference, hypothesis)`. Ojo: primero va la referencia.

**Ejemplo real del corpus** (`09-formulario-solicitud-vacaciones.pdf`): la referencia normalizada tiene N = 462 caracteres. Tesseract leyó "Antigüedad" como "Antigúedad", así que S = 1, D = 0 e I = 0. Entonces CER = 1/462 = 0,22 %. Fue el único error del documento.

**Normalizar antes de medir**: `normalize_for_cer` (`src/ingest/normalize.py:29`) pasa el texto a NFC y colapsa todos los blancos. Sin eso, cada salto de línea en otro lugar contaría como error, y estarías midiendo maquetación en lugar de reconocimiento.

**Lo que el CER no te dice**: el CER también mide el **orden**. En `13-formulario-rendicion-gastos.jpg`, Tesseract reconoció bien todos los caracteres. Pero con psm 3 leyó la columna "Concepto" de la tabla, siguió con el resto de la página y dejó la columna "Importe" al final. Resultado: CER de 23,81 %, con cero letras mal leídas. Son borrados e inserciones del texto desplazado.

**Promedio por documento** (lo que la spec llama "CER medio") contra **CER global** (todas las ediciones sobre todos los caracteres): con el primero, cada documento pesa lo mismo, sea largo o corto. El documento 13 es 1/6 del promedio de los escaneos limpios, aunque tenga menos texto que otros.

> **Pregunta**: el CER puede dar más de 100 %. ¿En qué situación pasa? (Pista: mirá qué cuenta el denominador.)

## 5. Texto de referencia sintético

**El problema**: para medir el CER necesitás el texto exacto de cada página. Con escaneos reales, alguien tiene que transcribirlos a mano: es caro, lento y también tiene errores.

**La solución**: generar los documentos. Así el texto de referencia se conoce por construcción. `layout_page` (`src/ingest/corpus/generate.py`) ubica cada línea en la página y, a la vez, devuelve esa misma línea como referencia.

**Reproducibilidad**: la misma semilla tiene que dar los mismos bytes. Para eso hacen falta dos cosas:

- **Un generador aleatorio por documento**: `np.random.default_rng([seed, index])` (`generate.py:240`). Si cambiás un documento, no se altera el ruido de los demás.
- **`Canvas(..., invariant=1)`** de reportlab (`generate.py:160`): saca la fecha de creación y el identificador aleatorio que reportlab mete en cada PDF. Sin esto, dos corridas darían archivos distintos aunque el contenido sea idéntico.

El test `test_generacion_con_la_misma_semilla_es_reproducible` regenera el corpus y lo compara contra el **manifiesto commiteado**, con el sha256 de cada archivo. En la primera ronda comparaba dos corridas entre sí, y la revisión marcó el problema: si alguien cambia el nivel de ruido, las dos corridas nuevas siguen siendo iguales entre sí, pero ya no son el corpus contra el que se midió. Anclar al manifiesto detecta ese cambio.

**Límite**: lo sintético es más fácil que lo real. El perfil ruidoso (ruido gaussiano sigma 35, rotación de 1 a 2°) dio CER 0,04 %. El ruido por píxel se promedia al bajar de 300 a 200 dpi, y la tinta sigue teniendo mucho contraste. Un escaneo real trae desenfoque, sombras y manchas que este corpus no simula.

> **Pregunta**: si el corpus sintético da CER cercano a 0, ¿qué podés afirmar sobre el OCR con documentos reales? ¿Y qué no?

## 6. Umbrales fijados antes de medir y separación entre desarrollo y prueba

**Pre-registro**: es fijar el criterio de éxito **antes** de ver los resultados (2 % para escaneo limpio y 8 % para ruidoso, decididos en la propuesta). Si fijás el umbral después de mirar el número, siempre "pasás", y la métrica deja de informar. Acá también se fijaron antes los perfiles de ruido: el commit `9f4273b` con el corpus es anterior a la primera corrida de OCR.

**Qué pasó en la ronda 1**: el escaneo limpio dio 4,04 % contra un umbral de 2 %, por el orden de lectura de una tabla (doc. 13). Con `--psm 4` o `--psm 6` bajaba a 0,07 % **en ese corpus**. Elegir psm 4 por eso habría sido ajustar el sistema mirando el set que lo evalúa. Es la misma razón por la que `evals/golden/` es de solo lectura (CLAUDE.md, regla 4).

**Separación entre desarrollo y prueba** (ronda 2, decisión 5). Hay dos conjuntos con roles distintos:

- **Validación (desarrollo)**: `data/corpus-validation/`, 6 escaneos nuevos, con otra semilla. Sirve para decidir.
- **Prueba**: `data/corpus/`. Sirve para reportar, y se usa una sola vez.

El orden quedó registrado en la historia de git:

1. Commit `7768799`: la regla de decisión, escrita en `design.md` antes de que existiera el set de validación. Candidatos psm 3, 4 y 6. Gana el de menor CER medio por página escaneada, y un empate con psm 3 (menos de 0,1 pp) se resuelve a favor de psm 3. Está implementada en `src/ingest/psm_selection.py:37` (`choose_psm`), con tests de la regla antes del código.
2. Commit `37a4454`: el set de validación. Lleva 2 documentos a dos columnas, 2 formularios con tabla y 2 textos corridos, una composición fijada sin haber medido.
3. Commit `76145f8`: la medición sobre la validación. Resultado: psm 3 0,13 %, psm 4 11,17 % y psm 6 18,40 %, así que se eligió psm 3.
4. Commit `ffe6d79`: la única corrida del corpus de prueba con psm 3. El escaneo limpio dio 4,04 % y no se ajustó nada más. El test quedó como falla declarada (sección 10).

**La lección**: en el set de prueba, psm 4 parecía la solución. En la validación, que tiene documentos a dos columnas, rompe la lectura: el boletín pasa de 0,13 % a 60,92 %. Sin la separación, habrías puesto en producción un modo que destruye todos los documentos a dos columnas, y con números que "lo probaban".

¿Por qué escribir la regla antes? Porque si mirás los números primero, siempre aparece una regla razonable que favorece al ganador: "promedio por documento", "solo los limpios", "empate con 0,5 pp". La regla commiteada antes de medir le quita ese grado de libertad a quien decide.

> **Pregunta**: si probás 10 configuraciones de Tesseract sobre el mismo corpus y te quedás con la mejor, ¿qué tan confiable es su CER como estimación para documentos nuevos? ¿Qué cambia si las probás sobre la validación y reportás la prueba?

## 7. Hash de contenido e idempotencia

**Idempotente**: correr dos veces da el mismo resultado que correr una vez. Acá la segunda corrida omite los 20 documentos en 0,02 s, sin una sola llamada al OCR (`evals/runs/ingest/corpus_76145f8_psm3_reingesta.json`).

**`doc_id` = sha256 del archivo** (`src/ingest/pipeline.py:144`):

- El mismo contenido da el mismo id, aunque cambien el nombre o la carpeta.
- Si cambia un solo byte, cambia el id.

Si se usara el nombre del archivo, renombrarlo duplicaría el documento, y editar su contenido sin renombrarlo dejaría la salida vieja.

**La clave de idempotencia es el `doc_id` más la configuración.** En la ronda 1, el salteo miraba solo el `doc_id` y la `PIPELINE_VERSION`. Si reingestabas en el mismo directorio con otro psm, el pipeline omitía todo y te quedabas con la salida vieja, sin ningún aviso.

Ahora la salida guarda `ocr_engine` y `config_hash` (`config_hash`, `src/ingest/pipeline.py:116`): el sha256 de un JSON canónico, con claves ordenadas, que tiene la versión del pipeline, los umbrales de detección, el dpi, los idiomas, el psm y el nombre del motor. Un documento se omite solo si coinciden el `doc_id` **y** el `config_hash` (`pipeline.py:134` y `pipeline.py:345`).

El timeout **no** entra en la huella: cambiarlo no cambia el texto que sale. La regla general es que entra todo lo que cambia la salida, y nada más. Si metieras algo que no la cambia, cada ajuste irrelevante forzaría a reprocesar todo.

`PIPELINE_VERSION` (`pipeline.py:51`) sigue existiendo para los cambios de lógica, que no son configuración. Pasó de 1 a 2 cuando cambió el esquema de la salida.

**Escritura atómica** (`pipeline.py:113`): primero se escribe un `.tmp` y después se hace `os.replace`. Si el proceso se corta a la mitad, no queda un JSONL cortado que la próxima corrida tome por válido.

> **Pregunta**: dos archivos con distinto nombre e idéntico contenido entran en el mismo lote. ¿Cuántos JSONL quedan y qué estado tiene cada uno en el reporte?

## 8. Protocol para el motor de OCR, y fakes

`OCREngine` (`src/ingest/ocr.py:19`) es un `Protocol`, o sea un **tipado estructural**: cualquier clase que tenga `name` y `recognize(image, *, dpi)` cumple el contrato sin heredar de nada. `TesseractEngine` no importa el Protocol. El pipeline depende de la interfaz, nunca de pytesseract.

Esto habilita dos cosas:

- **Tests sin Tesseract**: `FakeOCREngine` (`tests/fakes.py:24`) registra cada imagen que recibe, con su ancho, alto y dpi. Así, el test del PDF mixto verifica que hubo **exactamente una** llamada al OCR y que la página llegó a 300 dpi. `FailingOCREngine` (`tests/fakes.py:37`) simula un Tesseract caído.
- **Comparar motores**: un OCR en la nube sería otra clase con los mismos dos miembros.

**Fakes fieles** (ronda 2, hallazgo 5). Un fake que ignora la imagen es ciego a una parte de la lógica. Para demostrarlo, se rompió el pipeline a propósito de tres maneras, una por vez (un *test de mutación*):

1. Rasterizar la página siguiente en lugar de la correcta.
2. Mandar al OCR una imagen en blanco.
3. No normalizar el texto que devuelve el OCR.

**Ninguno** de los tests rápidos de la ronda 1 falló. Por eso se agregaron dos fakes nuevos:

- `PixelMeanOCREngine` (`tests/fakes.py:61`) "lee" el brillo medio de la imagen que recibe. El test arma un PDF con dos páginas escaneadas de brillos distintos (una mitad negra y otra gris oscuro) y verifica que cada página llegue con su propia media. Atrapa las mutaciones 1 y 2.
- `DirtyTextOCREngine` (`tests/fakes.py:49`) devuelve `"  Página\t uno \n\n\n\x0c"`, con el salto de página `\x0c` que Tesseract agrega al final, y el test exige `"Página uno"`. Atrapa la mutación 3.

**Un fake con comportamiento no alcanza**: también tiene que **depender de la entrada** que querés verificar.

La CI corre solo la suite rápida (`addopts = -m 'not integration'`, `pyproject.toml:74`). Los tests con Tesseract real llevan `@pytest.mark.integration` y se corren con `uv run pytest -m integration`. El adaptador de Tesseract también tiene tests sin el binario: reemplazan `pytesseract.image_to_string` con `monkeypatch` para simular un timeout, un `TesseractError` y un Tesseract no instalado.

> **Pregunta**: `FakeOCREngine` devuelve un texto que no tiene nada que ver con la imagen. ¿Qué escenarios de la spec **no** puede probar entonces, y dónde se prueban?

## 9. Aislar los errores en un lote

Cada archivo se procesa en su propio bloque `try` (`src/ingest/pipeline.py:303`). Un error se convierte en un código y queda en el reporte. Después, el lote sigue con el siguiente archivo. Los códigos son:

- `unsupported_format`: formato no soportado.
- `unreadable_file`: el archivo no se puede leer.
- `ocr_failed`: el OCR falló.
- `invalid_ground_truth`: el texto de referencia está roto.

**Qué atrapar** (ronda 2, hallazgo 3): en la ronda 1, solo se atrapaban los errores "esperados" (`PdfReadError` o una imagen no reconocida). Después aparecieron dos huecos:

- Una bomba de descompresión (una imagen chica en disco que ocupa gigas en memoria): Pillow lanza `DecompressionBombError`, que **no** hereda de `OSError`.
- Un `RuntimeError` de pymupdf dentro de una página.

Cualquiera de los dos cortaba el lote entero. Ahora las familias de errores de las librerías (`_UNREADABLE_ERRORS`, `pipeline.py:83`) se reportan como `unreadable_file`. Un `except Exception` genérico se evitó a propósito: un `AttributeError` es un bug tuyo y tiene que verse, no esconderse como "archivo ilegible".

La alternativa, *fail-fast* (cortar en el primer error), es buena en un script interactivo. Pero en una ingesta de miles de documentos, un PDF corrupto no puede frenar todo.

El riesgo del aislamiento es **tragarse los errores**. Por eso hay dos salvaguardas:

- La sección "Errores" del reporte.
- El código de salida 1 de la CLI cuando algún documento falló.

> **Pregunta**: ¿por qué `unsupported_format` no genera un JSONL vacío para ese documento?

## 10. Qué mostró la validación, y cómo convivir con un test que no pasa

**La validación evitó un error concreto.** En el corpus de prueba, psm 4 parecía la solución: el escaneo limpio pasaba de 4,04 % a 0,07 %. En el set de validación, el mismo psm 4 llevó el boletín a dos columnas de 0,13 % a **60,92 %**, y el CER medio por página escaneada de 0,13 % a 11,17 %. Si se hubiera adoptado mirando la prueba, cada documento a dos columnas que entrara después se habría ingestado con las líneas mezcladas, y el RAG habría respondido con texto revuelto.

La **regla preregistrada** fue lo que impidió ese error. Antes de ver un solo número de la validación, ya estaba escrito qué se iba a comparar y cómo se desempataba. Con la regla fijada de antemano, no quedó margen para elegir la métrica que favoreciera al candidato que "queríamos" que ganara.

**Tres maneras de manejar un umbral que no se cumple**:

| Opción | Qué pasa | Problema |
| --- | --- | --- |
| Mover el umbral (2 % → 5 %) | El test pasa | La métrica deja de informar: el umbral se fijó antes de medir justamente para que no se pudiera hacer esto |
| Dejar el test en rojo | La falla es honesta | Si la CI corre los tests de integración, queda roja para siempre. Es una *ventana rota*: todos se acostumbran al rojo y la próxima regresión real pasa inadvertida |
| `@pytest.mark.xfail(strict=True, reason=...)` | La falla queda **declarada**: aparece como `xfailed` en cada corrida, con la causa y el lugar donde se resuelve (`improve-ocr-quality`) | Hay que escribir un buen `reason` y tener una change que lo resuelva |

El `strict=True` le pone vencimiento a la marca. Si el test empieza a pasar (XPASS), pytest lo cuenta como **fallo**, así que nadie se puede olvidar el `xfail` puesto. Se comprobó corriendo la integración con `INGEST_OCR_PSM=4`: el test pasó y la suite dio `XPASS(strict)` → 1 failed. Sin `strict`, ese pase habría quedado como un aviso que nadie lee.

Lo que **no** se tocó: la aserción `stats.mean_cer <= CLEAN_SCAN_MAX_CER` y el umbral. El `xfail` declara que el sistema no cumple el contrato; no cambia el contrato.

> **Pregunta**: ¿por qué un `xfail` sin `strict` es peor que uno con `strict` justo el día en que alguien arregla el problema en `improve-ocr-quality`?

## Decisiones y su porqué

| Decisión | Por qué | Alternativa descartada |
| --- | --- | --- |
| `pymupdf>=1.28.2,<2` | La serie 2.x obliga a instalar onnxruntime (73 MB) y paquetes de layout y LLM que no se usan | pypdf + pypdfium2: dos librerías en lugar de una |
| pytesseract con un stub de tipos local (`stubs/pytesseract`) | No trae tipos ni tiene stubs en typeshed. El stub cubre los 4 símbolos que se usan, con las firmas copiadas del código instalado | Llamar a `tesseract` con `subprocess`: más control, pero reimplementa lo que la librería ya hace |
| `untyped_calls_exclude = ["pymupdf"]` y validación en `pdf.py` | pymupdf trae `py.typed`, pero `get_text` no tiene anotaciones. Se aísla en un módulo que chequea cada tipo | Un `# type: ignore` en cada llamada |
| Un JSONL por documento, con una sola línea | Si concatenás los archivos, obtenés el JSONL del corpus. El nombre del archivo es el `doc_id` | Un JSONL por página: el registro de la spec es por documento |
| La salida conserva los saltos de línea | `add-rag-core` los usa para detectar títulos al hacer chunking | Aplanar todo, como para el CER |
| `xfail(strict=True)` en el escenario de escaneo limpio | Falla declarada y visible, con vencimiento; la CI no queda roja para siempre | Dejar el test en rojo o mover el umbral |
| psm 3 como valor por defecto | Lo eligió la regla preregistrada sobre el set de validación (0,13 % contra 11,17 % y 18,40 %) | psm 4: pasaba el umbral en el set de prueba, pero rompe los documentos a dos columnas |
| `config_hash` en la clave de idempotencia | Un cambio de configuración tiene que forzar el reprocesamiento | Solo `doc_id` + versión: deja salidas viejas sin avisar |
| dpi declarado solo entre 100 y 600, con tope de 40 Mpx | 72 dpi es un valor por defecto, no un dato; un plano enorme no puede tumbar el proceso | Creer siempre en el metadato |
| `_typed` valida en tiempo de ejecución todo lo que pymupdf entrega como `Any` | mypy no puede verificar lo que no tiene anotaciones. La validación encontró que `needs_pass` devuelve `int`, no `bool` | Confiar en los nombres de los atributos |
| Perfiles de ruido fijados antes de medir | Para que el umbral de la spec signifique algo | Subir el ruido después de ver 0,04 % |

## Errores típicos

- Decidir nativo o escaneado por documento: los PDFs mixtos quedan mal.
- Un umbral de detección bajo: las páginas escaneadas con un sello se toman como nativas y su contenido se pierde **sin error**.
- Medir el CER sin normalizar los blancos: terminás midiendo dónde corta cada línea.
- Pasar los argumentos de `jiwer.cer` al revés (hipótesis primero): el denominador pasa a ser el largo de la hipótesis y el número cambia.
- Ajustar la configuración del OCR mirando el mismo corpus que la evalúa, en lugar de separar validación y prueba y escribir la regla antes de medir.
- Fakes que ignoran la entrada: pasan aunque el pipeline mande la página equivocada.
- Creer el dpi de los metadatos sin acotarlo (72 dpi por defecto) y no poner tope de píxeles.
- Atrapar solo `OSError` con Pillow: `DecompressionBombError` no hereda de ahí.
- Usar como `doc_id` el hash del nombre o de la ruta, o saltear sin tener en cuenta la versión del pipeline y la configuración.
- Escribir la salida directamente al archivo final (no atómico).
- Un generador "con semilla" que no es reproducible: fechas dentro del PDF, o un generador aleatorio global compartido entre documentos.
- Creer que una librería está tipada porque trae `py.typed`: pymupdf lo trae y `get_text` igual devuelve `Any`.

## Preguntas de entrevista

1. **¿Cómo decidís si una página de un PDF necesita OCR?** Por página: cuántos caracteres extraíbles tiene la capa de texto (acá, 50 o más) y qué proporción son imprimibles (90 % o más, para detectar capas rotas). Si no cumple, se rasteriza la página completa y va a OCR. El umbral es conservador porque tomar como nativa una página escaneada pierde contenido en silencio.
2. **¿Qué mide el CER y qué no?** Mide la distancia de edición a nivel de caracteres dividida por el largo de la referencia: sustituciones, borrados e inserciones. No distingue un carácter mal leído de un texto bien leído en otro orden. Una tabla leída columna por columna puede dar 24 % de CER con cero letras mal leídas.
3. **¿Por qué el `doc_id` es un hash del contenido y qué más entra en la clave de idempotencia?** El hash es estable ante renombres y cambia ante cualquier edición. Pero la clave completa es el `doc_id` más una huella de la configuración que cambia la salida (versión, umbrales, dpi, idiomas, psm y motor). Si no, reingestar con otro psm devuelve resultados viejos sin avisar.
4. **¿Cómo testeás un pipeline de OCR en CI sin instalar Tesseract?** Con el motor detrás de un `Protocol` y un fake que registra qué imágenes recibe, para verificar qué páginas van a OCR y a qué resolución. Los umbrales de calidad con el motor real van en tests `integration`, fuera de la suite rápida.
5. **Tu métrica no llega al umbral acordado. ¿Qué hacés?** No mover el umbral ni el set de prueba. Primero diagnosticar la causa (acá, el orden de lectura y no el reconocimiento). Después escribir la regla de decisión, elegir la configuración sobre un set de validación aparte y correr la prueba una sola vez. Si sigue sin llegar, se reporta tal cual. En esta change, psm 4 "arreglaba" la prueba, pero la validación mostró que rompe los documentos a dos columnas.
