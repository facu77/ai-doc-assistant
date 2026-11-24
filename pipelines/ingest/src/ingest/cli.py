"""CLI: `uv run ingest <in_dir> --out <out_dir>`.

Códigos de salida: 0 si todos los documentos se procesaron u omitieron, 1 si alguno terminó
con error (el resto del lote se procesa igual) y 2 si los argumentos son inválidos.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ingest.logs import configure_json_logging
from ingest.ocr import OCREngine
from ingest.pipeline import ingest_directory
from ingest.report import write_report
from ingest.settings import IngestSettings
from ingest.tesseract import TesseractEngine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingest", description="Ingesta PDFs e imágenes a JSONL, con OCR selectivo."
    )
    parser.add_argument("in_dir", type=Path, help="Directorio con los documentos de entrada.")
    parser.add_argument("--out", type=Path, required=True, help="Directorio de salida.")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help="Texto de referencia para el CER (por defecto, <in_dir>/ground_truth si existe).",
    )
    parser.add_argument("--min-native-chars", type=int, default=None)
    parser.add_argument("--min-printable-ratio", type=float, default=None)
    parser.add_argument("--dpi", dest="ocr_dpi", type=int, default=None)
    parser.add_argument("--lang", dest="ocr_lang", default=None)
    parser.add_argument("--psm", dest="ocr_psm", type=int, default=None)
    return parser


def run(argv: Sequence[str] | None = None, *, ocr: OCREngine | None = None) -> int:
    args = _parser().parse_args(argv)
    in_dir: Path = args.in_dir
    out_dir: Path = args.out
    if not in_dir.is_dir():
        print(f"ingest: {in_dir} no es un directorio", file=sys.stderr)
        return 2

    overrides = {
        key: getattr(args, key)
        for key in ("min_native_chars", "min_printable_ratio", "ocr_dpi", "ocr_lang", "ocr_psm")
        if getattr(args, key) is not None
    }
    settings = IngestSettings(**overrides)
    if ocr is None:
        ocr = TesseractEngine(settings)

    report = ingest_directory(
        in_dir, out_dir, ocr=ocr, settings=settings, ground_truth_dir=args.ground_truth
    )
    json_path, md_path = write_report(report, out_dir)
    print(
        f"{report.documents_total} documentos: {report.processed} procesados, "
        f"{report.skipped} omitidos, {report.errors} con error. Reporte: {json_path}, {md_path}"
    )
    return 1 if report.errors else 0


def main() -> int:
    configure_json_logging()
    return run()
