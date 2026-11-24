"""Requirement: Reporte de ingesta (y CER por documento cuando hay texto de referencia)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import fmean

import pytest

from ingest.models import GroundTruthDocument, IngestReport
from ingest.pipeline import ingest_directory
from ingest.report import JSON_REPORT_NAME, MARKDOWN_REPORT_NAME, write_report
from tests.conftest import CORPUS_DIR, native_page, write_pdf
from tests.fakes import FakeOCREngine


@pytest.fixture(scope="module")
def corpus_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[IngestReport, Path]:
    out_dir = tmp_path_factory.mktemp("corpus-out")
    report = ingest_directory(CORPUS_DIR, out_dir, ocr=FakeOCREngine())
    write_report(report, out_dir)
    return report, out_dir


def _ground_truth(corpus_dir: Path, source: str) -> GroundTruthDocument:
    path = corpus_dir / "ground_truth" / f"{source}.json"
    return GroundTruthDocument.model_validate_json(path.read_text(encoding="utf-8"))


def test_reporte_del_corpus_lista_los_20_documentos_con_estado_metodo_y_cer(
    corpus_run: tuple[IngestReport, Path],
) -> None:
    """Scenario: Corpus completo. Lista los 20 con estado, método por página y CER."""
    report, _ = corpus_run
    assert report.documents_total == 20
    assert len(report.documents) == 20
    for entry in report.documents:
        assert entry.status == "processed", entry.source
        assert entry.doc_id is not None
        assert entry.category is not None
        assert len(entry.pages) == entry.page_count > 0
        assert entry.cer is not None, entry.source
        assert all(page.cer is not None for page in entry.pages)


def test_totales_del_reporte_coinciden_con_la_suma_por_documento(
    corpus_run: tuple[IngestReport, Path],
) -> None:
    """Scenario: Corpus completo. Los totales coinciden con la suma por documento."""
    report, _ = corpus_run
    docs = report.documents
    assert report.processed + report.skipped + report.errors == report.documents_total
    assert report.processed == sum(1 for d in docs if d.status == "processed")
    assert report.pages_total == sum(d.page_count for d in docs)
    methods = Counter(page.method for d in docs for page in d.pages)
    assert report.pages_by_method == {"native": methods["native"], "ocr": methods["ocr"]}
    for category, stats in report.cer_by_category.items():
        cers = [d.cer for d in docs if d.category == category and d.cer is not None]
        assert stats.documents == len(cers)
        assert stats.mean_cer == pytest.approx(fmean(cers))
        assert stats.max_cer == pytest.approx(max(cers))
    assert set(report.cer_by_category) == {"native", "clean_scan", "noisy_scan", "mixed"}
    assert report.total_seconds > 0
    assert report.pages_processed == report.pages_total
    assert report.seconds_per_page is not None
    assert report.seconds_per_page == pytest.approx(report.total_seconds / report.pages_total)


def test_metodo_por_pagina_coincide_con_como_se_genero_cada_pagina(
    corpus_run: tuple[IngestReport, Path], corpus_dir: Path
) -> None:
    """La detección por página acierta en el corpus: nativa -> `native`, escaneada -> `ocr`."""
    report, _ = corpus_run
    for entry in report.documents:
        truth = _ground_truth(corpus_dir, entry.source)
        expected = ["native" if page.kind == "native" else "ocr" for page in truth.pages]
        assert [page.method for page in entry.pages] == expected, entry.source


def test_documentos_nativos_coinciden_exactamente_con_la_referencia(
    corpus_run: tuple[IngestReport, Path],
) -> None:
    """La extracción nativa no pierde texto: CER 0 en los 8 nativos (no depende del OCR)."""
    report, _ = corpus_run
    native = [d for d in report.documents if d.category == "native"]
    assert len(native) == 8
    assert all(d.cer == 0.0 for d in native), [(d.source, d.cer) for d in native]


def test_reporte_se_escribe_en_json_y_markdown(corpus_run: tuple[IngestReport, Path]) -> None:
    report, out_dir = corpus_run
    json_path = out_dir / JSON_REPORT_NAME
    md_path = out_dir / MARKDOWN_REPORT_NAME

    assert IngestReport.model_validate_json(json_path.read_text(encoding="utf-8")) == report
    markdown = md_path.read_text(encoding="utf-8")
    for heading in ("Resumen", "Páginas por método", "CER por categoría", "Documentos", "Errores"):
        assert heading in markdown
    for entry in report.documents:
        assert entry.source in markdown


def test_reporte_markdown_lista_los_errores(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    (in_dir / "memo.docx").write_bytes(b"PK\x03\x04 ficticio")
    write_pdf(in_dir / "ok.pdf", [native_page(1)])

    report = ingest_directory(in_dir, out_dir, ocr=fake_ocr)
    _, md_path = write_report(report, out_dir)

    errors_section = md_path.read_text(encoding="utf-8").split("Errores", 1)[1]
    assert "memo.docx" in errors_section
    assert "unsupported_format" in errors_section
    data = json.loads((out_dir / JSON_REPORT_NAME).read_text(encoding="utf-8"))
    assert data["errors"] == 1


def test_sin_texto_de_referencia_el_cer_queda_vacio(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    write_pdf(in_dir / "sin-referencia.pdf", [native_page(1)])

    report = ingest_directory(in_dir, out_dir, ocr=fake_ocr)

    [entry] = report.documents
    assert entry.cer is None
    assert entry.category is None
    assert report.cer_by_category == {}
    assert report.mean_cer is None
