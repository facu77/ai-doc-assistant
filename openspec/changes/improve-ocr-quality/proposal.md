# Proposal

## Why

`add-ingest-pipeline` dejó la calidad del OCR medida, pero con dos deudas declaradas:

1. **El escaneo limpio no cumple el umbral.** El CER medio del corpus de prueba da 4,04 %, contra un umbral de 2 % (`evals/runs/ingest/corpus_76145f8_psm3.json`). Todo el exceso viene de un solo documento, `13-formulario-rendicion-gastos.jpg` (23,81 %): Tesseract con psm 3 reconoce bien los caracteres, pero lee la tabla columna por columna y deja la columna "Importe" al final. El test de integración del escenario quedó como `xfail(strict=True)` y apunta a esta change.
2. **El perfil de escaneo ruidoso no discrimina.** Da un CER de 0,04 %, casi igual que el limpio. El umbral de 8 % todavía no se puso a prueba con un caso difícil (decisión 6 de `add-ingest-pipeline`).

Lo aprendido en `add-ingest-pipeline` marca el camino. **Ningún modo de segmentación único sirve para todos los diseños de página**:

| Corrida | psm 3 | psm 4 | psm 6 |
| --- | --- | --- | --- |
| Validación, CER medio por página escaneada (`validation_37a4454_psm*.json`) | **0,13 %** | 11,17 % | 18,40 % |
| Validación, boletín a dos columnas | 0,13 % | 60,92 % | 60,78 % |
| Validación, tablas (horas extra, guardería) | 0,63 % / 0,00 % | 0,63 % / 0,00 % | 0,63 % / 0,00 % |
| Prueba, escaneo limpio (`corpus_da01914_psm*.json`) | 4,04 % | 0,07 % | 0,07 % |

psm 4 y 6 arreglan la tabla del doc. 13, pero mezclan las líneas de los documentos a dos columnas. psm 3 respeta las columnas, pero en algunos formularios lee la tabla por columnas. La solución tiene que decidir **según la estructura de cada página**, no con un valor global.

## What Changes

- **Estructura de página y tablas.** Llevar el escaneo limpio del corpus de prueba a ≤ 2 % sin empeorar los documentos a dos columnas. Candidatos a evaluar, cada uno con la misma metodología:
  - **Detección de layout o tablas** antes del OCR (por ejemplo, con las cajas de `image_to_data` o con líneas y columnas detectadas en la imagen) para elegir el psm de cada página.
  - **psm por documento o por página según la estructura detectada**: dos columnas, psm 3; formulario o tabla, psm 4.
  - **Elegir entre modos por la confianza de Tesseract**: correr psm 3 y psm 4 y quedarse con el de mayor confianza media. Costo: doble OCR, unos 2 s más por página escaneada.
  - **Reconstruir el orden de lectura** a partir de las cajas de cada línea (`image_to_data`), en vez de confiar en el orden de segmentación.
- **Perfil de escaneo ruidoso más difícil.** Un perfil nuevo, `noisy_scan_v2`, con degradaciones de escaneo real: desenfoque, bajo contraste, manchas o *speckle*, papel con textura y 150 dpi. Su umbral se fija **antes de medir**. Se reporta aparte, sin reemplazar la medición del perfil actual.
- **Metodología** (la de la decisión 5 de `add-ingest-pipeline`):
  - La regla de decisión se escribe y se commitea en `design.md` antes de medir.
  - Se usa un set de validación separado, con documentos nuevos y otra semilla: dos columnas, tablas, formularios y texto corrido. Tiene que incluir **tablas que psm 3 lea por columnas**, como el doc. 13. Las dos tablas de la primera validación no reproducían esa falla (psm 3, 4 y 6 daban el mismo CER), así que esa validación no pudo medir el beneficio de psm 4 en tablas.
  - El corpus de prueba se corre una sola vez con el candidato elegido.
  - Todas las corridas se versionan en `evals/runs/ingest/`.
- **Cierre del escenario.** Si el escaneo limpio queda en ≤ 2 %, se saca la marca `xfail` del test de integración. Con `strict=True`, el test va a fallar como XPASS hasta que se saque la marca.

## Capabilities

### New Capabilities

### Modified Capabilities
- `document-ingestion`: elección del modo de segmentación por página (o reconstrucción del orden de lectura), y una categoría de escaneo ruidoso v2 con su propio umbral.

## Nota sobre las specs

La capability `document-ingestion` todavía no está en `openspec/specs/`: se archiva con `add-ingest-pipeline`, después del merge. Por eso esta change declara `skip_specs: true` en `.openspec.yaml`. Los deltas de spec (requirements y scenarios con `MODIFIED`/`ADDED`) se escriben al **aplicar** la change, sobre la capability ya archivada. En ese momento se saca `skip_specs`.

## Impact

- Código en `pipelines/ingest/`: el adaptador de Tesseract (más salida de `image_to_data` y quizás dos pasadas) y la detección de layout. Un perfil nuevo en el generador del corpus.
- Datos: un set de validación nuevo y documentos con el perfil ruidoso v2. La mantención del corpus de prueba se discute en las preguntas abiertas.
- Rendimiento: elegir el modo por confianza duplica el OCR de las páginas escaneadas. Hay que medirlo y reportarlo junto con el CER.
- Al cambiar la salida, sube `PIPELINE_VERSION` y el `config_hash` fuerza el reprocesamiento.

## Depende de

- `add-ingest-pipeline` integrada y archivada (la capability `document-ingestion` en `openspec/specs/`).

## Preguntas abiertas

1. **¿El corpus de prueba de `add-ingest-pipeline` se reutiliza tal cual?** A favor: hay continuidad y el xfail apunta a él. En contra: ya se miró mucho (el doc. 13 es conocido), así que deja de ser una muestra "a ciegas". Una opción es un segundo corpus de prueba nuevo para esta change, que se reporte junto al original.
2. **Umbral del perfil ruidoso v2**: ¿se mantiene el 8 % o se fija otro antes de medir?
3. **Presupuesto de tiempo**: ¿cuánto tiempo extra por página se acepta para elegir el modo por confianza?
