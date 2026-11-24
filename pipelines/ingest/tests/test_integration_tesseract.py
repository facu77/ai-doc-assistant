"""Tests con Tesseract real sobre el corpus versionado: `uv run pytest -m integration`.

Requirement: Calidad de OCR medida. Los umbrales salen de la spec y se fijaron antes de medir
(proposal.md, "Decisiones tomadas", punto 2): si no se cumplen, no se mueven.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ingest.models import GroundTruthDocument, IngestReport
from ingest.normalize import normalize_for_cer
from ingest.pdf import open_pdf, render_page_gray
from ingest.pipeline import DOCUMENTS_SUBDIR, ingest_directory, load_document
from ingest.settings import IngestSettings
from ingest.tesseract import TesseractEngine
from tests.conftest import CORPUS_DIR

pytestmark = pytest.mark.integration

CLEAN_SCAN_MAX_CER = 0.02  # spec: "el CER medio es menor o igual a 2%"
NOISY_SCAN_MAX_CER = 0.08  # spec: "el CER medio es menor o igual a 8%"
STAMPED_DOC = "20-constancia-capacitacion.pdf"


@pytest.fixture(scope="module")
def tesseract() -> TesseractEngine:
    if shutil.which("tesseract") is None:
        pytest.fail("falta Tesseract: instalá tesseract-ocr y tesseract-ocr-spa")
    return TesseractEngine(IngestSettings())


@pytest.fixture(scope="module")
def corpus_run(
    tesseract: TesseractEngine, tmp_path_factory: pytest.TempPathFactory
) -> tuple[IngestReport, Path]:
    out_dir = tmp_path_factory.mktemp("tesseract-out")
    return ingest_directory(CORPUS_DIR, out_dir, ocr=tesseract), out_dir


def test_cer_medio_de_escaneos_limpios_es_a_lo_sumo_2_por_ciento(
    corpus_run: tuple[IngestReport, Path],
) -> None:
    """Scenario: Escaneo limpio."""
    report, _ = corpus_run
    stats = report.cer_by_category["clean_scan"]
    assert stats.documents == 6
    assert stats.mean_cer <= CLEAN_SCAN_MAX_CER


def test_cer_medio_de_escaneos_ruidosos_es_a_lo_sumo_8_por_ciento(
    corpus_run: tuple[IngestReport, Path],
) -> None:
    """Scenario: Escaneo ruidoso."""
    report, _ = corpus_run
    stats = report.cer_by_category["noisy_scan"]
    assert stats.documents == 4
    assert stats.mean_cer <= NOISY_SCAN_MAX_CER


def test_pagina_escaneada_con_sello_corto_se_reconoce_por_ocr(
    corpus_run: tuple[IngestReport, Path],
) -> None:
    """Scenario: Página escaneada con poco texto nativo (con Tesseract real).

    La página 2 tiene un sello con capa de texto de menos de 50 caracteres: tiene que pasar
    por OCR y el texto reconocido tiene que incluir el contenido de la imagen, no solo el sello.
    """
    report, out_dir = corpus_run
    [entry] = [d for d in report.documents if d.source == STAMPED_DOC]
    doc = load_document(out_dir / DOCUMENTS_SUBDIR / f"{entry.doc_id}.jsonl")
    page = doc.pages[1]
    assert page.method == "ocr"
    assert 0 < page.native_char_count < 50

    truth = GroundTruthDocument.model_validate_json(
        (CORPUS_DIR / "ground_truth" / f"{STAMPED_DOC}.json").read_text(encoding="utf-8")
    )
    recognized = normalize_for_cer(page.text)
    # Líneas que están solo en la imagen (no en el sello).
    for line in ("Constancia de capacitación", "Duración del curso: 8 horas."):
        assert line in truth.pages[1].text
        assert normalize_for_cer(line) in recognized


def test_png_suelto_se_reconoce_con_tesseract(tesseract: TesseractEngine, tmp_path: Path) -> None:
    """Scenario: Imagen suelta (con Tesseract real)."""
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    with open_pdf(CORPUS_DIR / "07-capacitacion.pdf") as pdf:
        render_page_gray(pdf, 0, 300).save(in_dir / "capacitacion.png")

    ingest_directory(in_dir, tmp_path / "out", ocr=tesseract)

    [path] = sorted((tmp_path / "out" / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    doc = load_document(path)
    assert [page.method for page in doc.pages] == ["ocr"]
    assert "Política de capacitación y desarrollo" in doc.pages[0].text
