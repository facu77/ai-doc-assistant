"""CLI `ingest <in_dir> --out <out_dir>` (design.md, Context)."""

from __future__ import annotations

from pathlib import Path

from ingest.cli import run
from ingest.models import IngestReport
from ingest.pipeline import DOCUMENTS_SUBDIR
from ingest.report import JSON_REPORT_NAME, MARKDOWN_REPORT_NAME
from tests.conftest import native_page, text_image, write_pdf
from tests.fakes import FakeOCREngine


def test_cli_procesa_el_directorio_y_escribe_salida_y_reporte(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    write_pdf(in_dir / "politica.pdf", [native_page(1)])
    text_image(["Aviso"]).save(in_dir / "aviso.png")

    code = run([str(in_dir), "--out", str(out_dir)], ocr=fake_ocr)

    assert code == 0
    assert len(list((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))) == 2
    report = IngestReport.model_validate_json((out_dir / JSON_REPORT_NAME).read_text("utf-8"))
    assert report.processed == 2
    assert report.ocr_engine == "fake-ocr"
    assert (out_dir / MARKDOWN_REPORT_NAME).is_file()


def test_cli_devuelve_1_si_algun_documento_fallo_pero_procesa_el_resto(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    (in_dir / "memo.docx").write_bytes(b"PK\x03\x04 ficticio")
    write_pdf(in_dir / "politica.pdf", [native_page(1)])

    code = run([str(in_dir), "--out", str(out_dir)], ocr=fake_ocr)

    assert code == 1
    assert len(list((out_dir / DOCUMENTS_SUBDIR).glob("*.jsonl"))) == 1


def test_cli_permite_pisar_los_umbrales_de_deteccion(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    write_pdf(in_dir / "sello.pdf", [text_image(["Constancia"])], stamp="RECIBIDO RRHH")

    code = run(
        [str(in_dir), "--out", str(out_dir), "--min-native-chars", "5"],
        ocr=fake_ocr,
    )

    assert code == 0
    assert fake_ocr.calls == []


def test_cli_con_directorio_inexistente_devuelve_2(tmp_path: Path, fake_ocr: FakeOCREngine) -> None:
    code = run([str(tmp_path / "no-existe"), "--out", str(tmp_path / "out")], ocr=fake_ocr)
    assert code == 2


def test_cli_un_aviso_de_referencia_ilegible_no_cambia_el_codigo_de_salida(
    in_dir: Path, out_dir: Path, fake_ocr: FakeOCREngine
) -> None:
    """Decisión 10: la referencia sirve para medir, no para ingerir."""
    write_pdf(in_dir / "politica.pdf", [native_page(1)])
    (in_dir / "ground_truth").mkdir()
    (in_dir / "ground_truth" / "politica.pdf.json").write_text("{", encoding="utf-8")

    code = run([str(in_dir), "--out", str(out_dir)], ocr=fake_ocr)

    assert code == 0
    report = IngestReport.model_validate_json((out_dir / JSON_REPORT_NAME).read_text("utf-8"))
    assert report.warnings == 1
