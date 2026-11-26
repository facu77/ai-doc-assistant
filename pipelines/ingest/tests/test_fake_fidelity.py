"""Fakes más fieles (hallazgo 5): el texto del OCR llega sucio y la imagen importa."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from ingest.pipeline import DOCUMENTS_SUBDIR, ingest_directory, load_document
from tests.conftest import native_page, text_image, write_pdf
from tests.fakes import DirtyTextOCREngine, PixelMeanOCREngine

A4_PIXELS_AT_150_DPI = (1240, 1754)


def _page_image(fill: int, *, half_black: bool = False) -> Image.Image:
    image = Image.new("L", A4_PIXELS_AT_150_DPI, color=fill)
    if half_black:
        ImageDraw.Draw(image).rectangle((0, 0, A4_PIXELS_AT_150_DPI[0], 877), fill=0)
    return image


def test_el_texto_del_ocr_se_normaliza(in_dir: Path, out_dir: Path) -> None:
    text_image(["Página uno"]).save(in_dir / "a.png")

    ingest_directory(in_dir, out_dir, ocr=DirtyTextOCREngine())

    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    [page] = load_document(path).pages
    assert page.text == "Página uno"


def test_cada_pagina_escaneada_llega_al_ocr_con_su_propia_imagen(
    in_dir: Path, out_dir: Path
) -> None:
    """Rasterizar la página equivocada o mandar una imagen en blanco cambia la media."""
    half_black = _page_image(255, half_black=True)  # media ~127
    dark_gray = _page_image(64)  # media 64
    write_pdf(in_dir / "a.pdf", [native_page(1), half_black, native_page(3), dark_gray])
    ocr = PixelMeanOCREngine()

    ingest_directory(in_dir, out_dir, ocr=ocr)

    assert len(ocr.means) == 2
    expected = [_mean(half_black), _mean(dark_gray)]
    for received, wanted in zip(ocr.means, expected, strict=True):
        assert abs(received - wanted) < 3, (received, wanted)
    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    doc = load_document(path)
    assert [p.method for p in doc.pages] == ["native", "ocr", "native", "ocr"]
    assert doc.pages[1].text == f"media {ocr.means[0]:.1f}"


def _mean(image: Image.Image) -> float:
    histogram = image.histogram()
    return sum(value * count for value, count in enumerate(histogram)) / sum(histogram)
