# Resultados de evaluación

Cada fila sale de una corrida registrada: tiene el archivo en `evals/runs/` y el run de MLflow. Se prueba una sola variable por fila.

| Fecha | Commit | Variante | recall@5 | MRR | Fidelidad | Relevancia | p95 (ms) | Run MLflow | Notas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | — | línea base (pendiente: add-rag-core) | | | | | | | |

## Ingesta y OCR (`add-ingest-pipeline`)

CER medio por categoría. Cada fila sale del `ingest_report.json` indicado, que está versionado en `evals/runs/ingest/`. El detalle está en `pipelines/ingest/REPORT.md`. Umbrales de la spec: escaneo limpio ≤ 2 % y escaneo ruidoso ≤ 8 %.

El psm se eligió sobre el set de validación con una regla escrita antes de medir (`openspec/changes/add-ingest-pipeline/design.md`). El corpus de prueba se corrió una sola vez con el psm elegido.

| Fecha | Commit | Conjunto y variante | Archivo | Nativo | Escaneo limpio | Escaneo ruidoso | Mixto | CER medio por página escaneada | s/página | Notas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-26 | 37a4454 | Validación, psm 3 | `validation_37a4454_psm3.json` | — | 0,26 % | 0,00 % | — | 0,13 % | 2,30 | Elegido por la regla preregistrada |
| 2026-11-26 | 37a4454 | Validación, psm 4 | `validation_37a4454_psm4.json` | — | 20,52 % | 1,83 % | — | 11,17 % | 2,24 | Mezcla las líneas de las páginas a dos columnas |
| 2026-11-26 | 37a4454 | Validación, psm 6 | `validation_37a4454_psm6.json` | — | 20,47 % | 16,33 % | — | 18,40 % | 2,11 | Mezcla las líneas de las páginas a dos columnas |
| 2026-11-26 | 76145f8 | **Prueba, psm 3 (corrida única)** | `corpus_76145f8_psm3.json` | 0,00 % | **4,04 %** (no cumple) | 0,04 % | 0,00 % | 1,64 % | 0,95 | Tiempo de `corpus_76145f8_psm3_tiempos.json`; la corrida registrada tardó 2,18 s/página por carga de la máquina |
| 2026-11-26 | da01914 | Prueba, psm 3 | `corpus_da01914_psm3.json` | 0,00 % | 4,04 % | 0,04 % | 0,00 % | 1,64 % | 0,97 | Ronda 1, reproducida |
| 2026-11-26 | da01914 | Prueba, psm 4 | `corpus_da01914_psm4.json` | 0,00 % | 0,07 % | 0,04 % | 0,00 % | 0,05 % | 0,95 | Experimento de la ronda 1, reproducido; se eligió mirando el set de prueba, no se adoptó |
| 2026-11-26 | da01914 | Prueba, psm 6 | `corpus_da01914_psm6.json` | 0,00 % | 0,07 % | 0,04 % | 0,00 % | 0,05 % | 0,88 | Experimento de la ronda 1, reproducido; se eligió mirando el set de prueba, no se adoptó |

El escaneo limpio no cumple el umbral en el corpus de prueba. El test del escenario está marcado `xfail(strict=True)` (decisión 8 de `add-ingest-pipeline`) y se resuelve en la change `improve-ocr-quality`.
