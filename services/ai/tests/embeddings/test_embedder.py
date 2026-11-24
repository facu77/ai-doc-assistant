"""Requirements de `embeddings` testeados sin el modelo real (rápidos, offline)."""

from __future__ import annotations

import asyncio
import math

import pytest
from ai_doc_assistant.embeddings import (
    DEFAULT_EMBEDDINGS_MODEL,
    Embedder,
    EmbeddingsConfigError,
    FakeEmbedder,
    LocalEmbedder,
    build_embedder,
    load_embeddings_settings,
)

from tests.fakes.embeddings import RecordingEncoder


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def _local(encoder: RecordingEncoder, batch_size: int = 64) -> LocalEmbedder:
    return LocalEmbedder(
        model_id="modelo-local-de-prueba",
        dimension=encoder.dimension,
        encode_batch=encoder,
        batch_size=batch_size,
    )


# --- Requirement: Modelo identificado y de dimensión fija


def test_modelo_por_defecto(isolated_env: pytest.MonkeyPatch) -> None:
    """Scenario: Modelo por defecto (configuración; la dimensión real se mide en integración)."""
    isolated_env.setenv("EMBEDDINGS_PROVIDER", "local")
    settings = load_embeddings_settings()
    assert settings.model == "intfloat/multilingual-e5-small"
    assert DEFAULT_EMBEDDINGS_MODEL == "intfloat/multilingual-e5-small"
    assert settings.batch_size == 64


def test_proveedor_desconocido(isolated_env: pytest.MonkeyPatch) -> None:
    """Scenario: Proveedor desconocido."""
    isolated_env.setenv("EMBEDDINGS_PROVIDER", "desconocido")
    with pytest.raises(EmbeddingsConfigError) as excinfo:
        build_embedder(load_embeddings_settings())
    for valido in ("fake", "local"):
        assert valido in str(excinfo.value)


def test_sin_proveedor_falla(isolated_env: pytest.MonkeyPatch) -> None:
    with pytest.raises(EmbeddingsConfigError, match="EMBEDDINGS_PROVIDER"):
        build_embedder(load_embeddings_settings())


def test_batch_size_invalido(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("EMBEDDINGS_PROVIDER", "fake")
    isolated_env.setenv("EMBEDDINGS_BATCH_SIZE", "0")
    with pytest.raises(EmbeddingsConfigError, match="EMBEDDINGS_BATCH_SIZE"):
        load_embeddings_settings()


def test_fake_expone_modelo_y_dimension(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("EMBEDDINGS_PROVIDER", "fake")
    embedder: Embedder = build_embedder(load_embeddings_settings())
    assert embedder.model_id
    assert embedder.dimension == 384


# --- Requirement: Rol del texto: consulta o pasaje


async def test_consulta_y_pasaje_aplican_el_prefijo_de_e5() -> None:
    """Scenario: Consulta y pasaje con el mismo texto (formato que exige el modelo)."""
    encoder = RecordingEncoder()
    embedder = _local(encoder)
    (consulta,) = await embedder.embed_queries(["licencia anual"])
    (pasaje,) = await embedder.embed_passages(["licencia anual"])
    assert encoder.batches == [["query: licencia anual"], ["passage: licencia anual"]]
    assert len(consulta) == len(pasaje) == embedder.dimension
    assert consulta != pasaje


async def test_consulta_y_pasaje_con_el_fake() -> None:
    """Scenario: Consulta y pasaje con el mismo texto (embedder fake)."""
    embedder = FakeEmbedder()
    (consulta,) = await embedder.embed_queries(["licencia anual"])
    (pasaje,) = await embedder.embed_passages(["licencia anual"])
    assert len(consulta) == len(pasaje) == embedder.dimension
    assert consulta != pasaje


# --- Requirement: Determinismo


async def test_fake_determinista_y_normalizado() -> None:
    """Scenario: Dos corridas (embedder fake, incluso entre instancias distintas)."""
    textos = [f"texto ficticio número {i}" for i in range(10)]
    primera = await FakeEmbedder().embed_passages(textos)
    segunda = await FakeEmbedder().embed_passages(textos)
    for a, b in zip(primera, segunda, strict=True):
        assert _cos(a, b) >= 0.9999
        assert math.sqrt(sum(x * x for x in a)) == pytest.approx(1.0)


# --- Requirement: Procesamiento en lotes


async def test_lote_grande() -> None:
    """Scenario: Lote grande (250 textos, lote de 100 → 3 lotes, mismo orden, dimensión 384)."""
    encoder = RecordingEncoder(dimension=384)
    embedder = _local(encoder, batch_size=100)
    textos = [f"pasaje ficticio {i}" for i in range(250)]
    vectores = await embedder.embed_passages(textos)
    assert len(vectores) == 250
    assert all(len(v) == 384 for v in vectores)
    assert [len(lote) for lote in encoder.batches] == [100, 100, 50]
    for texto, vector in zip(textos, vectores, strict=True):
        assert vector == encoder.vector_for(f"passage: {texto}")


async def test_lista_vacia_no_llama_al_modelo() -> None:
    encoder = RecordingEncoder()
    assert await _local(encoder).embed_queries([]) == []
    assert encoder.batches == []


async def test_el_modelo_corre_fuera_del_event_loop() -> None:
    """Design: `encode` es CPU intensivo y síncrono: se llama con `asyncio.to_thread`."""
    encoder = RecordingEncoder(block_seconds=0.3)
    embedder = _local(encoder, batch_size=10)
    ticks = 0

    async def latido() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    tarea = asyncio.create_task(latido())
    await embedder.embed_passages(["uno", "dos"])
    tarea.cancel()
    # Si encode bloqueara el loop, el latido no avanzaría durante los 0,3 s.
    assert ticks >= 10
