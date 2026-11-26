# Proposal

## Why

El RAG solo puede ser tan bueno como el texto que recibe. El POC tiene que demostrar una ingesta real de PDFs nativos y escaneados con OCR medido (CER), no texto copiado a mano. Además, es un requisito excluyente del perfil buscado.

## What Changes

- Un pipeline de ingesta en `pipelines/ingest` (proyecto `uv` propio) que toma PDFs e imágenes y produce documentos normalizados en JSONL: texto por página, metadatos, estructura (títulos y tablas, cuando se detectan) y método de extracción.
- Detección por página entre texto nativo y escaneo, con OCR solo donde hace falta.
- Un corpus de 20 documentos **ficticios** de políticas internas y RRHH de la empresa ficticia "Acme S.A.", generados con un script. Mezcla nativos, escaneos simulados (texto renderizado a imagen con ruido) y mixtos. Así el texto de referencia es conocido y el CER es medible.
- Un reporte de ingesta (JSON y Markdown) con el método por página, el CER por documento, el tiempo y los errores.
- Idempotencia por hash de contenido.

## Capabilities

### New Capabilities
- `document-ingestion`: extracción de texto y estructura desde PDFs e imágenes, con OCR selectivo, normalización, idempotencia y reporte de calidad.

### Modified Capabilities

## Impact

- Código nuevo: `pipelines/ingest/` (pyproject, src y tests).
- Corpus: `data/corpus/` (ficticio y versionado) con su `ground_truth/`.
- Dependencias del sistema: `tesseract-ocr` con el paquete de idioma `spa`. Hay que documentarlas en el README y en el Dockerfile.
- Dependencias de Python candidatas: `pymupdf` o `pypdf`, `pytesseract` u `ocrmypdf`, `pillow` y `jiwer` (para el CER).

## Decisiones tomadas (2026-11-24)

1. **Motor de OCR**: Tesseract (`spa+eng`), local, detrás de `OCREngine`. Comparar contra un OCR en la nube queda como experimento opcional, fuera de esta change.
2. **Umbrales de CER**, fijados antes de medir: 2% como máximo para escaneo limpio y 8% como máximo para escaneo ruidoso. Si no se alcanzan, no se mueve el umbral: se documenta y se mejora el preprocesamiento.
3. **Dominio del corpus**: políticas internas y RRHH de la empresa ficticia "Acme S.A." (licencias, viáticos, beneficios, código de conducta, formularios escaneados). Sirve de base al set de oro (`add-rag-core`), a los casos de PII y a las ACL (`add-observability-security`).
4. **Tablas**: se extraen como texto plano y se documenta como limitación. La estructura de títulos y secciones se aprovecha en el experimento de chunking de `add-rag-core`.

## Decisiones tomadas (2026-11-26)

5. **Umbral de escaneo limpio: separación entre desarrollo y prueba (opción B de la pregunta abierta 1).** El modo de segmentación (psm) se elige con una regla escrita antes de medir (ver `design.md`, "Selección del psm"). La regla se aplica sobre un set de validación aparte (`data/corpus-validation/`, otra semilla, 6 escaneos con al menos un documento a dos columnas y al menos un formulario con tabla). El corpus original queda como set de prueba: se corre una sola vez con el psm elegido y se reporta tal cual. Si el escaneo limpio sigue por encima del 2 %, el test queda en rojo y no se ajusta nada más.
6. **Perfil ruidoso**: queda como está en esta change. Un perfil más difícil, con su umbral fijado antes de medir, va a una change posterior.
7. **La configuración entra en la clave de idempotencia (pregunta abierta 4)**. `IngestedDocument` guarda `ocr_engine` y un hash de la configuración efectiva. Se omite un documento solo si coinciden el `doc_id` y ese hash. La spec suma el escenario "Cambio de configuración fuerza reprocesamiento".
8. **El escaneo limpio queda como falla declarada, con una change de seguimiento (pregunta abierta 8, "opción C" del autor).** En la lista de la pregunta, esta decisión combina el `xfail` estricto (B) con la change posterior (C). El test `test_cer_medio_de_escaneos_limpios_es_a_lo_sumo_2_por_ciento` se marca `@pytest.mark.xfail(strict=True)`, con la causa en el `reason`. La aserción y el umbral de 2 % no cambian. La solución se trabaja en `improve-ocr-quality`. Por qué:
   - **Un test rojo permanente es una ventana rota.** Con la CI corriendo los tests de integración, todos aprenden a ignorar el rojo, y la próxima regresión real pasa inadvertida.
   - **Mover el umbral sería hacer trampa**: la métrica deja de informar.
   - **`xfail(strict=True)` es una falla declarada, visible y con vencimiento.** Aparece como `xfailed` en cada corrida, el `reason` dice por qué y dónde se resuelve, y si un día el test pasa, `strict` lo convierte en fallo (XPASS) y obliga a sacar la marca. Se comprobó con `INGEST_OCR_PSM=4`: el test pasa y pytest reporta `XPASS(strict)` como fallo.

9. **Gate de regresión del escaneo limpio** (revisión 2). Hay un test de integración aparte, sin `xfail`, que falla si el CER medio limpio supera la línea base registrada + 0,5 pp. La línea base se lee de `evals/runs/ingest/corpus_76145f8_psm3.json`, no está escrita a mano. Es un gate de regresión, distinto del umbral de 2 % de la spec, que sigue siendo el objetivo. Spec: requisito "Sin regresión de calidad de OCR".
10. **Un texto de referencia ilegible no bloquea la ingesta** (revisión 2). El documento se ingiere igual, con `cer=None` y el aviso `invalid_ground_truth` con su detalle en el reporte. El reporte cuenta los avisos aparte de los errores, y un aviso no cambia el código de salida de la CLI. Spec: escenario "Texto de referencia ilegible".

