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

## Preguntas abiertas

Ninguna por ahora.
