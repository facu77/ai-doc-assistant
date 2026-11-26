"""Requirement: Salida normalizada por documento."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ingest.models import IngestedDocument
from ingest.pipeline import DOCUMENTS_SUBDIR, PIPELINE_VERSION, ingest_directory, load_document
from tests.conftest import native_page, text_image, write_pdf
from tests.fakes import FailingOCREngine, FakeOCREngine


def _outputs(out_dir: Path) -> list[IngestedDocument]:
    return [load_document(path) for path in sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))]


def test_pdf_nativo_de_3_paginas_sale_con_3_paginas_native(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    """Scenario: PDF nativo. 3 páginas con capa de texto -> 3 páginas `native`, texto no vacío."""
    pdf = write_pdf(in_dir / "politica.pdf", [native_page(1), native_page(2), native_page(3)])

    report = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [doc] = _outputs(out_dir)
    assert doc.page_count == 3
    assert [page.page_number for page in doc.pages] == [1, 2, 3]
    assert [page.method for page in doc.pages] == ["native", "native", "native"]
    assert all(page.text.strip() for page in doc.pages)
    assert "Página 2 de la política de prueba." in doc.pages[1].text
    assert fake_ocr.calls == []
    # Registro con doc_id estable (sha256 del archivo), origen y versión del pipeline.
    assert doc.doc_id == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert doc.source == "politica.pdf"
    assert doc.source_format == "pdf"
    assert doc.pipeline_version == PIPELINE_VERSION
    [entry] = report.documents
    assert entry.status == "processed"
    assert entry.doc_id == doc.doc_id


def test_salida_es_un_jsonl_por_documento_con_el_modelo_pydantic(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    write_pdf(in_dir / "a.pdf", [native_page(1)])
    write_pdf(in_dir / "b.pdf", [native_page(1), native_page(2)])

    ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    files = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    assert len(files) == 2
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        doc = IngestedDocument.model_validate_json(lines[0])
        assert path.stem == doc.doc_id


def test_archivo_docx_se_reporta_como_unsupported_format_y_el_lote_sigue(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    """Scenario: Archivo no soportado. `.docx` -> `unsupported_format`; el resto se procesa."""
    (in_dir / "a-memo.docx").write_bytes(b"PK\x03\x04 documento de Word ficticio")
    write_pdf(in_dir / "b-politica.pdf", [native_page(1)])
    text_image(["Formulario escaneado"]).save(in_dir / "c-formulario.png")

    report = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    by_source = {entry.source: entry for entry in report.documents}
    assert set(by_source) == {"a-memo.docx", "b-politica.pdf", "c-formulario.png"}
    assert by_source["a-memo.docx"].status == "error"
    assert by_source["a-memo.docx"].error == "unsupported_format"
    assert by_source["b-politica.pdf"].status == "processed"
    assert by_source["c-formulario.png"].status == "processed"
    assert report.errors == 1
    assert report.processed == 2
    assert {doc.source for doc in _outputs(out_dir)} == {"b-politica.pdf", "c-formulario.png"}


def test_pdf_corrupto_se_reporta_como_unreadable_file_y_el_lote_sigue(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    (in_dir / "a-roto.pdf").write_bytes(b"%PDF-1.4 esto no es un PDF valido")
    write_pdf(in_dir / "b-ok.pdf", [native_page(1)])

    report = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    by_source = {entry.source: entry for entry in report.documents}
    assert by_source["a-roto.pdf"].status == "error"
    assert by_source["a-roto.pdf"].error == "unreadable_file"
    assert by_source["b-ok.pdf"].status == "processed"


def test_falla_del_ocr_se_reporta_como_ocr_failed_y_el_lote_sigue(
    in_dir: Path, out_dir: Path
) -> None:
    text_image(["Escaneo"]).save(in_dir / "a-escaneo.png")
    write_pdf(in_dir / "b-nativo.pdf", [native_page(1)])
    failing = FailingOCREngine()

    report = ingest_directory(in_dir, out_dir, ocr=failing)

    by_source = {entry.source: entry for entry in report.documents}
    assert by_source["a-escaneo.png"].status == "error"
    assert by_source["a-escaneo.png"].error == "ocr_failed"
    assert by_source["b-nativo.pdf"].status == "processed"
    assert failing.calls == 1
    assert [doc.source for doc in _outputs(out_dir)] == ["b-nativo.pdf"]
