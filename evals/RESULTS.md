# Resultados de evaluación

Cada fila sale de una corrida registrada: tiene el archivo en `evals/runs/` y el run de MLflow. Se prueba una sola variable por fila.

| Fecha | Commit | Variante | recall@5 | MRR | Fidelidad | Relevancia | p95 (ms) | Run MLflow | Notas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | — | línea base (pendiente: add-rag-core) | | | | | | | |

## Ingesta y OCR (`add-ingest-pipeline`)

CER medio por categoría sobre el corpus ficticio de 20 documentos (`data/corpus`). La corrida completa está en `pipelines/ingest/REPORT.md` y se reproduce con `uv run ingest ../../data/corpus --out <dir>` desde `pipelines/ingest`.

| Fecha | Commit | Variante | Nativo | Escaneo limpio (umbral 2 %) | Escaneo ruidoso (umbral 8 %) | Mixto | s/página | Notas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-24 | da01914 | Tesseract 5.3.4, psm 3 (por defecto) | 0,00 % | **4,04 %** (no cumple) | 0,04 % | 0,00 % | 0,85 | Error de orden de lectura en una tabla (doc. 13) |
| 2026-11-24 | da01914 | psm 4 (experimento) | 0,00 % | 0,07 % | 0,04 % | 0,00 % | 0,82 | Elegido mirando el corpus: no adoptado (Preguntas abiertas) |
| 2026-11-24 | da01914 | psm 6 (experimento) | 0,00 % | 0,07 % | 0,04 % | 0,00 % | 0,78 | Igual que psm 4 |
