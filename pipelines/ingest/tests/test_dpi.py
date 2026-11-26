"""Resolución que recibe el OCR (design.md: "Tesseract ... a 300 dpi").

Hallazgo 4 de la revisión: el dpi declarado por una imagen se usa solo si es plausible, se
aceptan los racionales de TIFF y hay un tope de píxeles por página.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ingest.pipeline as pipeline
from ingest.pipeline import ingest_directory
from tests.conftest import text_image, write_pdf
from tests.fakes import FakeOCREngine

WIDTH, HEIGHT = 1240, 400  # tamaño de text_image()


@pytest.mark.parametrize(
    ("filename", "fmt"),
    [pytest.param("a.png", "PNG", id="png"), pytest.param("a.tif", "TIFF", id="tiff-racional")],
)
def test_imagen_a_200_dpi_se_reescala_a_300(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, filename: str, fmt: str
) -> None:
    text_image(["Formulario"]).save(in_dir / filename, format=fmt, dpi=(200, 200))

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [call] = fake_ocr.calls
    assert (call.width, call.height) == (WIDTH * 3 // 2, HEIGHT * 3 // 2)
    assert call.dpi == 300


@pytest.mark.parametrize("dpi", [72, 1200], ids=["72-dpi", "1200-dpi"])
def test_dpi_implausible_se_ignora_y_no_se_reescala(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, dpi: int
) -> None:
    """72 dpi es el valor por defecto de muchas apps, no la resolución real del escaneo."""
    text_image(["Formulario"]).save(in_dir / "a.png", dpi=(dpi, dpi))

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [call] = fake_ocr.calls
    assert (call.width, call.height) == (WIDTH, HEIGHT)
    assert call.dpi == 300


def test_imagen_respeta_el_tope_de_pixeles(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "MAX_OCR_PIXELS", 1_000_000)
    text_image(["Formulario"]).save(in_dir / "a.png", dpi=(100, 100))  # x3 -> 4,5 Mpx

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [call] = fake_ocr.calls
    assert call.width * call.height <= 1_000_000
    assert call.width / call.height == pytest.approx(WIDTH / HEIGHT, rel=0.01)
    assert call.dpi < 300  # se informa la resolución efectiva, no la pedida


def test_pagina_de_pdf_respeta_el_tope_de_pixeles(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "MAX_OCR_PIXELS", 2_000_000)  # A4 a 300 dpi son 8,7 Mpx
    write_pdf(in_dir / "a.pdf", [text_image(["Escaneo"])])

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [call] = fake_ocr.calls
    assert call.width * call.height <= 2_000_000
    assert call.dpi < 300