## Preguntas abiertas

Surgieron al implementar (2026-11-24). Las mediciones están en `pipelines/ingest/REPORT.md`.

1. **(Resuelta: decisión 5.) El escaneo limpio no cumple el umbral: 4,04 % contra 2 %.** Casi todo el error viene de un documento con una tabla (`13-formulario-rendicion-gastos.jpg`, 23,81 %). Tesseract reconoce bien los caracteres, pero en modo psm 3 lee una columna entera antes que la otra. Con psm 4 o psm 6, el CER limpio baja a 0,07 %. El umbral no se movió y el test de integración queda en rojo.
   - A. Mantener psm 3 y aceptar el rojo hasta que haya manejo de tablas. A favor: no se ajusta nada mirando el corpus de evaluación. En contra: la change no cumple su definición de terminado.
   - B. Pasar el valor por defecto a psm 4. A favor: un cambio de una línea que lee las tablas fila por fila. En contra: se elige mirando el mismo corpus que mide el resultado (sobreajuste) y psm 4 supone una sola columna.
   - C. Elegir el psm por página (psm 3 en general y psm 4 o 6 si se detecta una tabla), o reordenar la salida de `image_to_data` por líneas. A favor: es general. En contra: más código, y las tablas son un non-goal de esta change.
   - D. Medir también un CER que no dependa del orden de lectura. En contra: cambia la definición del CER que fija el design (`jiwer.cer`).
   - **Recomendación**: B, pero validado contra un conjunto de retención. Se generan con otra semilla de 4 a 6 documentos nuevos que no se usan para decidir, incluido uno a dos columnas, y psm 4 se adopta solo si no empeora en ellos. Si se adopta, hay que subir `PIPELINE_VERSION`.
2. **(Resuelta: decisión 6.) El perfil ruidoso resultó fácil: 0,04 %.** El escenario pasa sin discriminar entre los dos perfiles.
   - A. Dejarlo como está, porque se fijó antes de medir.
   - B. Agregar en otra change un perfil "ruidoso v2" (desenfoque, bajo contraste, manchas, 150 dpi) y reportarlo aparte, sin reemplazar la medición actual.
   - C. Sumar escaneos reales anonimizados.
   - **Recomendación**: A para esta change y B como change futura.
3. **Estructura de títulos y tablas.** "What Changes" la menciona, pero ningún requirement de la spec la pide, así que no se implementó. La salida conserva los saltos de línea para que `add-rag-core` detecte los títulos.
   - **Recomendación**: resolverla en `add-rag-core`, que es donde se usa.
4. **(Resuelta: decisión 7.) Cambiar la configuración no invalida el salteo.** Para decidir si omite un documento, el pipeline mira solo el `doc_id` y la versión del pipeline. Si se reingesta en el mismo directorio con otros umbrales, otro dpi u otro psm, el documento se omite.
   - A. Documentarlo: hoy se usa otro `--out` o se sube la versión.
   - B. Guardar un hash de la configuración junto con la versión.
   - C. Agregar un flag `--force`.
   - **Recomendación**: B, porque es chico y evita resultados viejos sin aviso.
5. **Archivos compartidos pendientes para la integración.** Hay que hacer estos cambios al integrar, porque estos archivos los toca en paralelo `add-llm-client`:
   - Documentar las variables `INGEST_*` en `.env.example`: `MIN_NATIVE_CHARS`, `MIN_PRINTABLE_RATIO`, `OCR_DPI`, `OCR_LANG`, `OCR_PSM` y `OCR_TIMEOUT_S`.
   - Agregar `cd pipelines/ingest && uv sync` a `make install`.
   - El Dockerfile con `tesseract-ocr-spa` que menciona "Impact" queda para `add-deploy-and-ci`.
8. **(Resuelta: decisión 8.) El escaneo limpio sigue sin cumplir el umbral después de la decisión 5.** La regla eligió psm 3 sobre el set de validación. Con psm 3, el corpus de prueba da 4,04 % contra el 2 % del umbral, y todo el exceso viene del orden de lectura de una tabla (doc. 13, 23,81 %). El test de integración queda en rojo y la tarea 4.1 sin marcar.
   - A. Cerrar la change con el escenario en rojo y documentado como limitación conocida. A favor: honesto y sin sobreajuste. En contra: la definición de terminado exige `make verify` en verde con evaluación; hoy pasa solo porque los tests `integration` no corren en CI.
   - B. Marcar el test como `xfail(strict=True)` con la razón y un enlace a esta pregunta. A favor: la suite de integración queda en verde y avisa si un día el umbral se cumple. En contra: hay que modificar un test, algo que CLAUDE.md permite solo si el test está mal, y este no lo está.
   - C. Abrir una change posterior de OCR consciente del diseño de la página: elegir el psm por página según la confianza de `image_to_data`, o reconstruir el orden de lectura a partir de las cajas de cada línea. Se mediría con el mismo esquema de validación y prueba. A favor: ataca la causa. En contra: más alcance, y las tablas son non-goal de esta change.
   - **Recomendación**: A en esta change, más C como change posterior. B solo si el autor quiere la suite de integración en verde mientras tanto.
