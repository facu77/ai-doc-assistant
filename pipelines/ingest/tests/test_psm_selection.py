"""Regla preregistrada de selección del psm (design.md, "Selección del psm")."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingest.models import DocumentReport, IngestReport, PageReport
from ingest.psm_selection import choose_psm, main, mean_scanned_page_cer
from ingest.report import build_report


def _report(pages: list[tuple[str, float | None]]) -> IngestReport:
    doc = DocumentReport(
        source="v01.pdf",
        status="processed",
        doc_id="0" * 64,
        category="clean_scan",
        page_count=len(pages),
        pages=[
            PageReport(page_number=n, method="ocr" if m == "ocr" else "native", cer=c)
            for n, (m, c) in enumerate(pages, start=1)
        ],
        cer=0.0,
    )
    return build_report(
        [doc], pipeline_version="t", ocr_engine="fake", total_seconds=1.0, pages_processed=1
    )


def test_cer_medio_solo_cuenta_paginas_ocr_con_referencia() -> None:
    report = _report([("ocr", 0.02), ("native", 0.50), ("ocr", 0.04), ("ocr", None)])
    assert mean_scanned_page_cer(report) == pytest.approx(0.03)


def test_cer_medio_sin_paginas_escaneadas_es_un_error() -> None:
    with pytest.raises(ValueError, match="páginas escaneadas"):
        mean_scanned_page_cer(_report([("native", 0.0)]))


@pytest.mark.parametrize(
    ("means", "expected"),
    [
        pytest.param({3: 0.050, 4: 0.010, 6: 0.030}, 4, id="gana-psm-4"),
        pytest.param({3: 0.050, 4: 0.030, 6: 0.010}, 6, id="gana-psm-6"),
        pytest.param({3: 0.010, 4: 0.030, 6: 0.020}, 3, id="gana-psm-3"),
        pytest.param({3: 0.0105, 4: 0.0100, 6: 0.0200}, 3, id="empate-con-psm-3-se-queda-3"),
        pytest.param({3: 0.0300, 4: 0.0105, 6: 0.0100}, 4, id="empate-4-y-6-se-elige-4"),
        pytest.param({3: 0.0120, 4: 0.0100, 6: 0.0300}, 4, id="0.2-pp-no-es-empate"),
    ],
)
def test_regla_de_seleccion(means: dict[int, float], expected: int) -> None:
    assert choose_psm(means) == expected


def test_la_regla_exige_los_tres_candidatos() -> None:
    with pytest.raises(ValueError, match="candidatos"):
        choose_psm({3: 0.01, 4: 0.02})


def test_main_lee_los_reportes_y_aplica_la_regla(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths: dict[int, Path] = {}
    for psm, value in {3: 0.05, 4: 0.01, 6: 0.02}.items():
        path = tmp_path / f"psm{psm}.json"
        path.write_text(_report([("ocr", value)]).model_dump_json(), encoding="utf-8")
        paths[psm] = path

    code = main(["--psm3", str(paths[3]), "--psm4", str(paths[4]), "--psm6", str(paths[6])])

    assert code == 0
    out = capsys.readouterr().out
    assert "psm elegido: 4" in out
    assert "5.00 %" in out
