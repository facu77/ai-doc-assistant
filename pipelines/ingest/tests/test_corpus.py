"""Requirement: Datos ficticios (composición y reproducibilidad del corpus versionado)."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import numpy as np

from ingest.corpus.content import DOCUMENTS
from ingest.corpus.generate import DEFAULT_SEED, MANIFEST_NAME, generate_corpus, render_document
from ingest.detection import is_native_text
from ingest.models import CorpusManifest, GroundTruthDocument
from ingest.pdf import open_pdf, page_count, page_text


def _manifest(corpus_dir: Path) -> CorpusManifest:
    path = corpus_dir / "ground_truth" / MANIFEST_NAME
    return CorpusManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _ground_truth(corpus_dir: Path) -> dict[str, GroundTruthDocument]:
    docs = [
        GroundTruthDocument.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((corpus_dir / "ground_truth").glob("*.json"))
        if path.name != MANIFEST_NAME
    ]
    return {doc.source: doc for doc in docs}


def _file_page_count(path: Path) -> int:
    if path.suffix == ".pdf":
        with open_pdf(path) as doc:
            return page_count(doc)
    return 1


def test_corpus_tiene_20_documentos_8_6_4_2_con_referencia_por_pagina(corpus_dir: Path) -> None:
    """Scenario: Composición del corpus. 8 nativos, 6 limpios, 4 ruidosos y 2 mixtos."""
    manifest = _manifest(corpus_dir)
    truth = _ground_truth(corpus_dir)
    documents = sorted(p.name for p in corpus_dir.iterdir() if p.is_file())

    assert len(documents) == 20
    assert sorted(entry.source for entry in manifest.documents) == documents
    assert set(truth) == set(documents)
    counts = Counter(entry.category for entry in manifest.documents)
    assert counts == {"native": 8, "clean_scan": 6, "noisy_scan": 4, "mixed": 2}
    for entry in manifest.documents:
        path = corpus_dir / entry.source
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry.sha256
        gt = truth[entry.source]
        assert gt.category == entry.category
        assert [page.page_number for page in gt.pages] == list(range(1, entry.page_count + 1))
        assert _file_page_count(path) == entry.page_count
        assert all(page.text.strip() for page in gt.pages)


def test_los_mixtos_combinan_paginas_nativas_y_escaneadas(corpus_dir: Path) -> None:
    truth = _ground_truth(corpus_dir)
    mixed = [doc for doc in truth.values() if doc.category == "mixed"]
    assert len(mixed) == 2
    for doc in mixed:
        kinds = {page.kind for page in doc.pages}
        assert kinds == {"native", "scan"}, doc.source


def test_hay_una_pagina_escaneada_con_sello_nativo_de_menos_de_50_caracteres(
    corpus_dir: Path,
) -> None:
    """Precondición del scenario 'Página escaneada con poco texto nativo' en el corpus."""
    truth = _ground_truth(corpus_dir)
    stamped: list[tuple[str, int, str]] = []
    for doc in truth.values():
        if not doc.source.endswith(".pdf"):
            continue
        with open_pdf(corpus_dir / doc.source) as pdf:
            for page in doc.pages:
                native = page_text(pdf, page.page_number - 1).strip()
                if page.kind == "scan" and native:
                    stamped.append((doc.source, page.page_number, native))
    assert len(stamped) == 1
    [(_, _, stamp)] = stamped
    assert 0 < len(stamp) < 50
    assert not is_native_text(stamp, min_chars=50, min_printable_ratio=0.9)


def test_corpus_es_ficticio_correos_solo_del_dominio_reservado(corpus_dir: Path) -> None:
    """Scenario implícito de 'Datos ficticios': ningún correo fuera de `acme.example`."""
    text = "\n".join(page.text for doc in _ground_truth(corpus_dir).values() for page in doc.pages)
    emails = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)
    assert emails, "se esperaba al menos un correo ficticio de contacto"
    assert all(email.endswith("@acme.example") for email in emails), emails


def test_generacion_con_la_misma_semilla_es_reproducible(corpus_dir: Path, tmp_path: Path) -> None:
    """Scenario: Generación reproducible. Misma semilla -> mismos 20 documentos y referencia.

    Anclado al manifiesto versionado (hallazgo 8): regenerar tiene que dar exactamente los
    sha256 que están commiteados, no solo dos corridas iguales entre sí. Depende de las
    versiones fijadas en uv.lock (reportlab, pymupdf, Pillow/libjpeg, numpy).
    """
    generated = generate_corpus(tmp_path / "a", seed=DEFAULT_SEED)

    assert generated == _manifest(corpus_dir)
    assert _ground_truth(tmp_path / "a") == _ground_truth(corpus_dir)


def test_otra_semilla_cambia_los_escaneos_pero_no_la_referencia(tmp_path: Path) -> None:
    doc = next(d for d in DOCUMENTS if d.category == "noisy_scan")
    data_a, ref_a = render_document(doc, np.random.default_rng([1, 0]))
    data_b, ref_b = render_document(doc, np.random.default_rng([2, 0]))

    assert data_a != data_b
    assert ref_a == ref_b
