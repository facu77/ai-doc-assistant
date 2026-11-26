"""Las corridas versionadas en evals/runs/ingest/ se tienen que poder leer con los modelos.

Las de `da01914` son del esquema 1 (sin config_hash) y quedan como historia en JSON plano.
Las demás las leen choose_psm.py y el gate de regresión de la integración.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ingest.models import IngestReport
from tests.conftest import REPO_ROOT

RUNS_DIR = REPO_ROOT / "evals" / "runs" / "ingest"
SCHEMA_2_RUNS = sorted(p for p in RUNS_DIR.glob("*.json") if "_da01914_" not in p.name)


def test_hay_corridas_registradas() -> None:
    assert len(SCHEMA_2_RUNS) >= 6


@pytest.mark.parametrize("path", SCHEMA_2_RUNS, ids=lambda p: p.name)
def test_las_corridas_versionadas_se_leen_con_el_modelo_actual(path: Path) -> None:
    report = IngestReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.documents_total == len(report.documents)
