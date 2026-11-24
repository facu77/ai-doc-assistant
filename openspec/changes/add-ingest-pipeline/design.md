# Design

## Context

El pipeline corre como CLI (`uv run ingest <dir> --out <dir>`) y también lo va a invocar el endpoint `/ingest` (`add-api-and-gateway`). Su salida la consume `add-vector-index`.

## Goals / Non-Goals

**Goals:**
- Contrato de salida estable: un modelo Pydantic `IngestedDocument` y un JSONL por documento.
- OCR solo en las páginas sin capa de texto útil.
- Calidad medida: CER por documento contra la referencia.

**Non-Goals:**
- Chunking (lo resuelve `add-vector-index` o `add-rag-core`).
- Formatos Office, HTML y correo.
- Estructura de tablas: se extraen como texto plano (limitación documentada).
- OCR en la nube.

## Decisions

- **Detección nativo/escaneo por página**: se considera nativa una página con 50 caracteres extraíbles o más y un ratio de caracteres imprimibles de 0,9 o más. Si no cumple, se le aplica OCR. Los umbrales son configurables.
- **OCR**: Tesseract con `spa+eng` a 300 dpi, detrás de un Protocol `OCREngine` para poder comparar motores.
- **CER**: distancia de Levenshtein a nivel de caracteres (`jiwer.cer`) sobre el texto normalizado (NFC, espacios colapsados).
- **Idempotencia**: el `doc_id` es el `sha256` del archivo. Si ya existe una salida con el mismo hash y la misma versión de pipeline, se omite.
- **Corpus ficticio**: dominio de RRHH y políticas internas de "Acme S.A.", con empleados y datos 100% inventados. `scripts/make_corpus.py` genera PDFs con `reportlab`. Los escaneos se simulan rasterizando, rotando ±2°, agregando ruido gaussiano y bajando a 200 dpi.

## Risks / Trade-offs

- Tesseract en CI necesita `apt-get`, lo que hace más lenta la CI. Para mitigarlo, el OCR real se marca como `integration` y en CI rápida se usa un `OCREngine` falso.
- El corpus sintético es más fácil que el real. Hay que documentarlo como limitación en el README.
