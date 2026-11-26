"""Requirement: Datos ficticios. Ningún dato con forma de PII argentina real (hallazgo 9).

Los patrones se prueban primero contra ejemplos inventados, para que el test no pase por
tener una regex que no encuentra nada.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ingest.models import GroundTruthDocument
from tests.conftest import CORPUS_DIR

PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "dni-con-puntos": re.compile(r"\b\d{2}\.\d{3}\.\d{3}\b"),
    "dni-sin-puntos": re.compile(r"\b\d{7,8}\b"),
    "palabra-dni": re.compile(r"\bD\.?N\.?I\b", re.IGNORECASE),
    "cuit-cuil": re.compile(r"\b(?:20|23|24|27|30|33|34)-?\d{8}-?\d\b"),
    "cbu": re.compile(r"\b\d{22}\b"),
    "celular-o-fijo-amba": re.compile(
        r"(?:\+?54[ -]?)?(?:9[ -]?)?\b(?:11|15)[ -]?\d{4}[ -]?\d{4}\b"
    ),
    "telefono-0800": re.compile(r"\b0[68]00[ -]?\d{3}[ -]?\d{4}\b"),
    "telefono-generico": re.compile(r"\b\d{4}[ -]\d{4}\b"),
}

# Ejemplos inventados: solo existen para comprobar que cada patrón detecta algo.
POSITIVE_EXAMPLES = {
    "dni-con-puntos": "DNI 30.123.456",
    "dni-sin-puntos": "documento 30123456",
    "palabra-dni": "D.N.I. del empleado",
    "cuit-cuil": "CUIL 20-30123456-7",
    "cbu": "CBU 0170123400000012345678",
    "celular-o-fijo-amba": "llamar al +54 9 11 4567 8901",
    "telefono-0800": "línea 0800-555-0199",
    "telefono-generico": "interno o fijo 4567-8901",
}

DATA_DIRS = [pytest.param(CORPUS_DIR, id="corpus")]


@pytest.mark.parametrize("name", sorted(PII_PATTERNS))
def test_cada_patron_detecta_su_ejemplo(name: str) -> None:
    assert PII_PATTERNS[name].search(POSITIVE_EXAMPLES[name])


@pytest.mark.parametrize("data_dir", DATA_DIRS)
def test_el_texto_versionado_no_tiene_datos_con_forma_de_pii(data_dir: Path) -> None:
    texts = [
        page.text
        for path in sorted((data_dir / "ground_truth").glob("*.json"))
        if path.name != "manifest.json"
        for page in GroundTruthDocument.model_validate_json(path.read_text("utf-8")).pages
    ]
    assert texts
    found = {
        name: match.group(0)
        for name, pattern in PII_PATTERNS.items()
        for text in texts
        for match in [pattern.search(text)]
        if match
    }
    assert found == {}
