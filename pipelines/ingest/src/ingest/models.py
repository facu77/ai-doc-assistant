"""Contratos del pipeline (bordes): salida por documento, reporte y texto de referencia.

Todo lo que sale a disco o entra desde disco pasa por estos modelos Pydantic. Adentro del
pipeline se usan tipos simples.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExtractionMethod = Literal["native", "ocr"]
"""`native`: texto de la capa de texto del PDF. `ocr`: texto reconocido sobre la imagen."""

SourceFormat = Literal["pdf", "png", "jpeg", "tiff"]

DocumentStatus = Literal["processed", "skipped", "error"]
"""`skipped`: ya existía una salida con el mismo `doc_id` y la misma versión del pipeline."""

ErrorCode = Literal["unsupported_format", "unreadable_file", "ocr_failed", "invalid_ground_truth"]
"""Con estado `error`, el motivo de la falla. `invalid_ground_truth` es la excepción: es un
aviso (el texto de referencia existe pero no se puede leer) y el documento se ingiere igual,
con CER vacío."""

Category = Literal["native", "clean_scan", "noisy_scan", "mixed"]
"""Categoría del corpus (sale del texto de referencia, no la infiere el pipeline)."""

PageKind = Literal["native", "scan"]
"""Cómo se generó la página en el corpus: con capa de texto o como imagen."""

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- Salida del pipeline ---------------------------------------------------------------


class Page(_Frozen):
    page_number: int = Field(ge=1, description="Número de página, empezando en 1.")
    method: ExtractionMethod
    text: str = Field(description="Texto normalizado (NFC, espacios colapsados por línea).")
    native_char_count: int = Field(
        ge=0, description="Caracteres no blancos en la capa de texto, antes de decidir el método."
    )
    printable_ratio: float = Field(
        ge=0.0, le=1.0, description="Proporción de caracteres imprimibles en la capa de texto."
    )


class IngestedDocument(_Frozen):
    doc_id: str = Field(pattern=SHA256_PATTERN, description="sha256 del archivo de entrada.")
    source: str = Field(description="Nombre del archivo, relativo al directorio de entrada.")
    source_format: SourceFormat
    pipeline_version: str
    ocr_engine: str = Field(description="Motor de OCR configurado en la corrida que lo produjo.")
    config_hash: str = Field(
        pattern=SHA256_PATTERN,
        description="sha256 de la configuración efectiva: clave de idempotencia junto al doc_id.",
    )
    page_count: int = Field(ge=0)
    pages: list[Page]


# --- Reporte ---------------------------------------------------------------------------


class PageReport(_Frozen):
    page_number: int = Field(ge=1)
    method: ExtractionMethod
    cer: float | None = Field(default=None, ge=0.0, description="CER de la página, si hay ref.")


class DocumentReport(_Frozen):
    source: str
    status: DocumentStatus
    doc_id: str | None = None
    category: Category | None = None
    page_count: int = Field(default=0, ge=0)
    pages: list[PageReport] = Field(default_factory=list)
    cer: float | None = Field(default=None, ge=0.0, description="CER del documento completo.")
    seconds: float = Field(default=0.0, ge=0.0, description="Tiempo de proceso en esta corrida.")
    error: ErrorCode | None = None
    error_detail: str | None = None


class CategoryCER(_Frozen):
    documents: int = Field(ge=0)
    mean_cer: float = Field(ge=0.0, description="Promedio simple del CER por documento.")
    max_cer: float = Field(ge=0.0)


class IngestReport(_Frozen):
    pipeline_version: str
    ocr_engine: str
    config_hash: str = Field(pattern=SHA256_PATTERN)
    documents_total: int = Field(ge=0)
    processed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(ge=0)
    warnings: int = Field(
        ge=0, description="Documentos ingeridos con un aviso (por ejemplo, invalid_ground_truth)."
    )
    pages_total: int = Field(ge=0)
    pages_by_method: dict[ExtractionMethod, int]
    cer_by_category: dict[Category, CategoryCER]
    mean_cer: float | None = Field(
        default=None, description="Promedio del CER de todos los documentos con referencia."
    )
    total_seconds: float = Field(ge=0.0)
    pages_processed: int = Field(ge=0, description="Páginas procesadas en esta corrida.")
    seconds_per_page: float | None = Field(
        default=None, description="Tiempo medio por página procesada en esta corrida."
    )
    documents: list[DocumentReport]


# --- Texto de referencia del corpus ----------------------------------------------------


class GroundTruthPage(_Frozen):
    page_number: int = Field(ge=1)
    kind: PageKind
    text: str


class GroundTruthDocument(_Frozen):
    source: str
    category: Category
    title: str
    pages: list[GroundTruthPage]


class CorpusEntry(_Frozen):
    source: str
    category: Category
    page_count: int = Field(ge=1)
    sha256: str = Field(pattern=SHA256_PATTERN)


class ScanProfile(_Frozen):
    """Degradación aplicada a un escaneo simulado (fijada antes de medir el CER)."""

    max_rotation_deg: float = Field(ge=0.0)
    min_rotation_deg: float = Field(ge=0.0)
    noise_sigma: float = Field(ge=0.0, description="Desvío del ruido gaussiano (escala 0-255).")
    render_dpi: int = Field(gt=0, description="dpi del rasterizado inicial.")
    output_dpi: int = Field(gt=0, description="dpi final del escaneo, después de bajar resolución.")
    jpeg_quality: int = Field(ge=1, le=95)


class CorpusManifest(_Frozen):
    seed: int
    generator_version: str
    scan_profiles: dict[Literal["clean_scan", "noisy_scan"], ScanProfile]
    documents: list[CorpusEntry]
