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

### Selección del psm: regla preregistrada (2026-11-26)

Se escribe y se commitea antes de generar el set de validación y antes de medir. No se cambia después de ver resultados.

- **Candidatos**: psm 3, 4 y 6 de Tesseract. Todo lo demás queda con la configuración por defecto (`spa+eng`, 300 dpi, umbrales de detección 50 y 0,9).
- **Set de validación** (desarrollo): `data/corpus-validation/`. Son 6 documentos escaneados de Acme S.A. (limpios y ruidosos), generados con otra semilla y con contenido distinto del corpus. Incluyen al menos un documento a dos columnas y al menos un formulario con tabla.
- **Set de prueba**: `data/corpus/`. No se usa para elegir. Se corre una sola vez, con el psm elegido.
- **Métrica**: el CER medio por página, como promedio simple, sobre todas las páginas del set de validación que pasan por OCR y tienen texto de referencia.
- **Regla**: se elige el psm con menor CER medio. Si la diferencia entre ese psm y psm 3 es menor que 0,1 puntos porcentuales, se queda psm 3 (empate). Si psm 4 y psm 6 empatan entre sí (menos de 0,1 pp de diferencia) y los dos le ganan a psm 3 por 0,1 pp o más, se elige psm 4.
- **Herramienta**: `pipelines/ingest/scripts/choose_psm.py` aplica la regla sobre los `ingest_report.json` de las tres corridas.
- **Registro**: los reportes de todas las corridas se versionan en `evals/runs/ingest/`.
- **Consecuencia**: si el psm elegido no es 3, se cambia el valor por defecto y se sube `PIPELINE_VERSION`.

## Risks / Trade-offs

- Tesseract en CI necesita `apt-get`, lo que hace más lenta la CI. Para mitigarlo, el OCR real se marca como `integration` y en CI rápida se usa un `OCREngine` falso.
- El corpus sintético es más fácil que el real. Hay que documentarlo como limitación en el README.
