# Tasks

## 1. Preparación

- [ ] 1.1 Inicializar `pipelines/ingest` con `uv` (ruff, mypy estricto, pytest), igual que `services/ai`
- [ ] 1.2 Usar `docs-checker` para confirmar las APIs de `pymupdf`, `pytesseract` y `jiwer` en las versiones instaladas
- [ ] 1.3 Definir los modelos `IngestedDocument`, `Page` e `IngestReport`, y el Protocol `OCREngine`
- [ ] 1.4 Escribir el script del corpus ficticio con semilla (20 documentos y su texto de referencia)

## 2. Tests primero

- [ ] 2.1 Usar `test-writer` para escribir los tests de los escenarios, con un `OCREngine` falso para la CI rápida
- [ ] 2.2 Escribir los tests `integration` con Tesseract real para los umbrales de CER

## 3. Implementación

- [ ] 3.1 Extracción nativa y detección por página
- [ ] 3.2 Adaptador de Tesseract
- [ ] 3.3 Normalización, `doc_id` e idempotencia
- [ ] 3.4 Reporte en JSON y Markdown, y CLI `ingest`

## 4. Cierre

- [ ] 4.1 Correr `/verify` en verde y la corrida completa con el reporte commiteado en `pipelines/ingest/REPORT.md`
- [ ] 4.2 Pasar `reviewer` y documentar en el README el CER medido y las limitaciones del corpus sintético
