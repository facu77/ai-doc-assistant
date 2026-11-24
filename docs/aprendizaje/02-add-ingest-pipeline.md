# 02 · add-ingest-pipeline: de PDFs y escaneos a texto medido

Qué se construyó en esta change y qué conceptos hay detrás. El RAG solo puede ser tan bueno como el texto que recibe, y esta change produce ese texto: un JSONL por documento, con el texto por página, el método de extracción y una medida de calidad (el CER). Todo lo que sigue apunta a código real del repo y a números de la corrida registrada en `pipelines/ingest/REPORT.md`.

## 1. PDF nativo y PDF escaneado: la capa de texto

**Qué es**: un PDF puede guardar texto de dos maneras.

- **Nativo**: cada carácter está guardado como carácter, con su fuente y su posición. Esa información forma la *capa de texto*, y se lee sin OCR. Por ejemplo, `data/corpus/01-politica-licencias.pdf`.
- **Escaneado**: la página es una foto. No hay caracteres, solo píxeles. Por ejemplo, `data/corpus/09-formulario-solicitud-vacaciones.pdf`.

La capa de texto se lee con `page.get_text("text")`, en `src/ingest/pdf.py:48`.

**El problema**: un mismo PDF puede mezclar los dos tipos. `19-manual-evaluacion-desempeno.pdf` tiene las páginas 1 y 3 nativas y la 2 escaneada. Por eso se decide **por página** y no por documento.

**La regla** está en `src/ingest/detection.py:41`. Una página es nativa si tiene al menos 50 caracteres no blancos y al menos el 90 % de ellos son imprimibles. El ratio sirve para atrapar capas de texto rotas. Un caso típico son las fuentes sin tabla `ToUnicode`, que se extraen como `U+FFFD` (el carácter de reemplazo). Esa página "tiene texto", pero el texto es basura.

**El caso borde del sello**: la página 2 de `20-constancia-capacitacion.pdf` es una imagen con un sello que tiene capa de texto: "RECIBIDO RRHH 02/11/2026", 24 caracteres. Como no llega a 50, la página va a OCR. Además se rasteriza la página **completa** (`src/ingest/pipeline.py:142`), así que el OCR lee la imagen y el sello juntos.

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

El rasterizado está en `src/ingest/pdf.py:57` (`get_pixmap(dpi=..., colorspace=GRAY)`). Las imágenes sueltas que declaran otra resolución en sus metadatos (por ejemplo, los `.jpg` del corpus vienen a 200 dpi) se reescalan a 300 dpi (`src/ingest/pipeline.py:174`). Así todas las páginas llegan al OCR con el mismo criterio.

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

- **Un generador aleatorio por documento**: `np.random.default_rng([seed, index])` (`generate.py:204`). Si cambiás un documento, no se altera el ruido de los demás.
- **`Canvas(..., invariant=1)`** de reportlab (`generate.py:129`): saca la fecha de creación y el identificador aleatorio que reportlab mete en cada PDF. Sin esto, dos corridas darían archivos distintos aunque el contenido sea idéntico.

El test `test_generacion_con_la_misma_semilla_es_reproducible` genera el corpus dos veces y compara los bytes.

**Límite**: lo sintético es más fácil que lo real. El perfil ruidoso (ruido gaussiano sigma 35, rotación de 1 a 2°) dio CER 0,04 %. El ruido por píxel se promedia al bajar de 300 a 200 dpi, y la tinta sigue teniendo mucho contraste. Un escaneo real trae desenfoque, sombras y manchas que este corpus no simula.

> **Pregunta**: si el corpus sintético da CER cercano a 0, ¿qué podés afirmar sobre el OCR con documentos reales? ¿Y qué no?

## 6. Umbrales fijados antes de medir

**Qué es**: fijar el criterio de éxito **antes** de ver los resultados (2 % para escaneo limpio y 8 % para ruidoso, decididos en la propuesta). En ciencia se llama *pre-registro*. Si fijás el umbral después de mirar el número, siempre "pasás", y la métrica deja de informar.

Acá también se fijaron **antes** los perfiles de ruido: el commit `9f4273b` con el corpus es anterior a la primera corrida de OCR.

**Qué pasó**: el escaneo limpio dio 4,04 %, por encima del 2 %. No se movió el umbral ni se tocó el corpus. Lo que sí se hizo:

