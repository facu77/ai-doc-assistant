# Reporte de ingesta

Corridas registradas de `add-ingest-pipeline`. Cada número de este archivo sale de un `ingest_report.json` versionado en [`evals/runs/ingest/`](../../evals/runs/ingest/). El nombre de cada archivo indica el conjunto, el commit del código y el psm.

- **Entorno**: contenedor Linux x86_64 con 4 vCPU, Python 3.12.3, Tesseract 5.3.4 (`spa+eng`), 300 dpi, umbrales de detección 50 caracteres y 0,9.
- **Conjuntos**:
  - Validación (desarrollo): `data/corpus-validation/`, 6 escaneos, semilla 20261126.
  - Prueba: `data/corpus/`, 20 documentos, semilla 20261124.
- **Procedimiento** (decisión 5 de la propuesta): la regla de selección del psm se commiteó en `design.md` (commit `7768799`) antes de generar el set de validación. Después se midió la validación, se eligió el psm y recién entonces se corrió una sola vez el corpus de prueba.

## 1. Selección del psm sobre el set de validación

Archivos: `validation_37a4454_psm3.json`, `validation_37a4454_psm4.json` y `validation_37a4454_psm6.json`. Regla: `uv run python scripts/choose_psm.py --psm3 ... --psm4 ... --psm6 ...`.

| Documento | Tipo | Escaneo | psm 3 | psm 4 | psm 6 |
| --- | --- | --- | --- | --- | --- |
| `v01-boletin-interno.pdf` | dos columnas | limpio | 0.13 % | 60.92 % | 60.78 % |
| `v02-planilla-horas-extra.pdf` | tabla | limpio | 0.63 % | 0.63 % | 0.63 % |
| `v03-memo-feriados.pdf` | texto corrido | limpio | 0.00 % | 0.00 % | 0.00 % |
| `v04-solicitud-reintegro-guarderia.jpg` | tabla | ruidoso | 0.00 % | 0.00 % | 0.00 % |
| `v05-guia-rapida-beneficios.pdf` | dos columnas | ruidoso | 0.00 % | 5.50 % | 49.00 % |
| `v06-aviso-mantenimiento-edificio.pdf` | texto corrido | ruidoso | 0.00 % | 0.00 % | 0.00 % |
| **CER medio por página escaneada** | | | **0.13 %** | **11.17 %** | **18.40 %** |

**psm elegido: 3.** psm 4 y 6 suponen una sola columna, así que en los documentos a dos columnas leen cada renglón de izquierda a derecha y mezclan las dos columnas. En el boletín, el CER pasa de 0.13 % a 60.92 %. Las dos tablas del set de validación las lee bien psm 3 (0.63 % y 0.00 %). Como el valor por defecto sigue siendo psm 3, la salida no cambia y `PIPELINE_VERSION` queda en 2.

## 2. Corpus de prueba con el psm elegido (corrida única)

Archivo: `corpus_76145f8_psm3.json`. Lo que sigue es el `ingest_report.md` de esa corrida, renderizado con `ingest.report.render_markdown` sin editar (solo se bajó un nivel cada título).

### Resumen

| Campo | Valor |
| --- | --- |
| Versión del pipeline | 2 |
| Motor de OCR | tesseract 5.3.4 (spa+eng, psm 3) |
| Huella de configuración | `2e4681eb1fd4` |
| Documentos | 20 |
| Procesados | 20 |
| Omitidos (sin cambios) | 0 |
| Con error | 0 |
| Páginas | 35 |
| CER medio (documentos con referencia) | 1.22 % |
| Tiempo total | 76.46 s |
| Páginas procesadas en esta corrida | 35 |
| Tiempo por página procesada | 2.185 s |

### Páginas por método

| Método | Páginas |
| --- | --- |
| `native` | 20 |
| `ocr` | 15 |

### CER por categoría

| Categoría | Documentos | CER medio | CER máximo |
| --- | --- | --- | --- |
| Nativo | 8 | 0.00 % | 0.00 % |
| Escaneo limpio | 6 | 4.04 % | 23.81 % |
| Escaneo ruidoso | 4 | 0.04 % | 0.18 % |
| Mixto | 2 | 0.00 % | 0.00 % |

### Documentos

Método por página: `N` nativa, `O` OCR.

