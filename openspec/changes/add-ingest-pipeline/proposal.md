# Proposal

## Why

El RAG solo puede ser tan bueno como el texto que recibe. El POC tiene que demostrar una ingesta real de PDFs nativos y escaneados con OCR medido (CER), no texto copiado a mano. Además, es un requisito excluyente del perfil buscado.

## What Changes

- Un pipeline de ingesta en `pipelines/ingest` (proyecto `uv` propio) que toma PDFs e imágenes y produce documentos normalizados en JSONL: texto por página, metadatos, estructura (títulos y tablas, cuando se detectan) y método de extracción.
- Detección por página entre texto nativo y escaneo, con OCR solo donde hace falta.
- Un corpus de 20 documentos **ficticios** generados con un script: una mezcla de nativos, escaneos simulados (texto renderizado a imagen con ruido) y mixtos. Así el texto de referencia es conocido y el CER es medible.
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

## Preguntas abiertas

1. ¿Qué motor de OCR usamos: Tesseract (local, sin costo) o uno en la nube como baseline comparativo? ¿O ambos?
2. ¿El umbral de CER aceptable para escaneos limpios es 2% y para escaneos ruidosos 8%? Hay que confirmarlo antes de testear.
3. ¿Qué dominio tiene el corpus ficticio? Por ejemplo, manuales internos, contratos o normativa. Esto condiciona el set de oro.
4. ¿La detección de tablas entra en esta change o se pospone?
