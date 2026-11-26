"""Pipeline de ingesta: de un directorio de PDFs e imágenes a un JSONL por documento.

Por cada archivo: se calcula el `doc_id` (sha256 del archivo), se omite si ya hay salida con
ese `doc_id` y la misma versión del pipeline, y si no se extrae página por página (capa de
texto si sirve, OCR si no). Un error en un archivo se registra en el reporte y el lote sigue.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import numbers
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from ingest.detection import extractable_count, is_native_text, printable_ratio
from ingest.models import (
    Category,
    DocumentReport,
    DocumentStatus,
    ErrorCode,
    GroundTruthDocument,
    IngestedDocument,
    IngestReport,
    Page,
    PageReport,
    SourceFormat,
)
from ingest.normalize import normalize_text
from ingest.ocr import OCREngine, OCRError
from ingest.pdf import (
    PdfReadError,
    open_pdf,
    page_count,
    page_size_points,
    page_text,
    render_page_gray,
)
from ingest.quality import cer
from ingest.report import build_report
from ingest.settings import IngestSettings

PIPELINE_VERSION = "2"
"""Subirla cuando cambia la salida (extracción, normalización, OCR): invalida el salteo.

Historia: 1 -> 2 agrega `ocr_engine` y `config_hash` a la salida.
"""

DOCUMENTS_SUBDIR = "documents"
GROUND_TRUTH_SUBDIR = "ground_truth"

SUPPORTED_SUFFIXES: dict[str, SourceFormat] = {
    ".pdf": "pdf",
    ".png": "png",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".tif": "tiff",
    ".tiff": "tiff",
}

MIN_TRUSTED_DPI = 100.0
MAX_TRUSTED_DPI = 600.0
"""Fuera de este rango, el dpi que declara una imagen no se cree (72 es el valor por defecto
de muchas aplicaciones, no la resolución real del escaneo) y se asume `ocr_dpi`."""

MAX_OCR_PIXELS = 40_000_000
"""Tope de píxeles por página que llega al OCR. A4 a 300 dpi son 8,7 Mpx; un plano A0 a
300 dpi serían 139 Mpx. Si se supera, se baja la resolución y se informa el dpi efectivo."""

logger = logging.getLogger(__name__)


# Lo que pymupdf y Pillow lanzan ante archivos corruptos, enormes o inesperados.
# DecompressionBombError no hereda de OSError: hay que nombrarla.
_UNREADABLE_ERRORS = (
    PdfReadError,
    Image.DecompressionBombError,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
)


class _DocumentError(Exception):
    def __init__(self, code: ErrorCode, detail: str) -> None:
        super().__init__(detail)
        self.code: ErrorCode = code
        self.detail = detail


# --- Lectura y escritura de la salida -------------------------------------------------------


def load_document(path: Path) -> IngestedDocument:
    """Lee un JSONL de salida (una línea, un documento)."""
    return IngestedDocument.model_validate_json(path.read_text(encoding="utf-8").strip())


def _write_document(path: Path, doc: IngestedDocument) -> None:
    # Escritura atómica: si el proceso se corta, no queda un JSONL a medias que la próxima
    # corrida confunda con una salida válida.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(doc.model_dump_json() + "\n", encoding="utf-8")
    os.replace(tmp, path)


def config_hash(settings: IngestSettings, *, pipeline_version: str, ocr_engine: str) -> str:
    """Huella de todo lo que cambia la salida: versión, detección, rasterizado y OCR.

    `ocr_timeout_s` no entra: un timeout distinto no cambia el texto que sale.
    """
    effective = {
        "pipeline_version": pipeline_version,
        "ocr_engine": ocr_engine,
        "min_native_chars": settings.min_native_chars,
        "min_printable_ratio": settings.min_printable_ratio,
        "ocr_dpi": settings.ocr_dpi,
        "ocr_lang": settings.ocr_lang,
        "ocr_psm": settings.ocr_psm,
    }
    canonical = json.dumps(effective, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _existing_output(path: Path, expected_config_hash: str) -> IngestedDocument | None:
    if not path.is_file():
        return None
    try:
        doc = load_document(path)
    except (ValidationError, ValueError, OSError):
        return None  # salida ilegible o de un esquema anterior: se reprocesa y se sobrescribe
    return doc if doc.config_hash == expected_config_hash else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --- Extracción ---------------------------------------------------------------------------


def _ocr_page(
    page_number: int, image: Image.Image, native_text: str, *, ocr: OCREngine, dpi: int
) -> Page:
    try:
        recognized = ocr.recognize(image, dpi=dpi)
    except OCRError as exc:
        raise _DocumentError("ocr_failed", f"página {page_number}: {exc}") from exc
    return Page(
        page_number=page_number,
        method="ocr",
        text=normalize_text(recognized),
        native_char_count=extractable_count(native_text),
        printable_ratio=printable_ratio(native_text),
    )


def _pdf_pages(path: Path, *, ocr: OCREngine, settings: IngestSettings) -> list[Page]:
    pages: list[Page] = []
    try:
        with open_pdf(path) as doc:
            for index in range(page_count(doc)):
                number = index + 1
                native = page_text(doc, index)
                if is_native_text(
                    native,
                    min_chars=settings.min_native_chars,
                    min_printable_ratio=settings.min_printable_ratio,
                ):
                    pages.append(
                        Page(
                            page_number=number,
                            method="native",
                            text=normalize_text(native),
                            native_char_count=extractable_count(native),
                            printable_ratio=printable_ratio(native),
                        )
                    )
                else:
                    # Se rasteriza la página completa: si tiene un sello con capa de texto,
                    # el OCR lo lee junto con la imagen.
                    dpi = _capped_pdf_dpi(*page_size_points(doc, index), settings.ocr_dpi)
                    image = render_page_gray(doc, index, dpi)
                    pages.append(_ocr_page(number, image, native, ocr=ocr, dpi=dpi))
    except PdfReadError as exc:
        raise _DocumentError("unreadable_file", str(exc)) from exc
    return pages


def _capped_pdf_dpi(width_pt: float, height_pt: float, wanted_dpi: int) -> int:
    """El mayor dpi <= `wanted_dpi` con el que la página no supera `MAX_OCR_PIXELS`."""
    dpi = wanted_dpi
    # +1 por lado: pymupdf redondea el rectángulo de la página hacia afuera.
    while dpi > 1 and (width_pt / 72 * dpi + 1) * (height_pt / 72 * dpi + 1) > MAX_OCR_PIXELS:
        dpi -= 1
    return dpi


def _image_dpi(image: Image.Image) -> float | None:
    """dpi declarado por la imagen, si es plausible. Los TIFF lo dan como `IFDRational`."""
    value = image.info.get("dpi")
    if not isinstance(value, tuple) or not value or not isinstance(value[0], numbers.Real):
        return None
    dpi = float(value[0])
    # Se compara redondeado: PNG guarda píxeles por metro y 100 dpi vuelve como 99,9998.
    return dpi if MIN_TRUSTED_DPI <= round(dpi) <= MAX_TRUSTED_DPI else None


def _frames(image: Image.Image) -> Iterator[Image.Image]:
    for index in range(getattr(image, "n_frames", 1)):
        image.seek(index)
        yield image.convert("L")


def _image_pages(path: Path, *, ocr: OCREngine, settings: IngestSettings) -> list[Page]:
    try:
        with Image.open(path) as image:
            source_dpi = _image_dpi(image)
            frames = list(_frames(image))
    except (UnidentifiedImageError, OSError) as exc:
        raise _DocumentError("unreadable_file", str(exc)) from exc
    pages: list[Page] = []
    # Mismo criterio que con los PDF: el OCR recibe la página a `ocr_dpi`. Si la imagen no
    # declara una resolución plausible, se asume que ya está a `ocr_dpi`.
    base_dpi = source_dpi if source_dpi is not None else float(settings.ocr_dpi)
    for number, frame in enumerate(frames, start=1):
        scale = settings.ocr_dpi / base_dpi
        if frame.width * frame.height * scale**2 > MAX_OCR_PIXELS:
            scale = math.sqrt(MAX_OCR_PIXELS / (frame.width * frame.height))
        size = (max(1, math.floor(frame.width * scale)), max(1, math.floor(frame.height * scale)))
        if size != frame.size:
            frame = frame.resize(size, resample=Image.Resampling.BICUBIC)
        effective_dpi = round(base_dpi * scale)
        pages.append(_ocr_page(number, frame, "", ocr=ocr, dpi=effective_dpi))
    return pages


def extract_pages(
    path: Path, source_format: SourceFormat, *, ocr: OCREngine, settings: IngestSettings
) -> list[Page]:
    if source_format == "pdf":
        return _pdf_pages(path, ocr=ocr, settings=settings)
    return _image_pages(path, ocr=ocr, settings=settings)


# --- Calidad ------------------------------------------------------------------------------


def load_ground_truth(gt_dir: Path | None, source: str) -> GroundTruthDocument | None:
    if gt_dir is None:
        return None
    path = gt_dir / f"{source}.json"
    if not path.is_file():
        return None
    return GroundTruthDocument.model_validate_json(path.read_text(encoding="utf-8"))


def _page_reports(doc: IngestedDocument, truth: GroundTruthDocument | None) -> list[PageReport]:
    references = {page.page_number: page.text for page in truth.pages} if truth else {}
    reports: list[PageReport] = []
    for page in doc.pages:
        reference = references.get(page.page_number, "")
        page_cer = cer(reference, page.text) if reference.strip() else None
        reports.append(PageReport(page_number=page.page_number, method=page.method, cer=page_cer))
    return reports


def _document_cer(doc: IngestedDocument, truth: GroundTruthDocument | None) -> float | None:
    if truth is None:
        return None
    reference = "\n".join(page.text for page in truth.pages)
    if not reference.strip():
        return None
    return cer(reference, "\n".join(page.text for page in doc.pages))


# --- Lote ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Outcome:
    report: DocumentReport
    pages_processed: int


def _input_files(in_dir: Path) -> list[Path]:
    return sorted(p for p in in_dir.iterdir() if p.is_file() and not p.name.startswith("."))


def _ingest_file(
    path: Path,
    *,
    docs_dir: Path,
    ocr: OCREngine,
    settings: IngestSettings,
    gt_dir: Path | None,
    pipeline_version: str,
    ocr_engine: str,
    run_config_hash: str,
) -> _Outcome:
    start = perf_counter()
    source = path.name
    category: Category | None = None

    def failed(code: ErrorCode, detail: str, doc_id: str | None = None) -> _Outcome:
        report = DocumentReport(
            source=source,
            status="error",
            doc_id=doc_id,
            category=category,
            seconds=perf_counter() - start,
            error=code,
            error_detail=detail,
        )
        return _Outcome(report=report, pages_processed=0)

    try:
        truth = load_ground_truth(gt_dir, source)
    except (ValidationError, ValueError, OSError) as exc:
        return failed("invalid_ground_truth", f"texto de referencia ilegible: {exc}")
    category = truth.category if truth else None

    source_format = SUPPORTED_SUFFIXES.get(path.suffix.lower())
    if source_format is None:
        return failed("unsupported_format", f"extensión no soportada: {path.suffix or '(sin)'}")

    doc_id = sha256_file(path)
    out_path = docs_dir / f"{doc_id}.jsonl"
    status: DocumentStatus
    doc = _existing_output(out_path, run_config_hash)
    if doc is not None:
        status, pages_processed = "skipped", 0
    else:
        try:
            pages = extract_pages(path, source_format, ocr=ocr, settings=settings)
        except _DocumentError as exc:
            return failed(exc.code, exc.detail, doc_id)
        except _UNREADABLE_ERRORS as exc:
            # Fallos de las librerías con un archivo raro: quedan acotados a este documento.
            # Un error de programación (AttributeError, KeyError...) no se atrapa y se ve.
            return failed("unreadable_file", f"{type(exc).__name__}: {exc}", doc_id)
        doc = IngestedDocument(
            doc_id=doc_id,
            source=source,
            source_format=source_format,
            pipeline_version=pipeline_version,
            ocr_engine=ocr_engine,
            config_hash=run_config_hash,
            page_count=len(pages),
            pages=pages,
        )
        _write_document(out_path, doc)
        status, pages_processed = "processed", len(pages)

    report = DocumentReport(
        source=source,
        status=status,
        doc_id=doc_id,
        category=category,
        page_count=doc.page_count,
        pages=_page_reports(doc, truth),
        cer=_document_cer(doc, truth),
        seconds=perf_counter() - start,
    )
    return _Outcome(report=report, pages_processed=pages_processed)


def ingest_directory(
    in_dir: Path,
    out_dir: Path,
    *,
    ocr: OCREngine,
    settings: IngestSettings | None = None,
    ground_truth_dir: Path | None = None,
    pipeline_version: str = PIPELINE_VERSION,
) -> IngestReport:
    """Ingesta los archivos de primer nivel de `in_dir` y escribe `out_dir/documents/*.jsonl`.

    Un documento se omite si ya hay salida con su `doc_id` y la misma huella de configuración.

    Si no se indica `ground_truth_dir`, se usa `in_dir/ground_truth` cuando existe.
    """
    if not in_dir.is_dir():
        raise NotADirectoryError(str(in_dir))
    settings = settings or IngestSettings()
    if ground_truth_dir is None and (in_dir / GROUND_TRUTH_SUBDIR).is_dir():
        ground_truth_dir = in_dir / GROUND_TRUTH_SUBDIR
    docs_dir = out_dir / DOCUMENTS_SUBDIR
    docs_dir.mkdir(parents=True, exist_ok=True)

    ocr_engine = ocr.name
    run_config_hash = config_hash(
        settings, pipeline_version=pipeline_version, ocr_engine=ocr_engine
    )
    start = perf_counter()
    outcomes: list[_Outcome] = []
    for path in _input_files(in_dir):
        outcome = _ingest_file(
            path,
            docs_dir=docs_dir,
            ocr=ocr,
            settings=settings,
            gt_dir=ground_truth_dir,
            pipeline_version=pipeline_version,
            ocr_engine=ocr_engine,
            run_config_hash=run_config_hash,
        )
        entry = outcome.report
        logger.info(
            "documento",
            extra={
                "source": entry.source,
                "status": entry.status,
                "pages": entry.page_count,
                "error": entry.error,
                "seconds": round(entry.seconds, 3),
            },
        )
        outcomes.append(outcome)

    return build_report(
        [outcome.report for outcome in outcomes],
        pipeline_version=pipeline_version,
        ocr_engine=ocr_engine,
        config_hash=run_config_hash,
        total_seconds=perf_counter() - start,
        pages_processed=sum(outcome.pages_processed for outcome in outcomes),
    )
