# Tasks

## 1. Preparación

- [x] 1.1 Inicializar `pipelines/ingest` con `uv` (ruff, mypy estricto, pytest), igual que `services/ai`
- [x] 1.2 Usar `docs-checker` para confirmar las APIs de `pymupdf`, `pytesseract` y `jiwer` en las versiones instaladas
- [x] 1.3 Definir los modelos `IngestedDocument`, `Page` e `IngestReport`, y el Protocol `OCREngine`
- [x] 1.4 Escribir el script del corpus ficticio con semilla (20 documentos y su texto de referencia)

## 2. Tests primero

- [x] 2.1 Usar `test-writer` para escribir los tests de los escenarios, con un `OCREngine` falso para la CI rápida
- [x] 2.2 Escribir los tests `integration` con Tesseract real para los umbrales de CER

## 3. Implementación

- [x] 3.1 Extracción nativa y detección por página
- [x] 3.2 Adaptador de Tesseract
- [x] 3.3 Normalización, `doc_id` e idempotencia
- [x] 3.4 Reporte en JSON y Markdown, y CLI `ingest`

## 4. Cierre

- [ ] 4.1 Correr `/verify` en verde y la corrida completa con el reporte commiteado en `pipelines/ingest/REPORT.md` (verify en verde y reporte commiteado, pero el escenario de escaneo limpio sigue en rojo: 4,04 % contra 2 %. Queda sin marcar hasta que pase o el autor registre una decisión; ver la pregunta abierta 8)
- [ ] 4.2 Pasar `reviewer` y documentar en el README el CER medido y las limitaciones del corpus sintético (README hecho; falta el `reviewer`)

## 5. Ronda 2 (decisiones del autor y revisión, 2026-11-26)

- [x] 5.1 Preregistrar en `design.md` la regla de selección del psm, antes de medir
- [x] 5.2 Generar el set de validación `data/corpus-validation/` (6 escaneos, otra semilla, dos columnas y tablas)
- [x] 5.3 Aplicar la regla sobre la validación: psm 3 (0,13 % contra 11,17 % y 18,40 %)
- [x] 5.4 Correr una sola vez el corpus de prueba con el psm elegido y versionar todas las corridas en `evals/runs/ingest/`
- [x] 5.5 Agregar la huella de configuración y el motor de OCR a la clave de idempotencia (escenario nuevo en la spec)
- [x] 5.6 Corregir los hallazgos 3, 4, 5, 8, 9, 10, 11, 12, 13 y 15 de la revisión
