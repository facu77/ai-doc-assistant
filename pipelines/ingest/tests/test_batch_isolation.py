"""Requirement: Salida normalizada por documento ("el resto del lote se procesa igual").

Hallazgo 3 de la revisión: ninguna excepción de un archivo puede cortar el lote.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

import ingest.pipeline as pipeline
from ingest.pipeline import DOCUMENTS_SUBDIR, ingest_directory
from tests.conftest import native_page, text_image, write_pdf
from tests.fakes import FakeOCREngine


def _by_source(
    in_dir: Path, out_dir: Path, ocr: FakeOCREngine
) -> dict[str, tuple[str, str | None]]:
    report = ingest_directory(in_dir, out_dir, ocr=ocr)
    return {d.source: (d.status, d.error) for d in report.documents}


def test_bomba_de_descompresion_es_unreadable_file_y_el_lote_sigue(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    text_image(["Imagen enorme"]).save(in_dir / "a-enorme.png")  # 1240 x 400 = 496.000 px
    write_pdf(in_dir / "b-ok.pdf", [native_page(1)])
    # Pillow lanza DecompressionBombError por encima del doble de MAX_IMAGE_PIXELS.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100_000)

    result = _by_source(in_dir, out_dir, fake_ocr)

    assert result["a-enorme.png"] == ("error", "unreadable_file")
    assert result["b-ok.pdf"] == ("processed", None)
    assert fake_ocr.calls == []


def test_excepcion_inesperada_de_pymupdf_en_una_pagina_no_corta_el_lote(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La falla se inyecta en pymupdf (no en el adaptador): el adaptador es quien la traduce."""
    write_pdf(in_dir / "a-pagina-rota.pdf", [native_page(1)])
    write_pdf(in_dir / "b-ok.pdf", [native_page(1)])
    real_get_text: Callable[..., object] = pymupdf.Page.get_text
    calls = {"n": 0}

    def flaky_get_text(page: pymupdf.Page, *args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:  # el primer archivo en orden alfabético
            raise RuntimeError("estructura de página corrupta (simulada)")
        return real_get_text(page, *args, **kwargs)

    monkeypatch.setattr(pymupdf.Page, "get_text", flaky_get_text)

    result = _by_source(in_dir, out_dir, fake_ocr)

    assert result["a-pagina-rota.pdf"] == ("error", "unreadable_file")
    assert result["b-ok.pdf"] == ("processed", None)


def test_error_al_rasterizar_no_corta_el_lote(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_pdf(in_dir / "a-escaneo.pdf", [text_image(["Escaneo"])])
    write_pdf(in_dir / "b-ok.pdf", [native_page(1)])

    def broken_get_pixmap(page: pymupdf.Page, *args: object, **kwargs: object) -> object:
        raise ValueError("pixmap inválido (simulado)")

    monkeypatch.setattr(pymupdf.Page, "get_pixmap", broken_get_pixmap)

    result = _by_source(in_dir, out_dir, fake_ocr)

    assert result["a-escaneo.pdf"] == ("error", "unreadable_file")
    assert result["b-ok.pdf"] == ("processed", None)


def test_error_de_lectura_al_calcular_el_hash_no_corta_el_lote(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revisión 2, MEDIO 3: sha256_file también lee el archivo y puede fallar."""
    write_pdf(in_dir / "a-sin-permiso.pdf", [native_page(1)])
    write_pdf(in_dir / "b-ok.pdf", [native_page(1)])
    real_sha256 = pipeline.sha256_file

    def sha256_or_denied(path: Path) -> str:
        if path.name == "a-sin-permiso.pdf":
            raise PermissionError(13, "Permission denied (simulado)", str(path))
        return real_sha256(path)

    monkeypatch.setattr(pipeline, "sha256_file", sha256_or_denied)

    result = _by_source(in_dir, out_dir, fake_ocr)

    assert result["a-sin-permiso.pdf"] == ("error", "unreadable_file")
    assert result["b-ok.pdf"] == ("processed", None)


def test_un_bug_propio_no_se_disfraza_de_unreadable_file(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revisión 2, BAJO: un ValueError del código propio (por ejemplo, una ValidationError
    al construir un modelo) no es un archivo ilegible: tiene que verse, no reportarse."""
    write_pdf(in_dir / "a.pdf", [native_page(1)])

    def buggy_normalize(text: str) -> str:
        raise ValueError("bug simulado en la normalización")

    monkeypatch.setattr(pipeline, "normalize_text", buggy_normalize)

    with pytest.raises(ValueError, match="bug simulado"):
        ingest_directory(in_dir, out_dir, ocr=fake_ocr)


def test_texto_de_referencia_corrupto_queda_acotado_a_su_documento(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    write_pdf(in_dir / "a.pdf", [native_page(1)])
    write_pdf(in_dir / "b.pdf", [native_page(1)])
    gt_dir = in_dir / "ground_truth"
    gt_dir.mkdir()
    (gt_dir / "a.pdf.json").write_text("{ esto no es JSON", encoding="utf-8")

    result = _by_source(in_dir, out_dir, fake_ocr)

    assert result["a.pdf"] == ("error", "invalid_ground_truth")
    assert result["b.pdf"] == ("processed", None)
    assert len(list((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))) == 1
