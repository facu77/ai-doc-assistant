"""Requirement: Idempotencia."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ingest.pipeline import DOCUMENTS_SUBDIR, ingest_directory, load_document
from tests.conftest import native_page, text_image, write_pdf
from tests.fakes import FakeOCREngine


@pytest.fixture
def corpus_copy(corpus_dir: Path, tmp_path: Path) -> Path:
    target = tmp_path / "corpus"
    shutil.copytree(corpus_dir, target)
    return target


def test_reingesta_del_corpus_omite_los_20_y_no_cambia_los_doc_id(
    corpus_copy: Path, out_dir: Path
) -> None:
    """Scenario: Reingesta. Segunda corrida: 20 omitidos y el `doc_id` de cada uno igual."""
    first_ocr = FakeOCREngine()
    first = ingest_directory(corpus_copy, out_dir, ocr=first_ocr)
    outputs_before = {p.name: p.read_bytes() for p in (out_dir / DOCUMENTS_SUBDIR).iterdir()}

    second_ocr = FakeOCREngine()
    second = ingest_directory(corpus_copy, out_dir, ocr=second_ocr)

    assert first.processed == 20
    assert second.skipped == 20
    assert second.processed == 0
    assert all(entry.status == "skipped" for entry in second.documents)
    first_ids = {entry.source: entry.doc_id for entry in first.documents}
    second_ids = {entry.source: entry.doc_id for entry in second.documents}
    assert second_ids == first_ids
    # No vuelve a procesar (ni un solo OCR) y no duplica ni reescribe la salida.
    assert second_ocr.calls == []
    outputs_after = {p.name: p.read_bytes() for p in (out_dir / DOCUMENTS_SUBDIR).iterdir()}
    assert outputs_after == outputs_before
    assert len(outputs_after) == 20


def test_documentos_omitidos_conservan_metodo_por_pagina_y_cer_en_el_reporte(
    corpus_copy: Path, out_dir: Path
) -> None:
    first = ingest_directory(corpus_copy, out_dir, ocr=FakeOCREngine())
    second = ingest_directory(corpus_copy, out_dir, ocr=FakeOCREngine())

    for before, after in zip(first.documents, second.documents, strict=True):
        assert after.pages == before.pages
        assert after.cer == before.cer
    assert second.pages_by_method == first.pages_by_method
    assert second.pages_processed == 0
    assert second.seconds_per_page is None


def test_un_archivo_modificado_cambia_de_doc_id_y_se_reprocesa(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    pdf = write_pdf(in_dir / "politica.pdf", [native_page(1)])
    first = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    write_pdf(pdf, [native_page(1), native_page(2)])
    second = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [before] = first.documents
    [after] = second.documents
    assert after.status == "processed"
    assert after.doc_id != before.doc_id


def test_otra_version_del_pipeline_reprocesa_con_el_mismo_doc_id(
    in_dir: Path, out_dir: Path
) -> None:
    text_image(["Escaneo"]).save(in_dir / "escaneo.png")
    ingest_directory(in_dir, out_dir, ocr=FakeOCREngine(), pipeline_version="1")

    ocr = FakeOCREngine()
    report = ingest_directory(in_dir, out_dir, ocr=ocr, pipeline_version="2")

    [entry] = report.documents
    assert entry.status == "processed"
    assert len(ocr.calls) == 1
    assert len(list((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))) == 1


def test_archivo_renombrado_se_omite_y_conserva_el_nombre_original_en_la_salida(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    """Hallazgo 15 (comportamiento documentado en el README): el doc_id es del contenido."""
    pdf = write_pdf(in_dir / "a-original.pdf", [native_page(1)])
    first = ingest_directory(in_dir, out_dir, ocr=fake_ocr)
    pdf.rename(in_dir / "b-renombrado.pdf")

    second = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [entry] = second.documents
    assert entry.source == "b-renombrado.pdf"
    assert entry.status == "skipped"
    assert entry.doc_id == first.documents[0].doc_id
    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    assert load_document(path).source == "a-original.pdf"


def test_archivos_duplicados_en_el_mismo_lote_generan_una_sola_salida(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    pdf = write_pdf(in_dir / "a.pdf", [native_page(1)])
    (in_dir / "b-copia.pdf").write_bytes(pdf.read_bytes())

    report = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    assert [(d.source, d.status) for d in report.documents] == [
        ("a.pdf", "processed"),
        ("b-copia.pdf", "skipped"),
    ]
    assert len(list((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))) == 1
