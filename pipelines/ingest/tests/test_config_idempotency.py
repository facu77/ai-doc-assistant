"""Requirement: Idempotencia. Scenario: Cambio de configuración fuerza reprocesamiento."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingest.models import IngestedDocument
from ingest.pipeline import (
    DOCUMENTS_SUBDIR,
    PIPELINE_VERSION,
    config_hash,
    ingest_directory,
    load_document,
)
from ingest.settings import IngestSettings
from tests.conftest import native_page, text_image, write_pdf
from tests.fakes import FakeOCREngine


@pytest.fixture
def mixed_dir(in_dir: Path) -> Path:
    write_pdf(in_dir / "mixto.pdf", [native_page(1), text_image(["Anexo escaneado"])])
    return in_dir


def _only_output(out_dir: Path) -> IngestedDocument:
    [path] = sorted((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))
    return load_document(path)


def test_la_salida_registra_motor_de_ocr_y_huella_de_configuracion(
    mixed_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    settings = IngestSettings()

    ingest_directory(mixed_dir, out_dir, ocr=fake_ocr, settings=settings)

    doc = _only_output(out_dir)
    assert doc.ocr_engine == "fake-ocr"
    assert doc.config_hash == config_hash(
        settings, pipeline_version=PIPELINE_VERSION, ocr_engine="fake-ocr"
    )


@pytest.mark.parametrize(
    "changed",
    [
        pytest.param(IngestSettings(ocr_psm=4), id="psm"),
        pytest.param(IngestSettings(ocr_dpi=200), id="dpi"),
        pytest.param(IngestSettings(min_native_chars=10), id="umbral-de-caracteres"),
        pytest.param(IngestSettings(min_printable_ratio=0.5), id="umbral-de-imprimibles"),
        pytest.param(IngestSettings(ocr_lang="spa"), id="idiomas"),
    ],
)
def test_cambio_de_configuracion_fuerza_reprocesamiento(
    mixed_dir: Path, out_dir: Path, changed: IngestSettings
) -> None:
    """Scenario: Cambio de configuración fuerza reprocesamiento."""
    first = ingest_directory(mixed_dir, out_dir, ocr=FakeOCREngine(), settings=IngestSettings())
    before = _only_output(out_dir)

    ocr = FakeOCREngine()
    second = ingest_directory(mixed_dir, out_dir, ocr=ocr, settings=changed)

    [entry] = second.documents
    assert entry.status == "processed"
    assert entry.doc_id == first.documents[0].doc_id
    assert len(ocr.calls) == 1
    after = _only_output(out_dir)  # no se duplica: sigue habiendo un solo JSONL
    assert after.doc_id == before.doc_id
    assert after.config_hash != before.config_hash
    assert after.config_hash == config_hash(
        changed, pipeline_version=PIPELINE_VERSION, ocr_engine="fake-ocr"
    )


def test_cambio_de_motor_de_ocr_fuerza_reprocesamiento(mixed_dir: Path, out_dir: Path) -> None:
    ingest_directory(mixed_dir, out_dir, ocr=FakeOCREngine(name="motor-a"))

    ocr = FakeOCREngine(name="motor-b")
    report = ingest_directory(mixed_dir, out_dir, ocr=ocr)

    assert report.documents[0].status == "processed"
    assert _only_output(out_dir).ocr_engine == "motor-b"


def test_misma_configuracion_se_omite_y_el_timeout_no_cuenta(
    mixed_dir: Path, out_dir: Path
) -> None:
    ingest_directory(mixed_dir, out_dir, ocr=FakeOCREngine(), settings=IngestSettings())

    ocr = FakeOCREngine()
    report = ingest_directory(mixed_dir, out_dir, ocr=ocr, settings=IngestSettings(ocr_timeout_s=5))

    assert report.documents[0].status == "skipped"
    assert ocr.calls == []


def test_la_huella_es_determinista_y_sensible_a_la_version() -> None:
    settings = IngestSettings()
    a = config_hash(settings, pipeline_version="1", ocr_engine="x")
    assert a == config_hash(IngestSettings(), pipeline_version="1", ocr_engine="x")
    assert a != config_hash(settings, pipeline_version="2", ocr_engine="x")
    assert len(a) == 64


def test_el_reporte_registra_la_huella_de_la_corrida(
    mixed_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    report = ingest_directory(mixed_dir, out_dir, ocr=fake_ocr)

    assert report.config_hash == _only_output(out_dir).config_hash
