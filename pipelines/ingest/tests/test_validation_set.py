"""Set de validación para elegir el psm (design.md, "Selección del psm"; decisión 5).

Está separado del corpus de prueba: otra semilla, otros documentos, otro directorio.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from ingest.corpus.content import DOCUMENTS, Columns, Row
from ingest.corpus.generate import (
    DEFAULT_SEED,
    MANIFEST_NAME,
    VALIDATION_SEED,
    generate_corpus,
    layout_page,
)
from ingest.corpus.validation_content import VALIDATION_DOCUMENTS
from ingest.models import CorpusManifest, GroundTruthDocument
from tests.conftest import VALIDATION_DIR


@pytest.fixture
def validation_dir() -> Path:
    if not VALIDATION_DIR.is_dir():
        pytest.fail(f"no existe {VALIDATION_DIR}; corré `uv run make-corpus --set validation`")
    return VALIDATION_DIR


def _manifest(path: Path) -> CorpusManifest:
    return CorpusManifest.model_validate_json(
        (path / "ground_truth" / MANIFEST_NAME).read_text(encoding="utf-8")
    )


def test_set_de_validacion_tiene_6_escaneos_limpios_y_ruidosos() -> None:
    assert len(VALIDATION_DOCUMENTS) == 6
    categories = Counter(doc.category for doc in VALIDATION_DOCUMENTS)
    assert set(categories) == {"clean_scan", "noisy_scan"}
    assert all(page.kind == "scan" for doc in VALIDATION_DOCUMENTS for page in doc.pages)


def test_incluye_documentos_a_dos_columnas_y_formularios_con_tabla() -> None:
    blocks = [b for doc in VALIDATION_DOCUMENTS for page in doc.pages for b in page.blocks]
    two_column = [
        d
        for d in VALIDATION_DOCUMENTS
        if any(isinstance(b, Columns) for p in d.pages for b in p.blocks)
    ]
    with_table = [
        d
        for d in VALIDATION_DOCUMENTS
        if any(isinstance(b, Row) for p in d.pages for b in p.blocks)
    ]
    assert len(two_column) >= 1
    assert len(with_table) >= 1
    assert blocks


def test_no_comparte_documentos_ni_semilla_con_el_corpus_de_prueba() -> None:
    assert VALIDATION_SEED != DEFAULT_SEED
    test_names = {doc.filename for doc in DOCUMENTS} | {doc.title for doc in DOCUMENTS}
    for doc in VALIDATION_DOCUMENTS:
        assert doc.filename not in test_names
        assert doc.title not in test_names


def test_dos_columnas_se_leen_columna_por_columna_en_la_referencia() -> None:
    """La referencia de una página a dos columnas es la columna izquierda entera y después
    la derecha: el orden en que la lee una persona."""
    doc = next(
        d for d in VALIDATION_DOCUMENTS if any(isinstance(b, Columns) for b in d.pages[0].blocks)
    )
    columns = next(b for b in doc.pages[0].blocks if isinstance(b, Columns))
    lines, reference = layout_page(doc.pages[0])
    xs = sorted({round(line.x) for line in lines})
    assert len(xs) >= 2  # hay líneas en dos posiciones horizontales distintas
    text = "\n".join(reference)
    last_left = columns.left[-1].text.split()[-1]
    first_right = columns.right[0].text.split()[0]
    assert text.index(last_left) < text.index(first_right)


def test_set_de_validacion_versionado_coincide_con_su_contenido(
    validation_dir: Path,
) -> None:
    manifest = _manifest(validation_dir)
    files = sorted(p.name for p in validation_dir.iterdir() if p.is_file())
    assert manifest.seed == VALIDATION_SEED
    assert sorted(e.source for e in manifest.documents) == files
    assert files == sorted(doc.filename for doc in VALIDATION_DOCUMENTS)
    for entry in manifest.documents:
        gt = GroundTruthDocument.model_validate_json(
            (validation_dir / "ground_truth" / f"{entry.source}.json").read_text("utf-8")
        )
        assert len(gt.pages) == entry.page_count
        assert all(page.kind == "scan" and page.text.strip() for page in gt.pages)


def test_set_de_validacion_es_reproducible_y_anclado_al_manifiesto(
    validation_dir: Path, tmp_path: Path
) -> None:
    generated = generate_corpus(tmp_path, seed=VALIDATION_SEED, documents=VALIDATION_DOCUMENTS)
    assert generated == _manifest(validation_dir)
