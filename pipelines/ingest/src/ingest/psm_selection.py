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


def _gap(a: float, b: float) -> float:
    """a - b redondeado a 1e-9: 0.011 - 0.010 da 0.000999... en float y tiene que contar
    como 0,1 pp exactos en el borde de la regla."""
    return round(a - b, 9)


def choose_psm(means: Mapping[int, float]) -> int:
    """Regla de design.md: gana el menor CER; empate con psm 3 (< 0,1 pp) -> psm 3; si psm 4
    y psm 6 empatan entre sí y los dos le ganan a psm 3 por 0,1 pp o más -> psm 4."""
    if set(means) != set(PSM_CANDIDATES):
        raise ValueError(f"se esperaban los candidatos {PSM_CANDIDATES}, llegaron {sorted(means)}")
    best = min(PSM_CANDIDATES, key=lambda psm: (means[psm], psm))
    if _gap(means[DEFAULT_PSM], means[best]) < TIE_THRESHOLD:
        return DEFAULT_PSM  # empate con psm 3: se queda el valor por defecto
    both_beat_default = all(_gap(means[DEFAULT_PSM], means[psm]) >= TIE_THRESHOLD for psm in (4, 6))
    if both_beat_default and abs(_gap(means[4], means[6])) < TIE_THRESHOLD:
        return 4
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
