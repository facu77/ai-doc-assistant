"""Tests con el modelo real `intfloat/multilingual-e5-small` (descarga ~470 MB la primera vez).

Correr con: `make test-integration` (o `uv run pytest -m integration`).
"""

from __future__ import annotations

import math

import pytest

from ai_doc_assistant.embeddings import (
    EmbeddingsSettings,
    LocalEmbedder,
    build_embedder,
)

pytestmark = pytest.mark.integration


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


@pytest.fixture(scope="module")
def e5() -> LocalEmbedder:
    embedder = build_embedder(EmbeddingsSettings(provider="local", batch_size=100))
    assert isinstance(embedder, LocalEmbedder)
    return embedder


def test_modelo_por_defecto_informa_dimension_384(e5: LocalEmbedder) -> None:
    """Scenario: Modelo por defecto."""
    assert e5.model_id == "intfloat/multilingual-e5-small"
    assert e5.dimension == 384


async def test_consulta_y_pasaje_con_el_mismo_texto(e5: LocalEmbedder) -> None:
    """Scenario: Consulta y pasaje con el mismo texto."""
    (consulta,) = await e5.embed_queries(["licencia anual"])
    (pasaje,) = await e5.embed_passages(["licencia anual"])
    assert len(consulta) == len(pasaje) == 384
    assert consulta != pasaje


async def test_dos_corridas(e5: LocalEmbedder) -> None:
    """Scenario: Dos corridas (coseno >= 0,9999 entre pares correspondientes)."""
    textos = [
        "Procedimiento para solicitar la licencia anual",
        "Política de trabajo remoto para el equipo de soporte",
        "Reintegro de gastos de movilidad",
        "Horario de atención de la mesa de ayuda",
        "Cómo cargar horas extra en el sistema",
        "Beneficio de guardería para hijos menores",
        "Capacitaciones obligatorias del primer año",
        "Pasos para dar de alta un proveedor",
        "Código de conducta y canal de denuncias",
        "Vacaciones de invierno: cronograma 2026",
    ]
    primera = await e5.embed_passages(textos)
    segunda = await e5.embed_passages(textos)
    for a, b in zip(primera, segunda, strict=True):
        assert _cos(a, b) >= 0.9999


async def test_vectores_normalizados(e5: LocalEmbedder) -> None:
    """Design: vectores de norma 1, así que coseno = producto interno."""
    vectores = await e5.embed_queries(["¿cómo pido vacaciones?", "otra consulta"])
    for v in vectores:
        assert math.sqrt(sum(x * x for x in v)) == pytest.approx(1.0, abs=1e-4)


async def test_lote_grande_con_el_modelo_real(e5: LocalEmbedder) -> None:
    """Scenario: Lote grande (250 textos con lote de 100)."""
    textos = [f"Pasaje ficticio número {i} sobre políticas internas" for i in range(250)]
    vectores = await e5.embed_passages(textos)
    assert len(vectores) == 250
    assert all(len(v) == 384 for v in vectores)
    # Mismo orden: el vector i coincide con embeber el texto i solo.
    (vector_137,) = await e5.embed_passages([textos[137]])
    assert _cos(vectores[137], vector_137) >= 0.9999


async def test_parafrasis_frente_a_texto_no_relacionado(e5: LocalEmbedder) -> None:
    """Scenario: Paráfrasis frente a texto no relacionado."""
    (consulta,) = await e5.embed_queries(["¿cómo pido vacaciones?"])
    licencia, receta = await e5.embed_passages(
        ["Procedimiento para solicitar la licencia anual", "Receta de pan casero"]
    )
    assert _cos(consulta, licencia) > _cos(consulta, receta)