| Documento | Categoría | Estado | Páginas | Método por página | CER | Tiempo |
| --- | --- | --- | --- | --- | --- | --- |
| 01-politica-licencias.pdf | Nativo | processed | 3 | N N N | 0.00 % | 0.01 s |
| 02-politica-viaticos.pdf | Nativo | processed | 2 | N N | 0.00 % | 0.00 s |
| 03-beneficios.pdf | Nativo | processed | 2 | N N | 0.00 % | 0.00 s |
| 04-codigo-de-conducta.pdf | Nativo | processed | 3 | N N N | 0.00 % | 0.00 s |
| 05-home-office.pdf | Nativo | processed | 2 | N N | 0.00 % | 0.00 s |
| 06-onboarding.pdf | Nativo | processed | 2 | N N | 0.00 % | 0.00 s |
| 07-capacitacion.pdf | Nativo | processed | 1 | N | 0.00 % | 0.00 s |
| 08-seguridad-informacion.pdf | Nativo | processed | 2 | N N | 0.00 % | 0.00 s |
| 09-formulario-solicitud-vacaciones.pdf | Escaneo limpio | processed | 1 | O | 0.22 % | 4.65 s |
| 10-memo-aguinaldo.pdf | Escaneo limpio | processed | 1 | O | 0.19 % | 10.18 s |
| 11-circular-horario-verano.pdf | Escaneo limpio | processed | 1 | O | 0.00 % | 4.15 s |
| 12-reglamento-comedor.pdf | Escaneo limpio | processed | 2 | O O | 0.00 % | 13.14 s |
| 13-formulario-rendicion-gastos.jpg | Escaneo limpio | processed | 1 | O | 23.81 % | 2.40 s |
| 14-procedimiento-licencia-medica.pdf | Escaneo limpio | processed | 2 | O O | 0.00 % | 4.67 s |
| 15-acta-comite-seguridad-higiene.pdf | Escaneo ruidoso | processed | 1 | O | 0.00 % | 5.00 s |
| 16-formulario-alta-beneficiario.pdf | Escaneo ruidoso | processed | 1 | O | 0.00 % | 2.12 s |
| 17-aviso-cambio-turnos.jpg | Escaneo ruidoso | processed | 1 | O | 0.00 % | 8.72 s |
| 18-politica-prestamos-personales.pdf | Escaneo ruidoso | processed | 2 | O O | 0.18 % | 10.34 s |
| 19-manual-evaluacion-desempeno.pdf | Mixto | processed | 3 | N O N | 0.00 % | 8.94 s |
| 20-constancia-capacitacion.pdf | Mixto | processed | 2 | N O | 0.00 % | 2.14 s |

### Errores

Sin errores.

## 3. Reingesta y tiempos

- **Reingesta** (`corpus_76145f8_psm3_reingesta.json`): mismo directorio de salida y misma configuración. Resultado: 20 documentos omitidos, 0 procesados, 0.02 s.
- **Tiempos**: la corrida registrada tardó 76.5 s porque la máquina estaba cargada. Una segunda corrida, hecha solo para medir el tiempo, tardó 33.3 s (0.95 s por página) (`corpus_76145f8_psm3_tiempos.json`). El CER es idéntico, porque el pipeline es determinista. Casi todo el tiempo se va en las 15 páginas con OCR.

## 4. Umbrales de la spec

| Categoría | CER medio | Umbral (fijado antes de medir) | Resultado |
| --- | --- | --- | --- |
| Escaneo limpio | 4.04 % | 2 % | **No cumple** |
| Escaneo ruidoso | 0.04 % | 8 % | Cumple |

`uv run pytest -m integration` da 1 test fallado (`test_cer_medio_de_escaneos_limpios_es_a_lo_sumo_2_por_ciento`) y 3 que pasan. El umbral no se movió.

## 5. Hallazgos

- **El error de los escaneos limpios es de orden de lectura.** Casi todo viene de `13-formulario-rendicion-gastos.jpg` (23.81 %). psm 3 lee la columna "Concepto" de la tabla, sigue con el resto de la página y deja la columna "Importe" al final. Los caracteres se reconocen bien. Los otros 5 escaneos limpios suman 2 sustituciones ("Antigüedad" leída como "Antigúedad").
- **psm 4 y 6 lo arreglarían en este corpus, pero no en general.** Con el código anterior (`corpus_da01914_psm4.json` y `corpus_da01914_psm6.json`), el escaneo limpio daba 0.07 % y 0.07 %, contra 4.04 % con psm 3 (`corpus_da01914_psm3.json`). Esas corridas se reprodujeron el 2026-11-26 desde `git archive da01914`. Pero en el set de validación, los dos modos rompen los documentos a dos columnas. Elegirlos mirando el corpus de prueba habría sido sobreajustar a un corpus que no tiene ninguna página a dos columnas.
- **El perfil ruidoso es fácil para Tesseract** (0.04 %). Se mantiene en esta change (decisión 6).

## 6. Corridas registradas

| Archivo | Conjunto | Código | psm | Para qué |
| --- | --- | --- | --- | --- |
| `validation_37a4454_psm3.json` | validación | `37a4454` | 3 | Regla de selección |
| `validation_37a4454_psm4.json` | validación | `37a4454` | 4 | Regla de selección |
| `validation_37a4454_psm6.json` | validación | `37a4454` | 6 | Regla de selección |
| `corpus_76145f8_psm3.json` | prueba | `76145f8` | 3 | Resultado reportado |
| `corpus_76145f8_psm3_reingesta.json` | prueba | `76145f8` | 3 | Idempotencia |
| `corpus_76145f8_psm3_tiempos.json` | prueba | `76145f8` | 3 | Tiempo sin carga de la máquina |
| `corpus_da01914_psm3.json` | prueba | `da01914` | 3 | Ronda 1 (reproducida) |
| `corpus_da01914_psm4.json` | prueba | `da01914` | 4 | Experimento de la ronda 1 (reproducido) |
| `corpus_da01914_psm6.json` | prueba | `da01914` | 6 | Experimento de la ronda 1 (reproducido) |