1. **Diagnosticar**: el error venía del orden de lectura en el documento 13, no del reconocimiento.
2. **Experimentar con una sola variable**: con `--psm 4` o `--psm 6`, el CER limpio baja a 0,07 %.
3. **No adoptar el resultado**: elegir psm 4 *porque anda en este corpus* es ajustar el sistema mirando el set de evaluación. Es la misma razón por la que `evals/golden/` es de solo lectura (CLAUDE.md, regla 4).

La recomendación quedó en las Preguntas abiertas: validar psm 4 con documentos nuevos (un conjunto de retención, o *holdout*: datos que no se usan para decidir) antes de cambiar el valor por defecto.

> **Pregunta**: si probás 10 configuraciones de Tesseract sobre el mismo corpus y te quedás con la mejor, ¿qué tan confiable es su CER como estimación para documentos nuevos?

## 7. Hash de contenido e idempotencia

**Idempotente**: correr dos veces da el mismo resultado que correr una vez. Acá la segunda corrida omite los 20 documentos en 0,03 s, sin una sola llamada al OCR.

**`doc_id` = sha256 del archivo** (`src/ingest/pipeline.py:91`):

- El mismo contenido da el mismo id, aunque cambien el nombre o la carpeta.
- Si cambia un solo byte, cambia el id.

Si se usara el nombre del archivo, renombrarlo duplicaría el documento, y editar su contenido sin renombrarlo dejaría la salida vieja.

El salteo está en `pipeline.py:81` y `pipeline.py:268`. Se omite un documento solo si existe su salida **y** tiene la misma `PIPELINE_VERSION` (`pipeline.py:40`). La versión existe para invalidar resultados cuando cambia la lógica: si mejorás la normalización y no la subís, los documentos viejos quedan con la normalización anterior.

**Escritura atómica** (`pipeline.py:78`): primero se escribe un `.tmp` y después se hace `os.replace`. Si el proceso se corta a la mitad, no queda un JSONL cortado que la próxima corrida tome por válido.

**Límite conocido**: cambiar la configuración (umbrales, dpi, psm) no invalida el salteo (Pregunta abierta 4).

> **Pregunta**: dos archivos con distinto nombre e idéntico contenido entran en el mismo lote. ¿Cuántos JSONL quedan y qué estado tiene cada uno en el reporte?

## 8. Protocol para el motor de OCR, y fakes

`OCREngine` (`src/ingest/ocr.py:19`) es un `Protocol`, o sea un **tipado estructural**: cualquier clase que tenga `name` y `recognize(image, *, dpi)` cumple el contrato sin heredar de nada. `TesseractEngine` no importa el Protocol. El pipeline depende de la interfaz, nunca de pytesseract.

Esto habilita dos cosas:

- **Tests sin Tesseract**: `FakeOCREngine` (`tests/fakes.py:24`) registra cada imagen que recibe, con su ancho, alto y dpi. Así, el test del PDF mixto verifica que hubo **exactamente una** llamada al OCR y que la página llegó a 300 dpi. Un `MagicMock` que devuelve un texto fijo no te dejaría ver *qué* páginas fueron al OCR, que es justo la lógica bajo prueba. `FailingOCREngine` (`tests/fakes.py:37`) simula un Tesseract caído.
- **Comparar motores**: un OCR en la nube sería otra clase con los mismos dos miembros.

La CI corre solo la suite rápida (`addopts = -m 'not integration'`, `pyproject.toml:73`). Los tests con Tesseract real llevan `@pytest.mark.integration` y se corren con `uv run pytest -m integration`.

> **Pregunta**: el fake devuelve un texto que no tiene nada que ver con la imagen. ¿Qué escenarios de la spec **no** puede probar entonces, y dónde se prueban?

## 9. Aislar los errores en un lote

Cada archivo se procesa en su propio bloque `try`. Un error se convierte en un `_DocumentError` con un código (`unsupported_format`, `unreadable_file` u `ocr_failed`) y queda en el reporte. Después, el lote sigue con el siguiente archivo (`src/ingest/pipeline.py:233`).

La alternativa, *fail-fast* (cortar en el primer error), es buena en un script interactivo. Pero en una ingesta de miles de documentos, un PDF corrupto no puede frenar todo.

El riesgo del aislamiento es **tragarse los errores**. Por eso hay dos salvaguardas:

