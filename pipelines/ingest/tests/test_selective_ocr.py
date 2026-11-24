"""Requirement: OCR selectivo (y la detección nativo/escaneo por página de design.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingest.detection import is_native_text, printable_ratio
from ingest.pipeline import DOCUMENTS_SUBDIR, ingest_directory, load_document
from ingest.settings import IngestSettings
from tests.conftest import native_page, text_image, write_pdf
from tests.fakes import FakeOCREngine

A4_WIDTH_AT_300_DPI = 2480  # 595,28 pt / 72 * 300


def test_pdf_mixto_solo_la_pagina_2_pasa_por_ocr(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    """Scenario: PDF mixto. Páginas 1 y 3 nativas, 2 escaneada -> solo la 2 tiene `ocr`."""
    scanned = text_image(["Anexo escaneado", "Escala de calificación"])
    write_pdf(in_dir / "mixto.pdf", [native_page(1), scanned, native_page(3)])

    report = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    doc = load_document(path)
    assert [page.method for page in doc.pages] == ["native", "ocr", "native"]
    assert len(fake_ocr.calls) == 1
    assert doc.pages[1].text == "Texto reconocido por el OCR falso, llamada 1"
    assert "Página 3 de la política de prueba." in doc.pages[2].text
    # Se registra qué páginas pasaron por OCR también en el reporte.
    [entry] = report.documents
    assert [page.method for page in entry.pages] == ["native", "ocr", "native"]


def test_la_pagina_escaneada_se_rasteriza_a_300_dpi(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    write_pdf(in_dir / "escaneo.pdf", [text_image(["Escaneo"])])

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [call] = fake_ocr.calls
    assert call.dpi == 300
    assert abs(call.width - A4_WIDTH_AT_300_DPI) <= 2


def test_png_suelto_sale_con_1_pagina_ocr(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    """Scenario: Imagen suelta. Un PNG con texto -> 1 página con método `ocr`."""
    text_image(["Aviso al personal", "Cambio de turnos"]).save(in_dir / "aviso.png")

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    doc = load_document(path)
    assert doc.source_format == "png"
    assert doc.page_count == 1
    assert [page.method for page in doc.pages] == ["ocr"]
    assert doc.pages[0].text == "Texto reconocido por el OCR falso, llamada 1"
    assert len(fake_ocr.calls) == 1


def test_jpeg_suelto_tambien_es_una_pagina_ocr(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    text_image(["Formulario"]).save(in_dir / "formulario.jpg", format="JPEG")

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    doc = load_document(path)
    assert doc.source_format == "jpeg"
    assert [page.method for page in doc.pages] == ["ocr"]


def test_pagina_escaneada_con_sello_nativo_corto_pasa_por_ocr(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    """Scenario: Página escaneada con poco texto nativo (versión rápida, OCR falso).

    El sello tiene capa de texto pero menos de 50 caracteres: la página va a OCR y su texto
    es el reconocido (no el del sello).
    """
    stamp = "RECIBIDO RRHH 02/11/2026"
    assert len(stamp) < 50
    write_pdf(in_dir / "constancia.pdf", [text_image(["Constancia de capacitación"])], stamp=stamp)

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    doc = load_document(path)
    [page] = doc.pages
    assert page.method == "ocr"
    assert page.native_char_count == len(stamp.replace(" ", ""))
    assert page.text == "Texto reconocido por el OCR falso, llamada 1"


def test_los_umbrales_de_deteccion_son_configurables(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    stamp = "RECIBIDO RRHH 02/11/2026"
    write_pdf(in_dir / "constancia.pdf", [text_image(["Constancia"])], stamp=stamp)
    settings = IngestSettings(min_native_chars=10)

    ingest_directory(in_dir, out_dir, ocr=fake_ocr, settings=settings)

    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    [page] = load_document(path).pages
    assert page.method == "native"
    assert page.text == stamp
    assert fake_ocr.calls == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("x" * 50, True, id="50-caracteres-justo-en-el-umbral"),
        pytest.param("x" * 49, False, id="49-caracteres"),
        pytest.param("  ".join(["xxxxx"] * 10), True, id="los-blancos-no-cuentan-pero-alcanza"),
        pytest.param(" \n " * 40, False, id="solo-blancos"),
        pytest.param("�" * 60, False, id="capa-de-texto-rota-ratio-0"),
        pytest.param("x" * 54 + "�" * 6, True, id="ratio-0.9-justo"),
        pytest.param("x" * 53 + "�" * 7, False, id="ratio-menor-a-0.9"),
    ],
)
def test_deteccion_nativa_con_50_caracteres_y_ratio_0_9(text: str, expected: bool) -> None:
    assert is_native_text(text, min_chars=50, min_printable_ratio=0.9) is expected


def test_printable_ratio_ignora_blancos_y_penaliza_caracteres_de_reemplazo() -> None:
    assert printable_ratio("ab cd") == 1.0
    assert printable_ratio("ab��") == 0.5
    assert printable_ratio("ab\x07\x07") == 0.5
    assert printable_ratio("") == 0.0
