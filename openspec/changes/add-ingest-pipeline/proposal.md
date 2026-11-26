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