- La sección "Errores" del reporte.
- El código de salida 1 de la CLI cuando algún documento falló.

> **Pregunta**: ¿por qué `unsupported_format` no genera un JSONL vacío para ese documento?

## Decisiones y su porqué

| Decisión | Por qué | Alternativa descartada |
| --- | --- | --- |
| `pymupdf>=1.28.2,<2` | La serie 2.x obliga a instalar onnxruntime (73 MB) y paquetes de layout y LLM que no se usan | pypdf + pypdfium2: dos librerías en lugar de una |
| pytesseract con un stub de tipos local (`stubs/pytesseract`) | No trae tipos ni tiene stubs en typeshed. El stub cubre los 4 símbolos que se usan, con las firmas copiadas del código instalado | Llamar a `tesseract` con `subprocess`: más control, pero reimplementa lo que la librería ya hace |
| `untyped_calls_exclude = ["pymupdf"]` y validación en `pdf.py` | pymupdf trae `py.typed`, pero `get_text` no tiene anotaciones. Se aísla en un módulo que chequea cada tipo | Un `# type: ignore` en cada llamada |
| Un JSONL por documento, con una sola línea | Si concatenás los archivos, obtenés el JSONL del corpus. El nombre del archivo es el `doc_id` | Un JSONL por página: el registro de la spec es por documento |
| La salida conserva los saltos de línea | `add-rag-core` los usa para detectar títulos al hacer chunking | Aplanar todo, como para el CER |
| psm 3 se queda como valor por defecto | Cambiarlo sería decidir mirando el corpus de evaluación | psm 4 (pasa el umbral; pendiente de validar con un holdout) |
| Perfiles de ruido fijados antes de medir | Para que el umbral de la spec signifique algo | Subir el ruido después de ver 0,04 % |

## Errores típicos

- Decidir nativo o escaneado por documento: los PDFs mixtos quedan mal.
- Un umbral de detección bajo: las páginas escaneadas con un sello se toman como nativas y su contenido se pierde **sin error**.
- Medir el CER sin normalizar los blancos: terminás midiendo dónde corta cada línea.
- Pasar los argumentos de `jiwer.cer` al revés (hipótesis primero): el denominador pasa a ser el largo de la hipótesis y el número cambia.
- Ajustar la configuración del OCR mirando el mismo corpus que la evalúa.
- Usar como `doc_id` el hash del nombre o de la ruta, o saltear sin guardar la versión del pipeline.
- Escribir la salida directamente al archivo final (no atómico).
- Un generador "con semilla" que no es reproducible: fechas dentro del PDF, o un generador aleatorio global compartido entre documentos.
- Creer que una librería está tipada porque trae `py.typed`: pymupdf lo trae y `get_text` igual devuelve `Any`.

## Preguntas de entrevista

1. **¿Cómo decidís si una página de un PDF necesita OCR?** Por página: cuántos caracteres extraíbles tiene la capa de texto (acá, 50 o más) y qué proporción son imprimibles (90 % o más, para detectar capas rotas). Si no cumple, se rasteriza la página completa y va a OCR. El umbral es conservador porque tomar como nativa una página escaneada pierde contenido en silencio.
2. **¿Qué mide el CER y qué no?** Mide la distancia de edición a nivel de caracteres dividida por el largo de la referencia: sustituciones, borrados e inserciones. No distingue un carácter mal leído de un texto bien leído en otro orden. Una tabla leída columna por columna puede dar 24 % de CER con cero letras mal leídas.
3. **¿Por qué el `doc_id` es un hash del contenido?** Porque es estable ante renombres y cambia ante cualquier edición. Junto con la versión del pipeline, permite saltear lo ya procesado (idempotencia) sin duplicar ni dejar salidas viejas.
4. **¿Cómo testeás un pipeline de OCR en CI sin instalar Tesseract?** Con el motor detrás de un `Protocol` y un fake que registra qué imágenes recibe, para verificar qué páginas van a OCR y a qué resolución. Los umbrales de calidad con el motor real van en tests `integration`, fuera de la suite rápida.
5. **Tu métrica no llega al umbral acordado. ¿Qué hacés?** No mover el umbral ni el set de evaluación. Diagnosticar la causa (acá, el orden de lectura y no el reconocimiento), probar los cambios de a una variable y documentarlos. Antes de adoptar un cambio elegido mirando ese set, validarlo con datos nuevos.
