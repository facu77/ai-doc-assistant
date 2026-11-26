"""Regla preregistrada para elegir el modo de segmentación (psm) de Tesseract.

Está escrita en design.md ("Selección del psm") antes de medir. Se aplica sobre los reportes
del set de validación (`data/corpus-validation/`), nunca sobre el corpus de prueba.

Uso: `uv run python scripts/choose_psm.py --psm3 a.json --psm4 b.json --psm6 c.json`
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean

from ingest.models import IngestReport

PSM_CANDIDATES = (3, 4, 6)
DEFAULT_PSM = 3
TIE_THRESHOLD = 0.001
"""0,1 puntos porcentuales, expresado como fracción (el CER se guarda entre 0 y 1)."""


def mean_scanned_page_cer(report: IngestReport) -> float:
    """CER medio (promedio simple) de las páginas que pasaron por OCR y tienen referencia."""
    cers = [
        page.cer
        for doc in report.documents
        for page in doc.pages
        if page.method == "ocr" and page.cer is not None
    ]
    if not cers:
        raise ValueError("el reporte no tiene páginas escaneadas con texto de referencia")
    return fmean(cers)


def choose_psm(means: Mapping[int, float]) -> int:
    if set(means) != set(PSM_CANDIDATES):
        raise ValueError(f"se esperaban los candidatos {PSM_CANDIDATES}, llegaron {sorted(means)}")
    best = min(PSM_CANDIDATES, key=lambda psm: (means[psm], psm))
    if means[DEFAULT_PSM] - means[best] < TIE_THRESHOLD:
        return DEFAULT_PSM  # empate con psm 3: se queda el valor por defecto
    if abs(means[4] - means[6]) < TIE_THRESHOLD:
        return 4  # 4 y 6 empatan y los dos le ganan a 3
    return best


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aplica la regla preregistrada del psm.")
    for psm in PSM_CANDIDATES:
        parser.add_argument(f"--psm{psm}", type=Path, required=True, help="ingest_report.json")
    args = parser.parse_args(argv)
    means: dict[int, float] = {}
    for psm in PSM_CANDIDATES:
        path: Path = getattr(args, f"psm{psm}")
        report = IngestReport.model_validate_json(path.read_text(encoding="utf-8"))
        means[psm] = mean_scanned_page_cer(report)
        print(f"psm {psm}: CER medio por página escaneada = {means[psm] * 100:.2f} %")
    print(f"psm elegido: {choose_psm(means)}")
    return 0
