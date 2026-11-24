# Reporte de ingesta del corpus

Corrida registrada de `add-ingest-pipeline` sobre el corpus ficticio versionado (`data/corpus`).

- **Código**: commit `da01914` (pipeline versión 1).
- **Corpus**: semilla 20261124, generador versión 1 (`uv run make-corpus --out ../../data/corpus`).
- **Entorno**: contenedor Linux x86_64 con 4 vCPU, Python 3.12.3, Tesseract 5.3.4 (`spa+eng`).
- **Comando**: `uv run ingest ../../data/corpus --out <dir>` (desde `pipelines/ingest`, configuración por defecto: 50 caracteres, ratio 0,9, 300 dpi, psm 3).
- **Fecha**: 2026-11-24.

Lo que sigue es el `ingest_report.md` que escribió esa corrida, sin editar (solo se bajó un nivel cada título).

## Corrida con la configuración por defecto (psm 3)

### Resumen

| Campo | Valor |
| --- | --- |
| Versión del pipeline | 1 |
| Motor de OCR | tesseract 5.3.4 (spa+eng, psm 3) |
| Documentos | 20 |
| Procesados | 20 |
| Omitidos (sin cambios) | 0 |
| Con error | 0 |
| Páginas | 35 |
| CER medio (documentos con referencia) | 1.22 % |
| Tiempo total | 29.65 s |
| Páginas procesadas en esta corrida | 35 |
| Tiempo por página procesada | 0.847 s |

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
| 09-formulario-solicitud-vacaciones.pdf | Escaneo limpio | processed | 1 | O | 0.22 % | 1.97 s |
| 10-memo-aguinaldo.pdf | Escaneo limpio | processed | 1 | O | 0.19 % | 2.23 s |
| 11-circular-horario-verano.pdf | Escaneo limpio | processed | 1 | O | 0.00 % | 2.10 s |
| 12-reglamento-comedor.pdf | Escaneo limpio | processed | 2 | O O | 0.00 % | 3.66 s |
| 13-formulario-rendicion-gastos.jpg | Escaneo limpio | processed | 1 | O | 23.81 % | 2.08 s |
| 14-procedimiento-licencia-medica.pdf | Escaneo limpio | processed | 2 | O O | 0.00 % | 4.30 s |
| 15-acta-comite-seguridad-higiene.pdf | Escaneo ruidoso | processed | 1 | O | 0.00 % | 2.10 s |
| 16-formulario-alta-beneficiario.pdf | Escaneo ruidoso | processed | 1 | O | 0.00 % | 1.95 s |
| 17-aviso-cambio-turnos.jpg | Escaneo ruidoso | processed | 1 | O | 0.00 % | 1.65 s |
| 18-politica-prestamos-personales.pdf | Escaneo ruidoso | processed | 2 | O O | 0.18 % | 3.65 s |
| 19-manual-evaluacion-desempeno.pdf | Mixto | processed | 3 | N O N | 0.00 % | 1.99 s |
| 20-constancia-capacitacion.pdf | Mixto | processed | 2 | N O | 0.00 % | 1.92 s |

### Errores

Sin errores.

## Reingesta (idempotencia)

Mismo comando, mismo directorio de salida, sin cambios en el corpus: 20 documentos omitidos, 0 procesados, 0 páginas procesadas, 0.03 s en total. Los `doc_id` y los JSONL no cambian.

## Umbrales de la spec

| Categoría | CER medio | Umbral (fijado antes de medir) | Resultado |
| --- | --- | --- | --- |
| Escaneo limpio | 4.04 % | 2 % | **No cumple** |
| Escaneo ruidoso | 0.04 % | 8 % | Cumple |

El test `test_cer_medio_de_escaneos_limpios_es_a_lo_sumo_2_por_ciento` (`uv run pytest -m integration`) queda en rojo a propósito: el umbral no se mueve.

## Hallazgo: el error de los escaneos limpios es de orden de lectura, no de reconocimiento

El 4,04 % sale casi entero de un documento: `13-formulario-rendicion-gastos.jpg` (CER 23,81 %). Los otros 5 escaneos limpios suman 2 sustituciones en total. En el documento 13, Tesseract reconoce bien todos los caracteres, pero el modo de segmentación automática (psm 3) separa la tabla de dos columnas en dos bloques: lee la columna "Concepto" completa, sigue con el texto de abajo y deja la columna "Importe" al final. El CER cuenta ese texto desplazado como borrados más inserciones.

Los errores de reconocimiento que sí aparecen en todo el corpus son una sola confusión, repetida en 3 documentos (dos limpios y uno ruidoso): "Antigüedad" leída como "Antigúedad". En `09-formulario-solicitud-vacaciones.pdf` es 1 sustitución sobre 462 caracteres, o sea CER 0,22 %.

Binarizar o enderezar la imagen no cambiaría nada, porque los caracteres ya se reconocen bien. Lo que cambia el resultado es el modo de segmentación de página de Tesseract. Experimento (una variable por vez, mismo commit y mismo corpus, `--psm N`):

| Configuración | CER medio limpio | CER medio ruidoso | CER del doc. 13 | Tiempo total |
| --- | --- | --- | --- | --- |
| psm 3 (por defecto) | 4.04 % | 0.04 % | 23.81 % | 29.6 s |
| psm 4 | 0.07 % | 0.04 % | 0.00 % | 28.7 s |
| psm 6 | 0.07 % | 0.04 % | 0.00 % | 27.4 s |

psm 4 ("una columna de texto de tamaños variables") y psm 6 ("un bloque uniforme de texto") leen la tabla fila por fila. **No se adoptaron como valor por defecto**: se eligieron mirando este mismo corpus, que tiene una sola columna en todas las páginas. Además, según la documentación de Tesseract, los dos modos suponen una sola columna, así que en un documento a dos columnas mezclarían las líneas de ambas (eso no se midió). La decisión queda abierta en `openspec/changes/add-ingest-pipeline/proposal.md` (Preguntas abiertas).

## Hallazgo: el perfil ruidoso resultó fácil para Tesseract

El perfil ruidoso (rotación de 1 a 2°, ruido gaussiano sigma 35, JPEG calidad 60, 300 a 200 dpi) da un CER medio de 0,04 %, casi igual al limpio. El ruido gaussiano por píxel se promedia al bajar la resolución y el texto mantiene mucho contraste, así que el escenario pasa sin discriminar. Los parámetros se fijaron antes de medir y no se tocaron. Los escaneos reales (desenfoque, bajo contraste, manchas, papel con textura, 150 dpi o menos) son más difíciles: es una limitación del corpus sintético.
