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
from ai_doc_assistant.embeddings import local as local_module
from ai_doc_assistant.embeddings.local import e5_prefixes
from tests.fakes.embeddings import FakeSentenceTransformer, RecordingEncoder


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def _local(encoder: RecordingEncoder, batch_size: int = 64) -> LocalEmbedder:
    return LocalEmbedder(
        # Id de e5: el constructor deriva los prefijos del id (como `from_pretrained`).
        model_id="intfloat/multilingual-e5-small",
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


# --- La fábrica conecta EMBEDDINGS_* de punta a punta (sin cargar el modelo real)


@pytest.fixture
def modelos_cargados(isolated_env: pytest.MonkeyPatch) -> list[FakeSentenceTransformer]:
    cargados: list[FakeSentenceTransformer] = []

    def cargar(model_id: str) -> FakeSentenceTransformer:
        modelo = FakeSentenceTransformer(model_id=model_id)
        cargados.append(modelo)
        return modelo

    isolated_env.setattr(local_module, "load_sentence_transformer", cargar)
    return cargados


async def test_fabrica_aplica_batch_size_del_entorno(
    isolated_env: pytest.MonkeyPatch, modelos_cargados: list[FakeSentenceTransformer]
) -> None:
    """Scenario: Lote grande (EMBEDDINGS_BATCH_SIZE llega desde el entorno)."""
    isolated_env.setenv("EMBEDDINGS_PROVIDER", "local")
    isolated_env.setenv("EMBEDDINGS_BATCH_SIZE", "7")
    embedder = build_embedder(load_embeddings_settings())
    vectores = await embedder.embed_passages([f"texto {i}" for i in range(20)])
    assert len(vectores) == 20
    (modelo,) = modelos_cargados
    assert modelo.model_id == "intfloat/multilingual-e5-small"
    assert [len(textos) for textos, _ in modelo.calls] == [7, 7, 6]
    for _, kwargs in modelo.calls:
        assert kwargs["normalize_embeddings"] is True
    assert embedder.dimension == 384


@pytest.mark.parametrize(
    ("model_id", "prefijo_consulta", "prefijo_pasaje"),
    [
        ("intfloat/multilingual-e5-small", "query: ", "passage: "),
        ("intfloat/e5-base-v2", "query: ", "passage: "),
        ("sentence-transformers/all-MiniLM-L6-v2", "", ""),
    ],
)
async def test_prefijos_solo_para_la_familia_e5(
    isolated_env: pytest.MonkeyPatch,
    modelos_cargados: list[FakeSentenceTransformer],
    model_id: str,
    prefijo_consulta: str,
    prefijo_pasaje: str,
) -> None:
    """Scenario: Modelo fuera de la familia e5 (no recibe los prefijos de e5)."""
    isolated_env.setenv("EMBEDDINGS_PROVIDER", "local")
    isolated_env.setenv("EMBEDDINGS_MODEL", model_id)
    embedder = build_embedder(load_embeddings_settings())
    await embedder.embed_queries(["licencia anual"])
    await embedder.embed_passages(["licencia anual"])
    (modelo,) = modelos_cargados
    assert [textos for textos, _ in modelo.calls] == [
        [f"{prefijo_consulta}licencia anual"],
        [f"{prefijo_pasaje}licencia anual"],
    ]


@pytest.mark.parametrize(
    "model_id", ["intfloat/multilingual-e5-large-instruct", "intfloat/e5-mistral-7b-instruct"]
)
def test_modelo_e5_instruct_se_rechaza(
    isolated_env: pytest.MonkeyPatch,
    modelos_cargados: list[FakeSentenceTransformer],
    model_id: str,
) -> None:
    """Scenario: Modelo e5 instruct (formato de prompt no soportado: error de configuración)."""
    isolated_env.setenv("EMBEDDINGS_PROVIDER", "local")
    isolated_env.setenv("EMBEDDINGS_MODEL", model_id)
    with pytest.raises(EmbeddingsConfigError, match="instruct"):
        build_embedder(load_embeddings_settings())
    assert modelos_cargados == [], "se rechaza antes de cargar (o descargar) el modelo"


def test_constructor_deriva_los_prefijos_del_model_id() -> None:
    """Los prefijos por defecto del constructor salen de `e5_prefixes(model_id)`."""
    encoder = RecordingEncoder()
    otro = LocalEmbedder(
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        dimension=encoder.dimension,
        encode_batch=encoder,
        batch_size=8,
    )
    assert e5_prefixes(otro.model_id) == ("", "")
    with pytest.raises(EmbeddingsConfigError):
        LocalEmbedder(
            model_id="intfloat/multilingual-e5-large-instruct",
            dimension=encoder.dimension,
            encode_batch=encoder,
            batch_size=8,
        )


async def test_constructor_sin_prefijo_para_modelos_no_e5() -> None:
    encoder = RecordingEncoder()
    embedder = LocalEmbedder(
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        dimension=encoder.dimension,
        encode_batch=encoder,
        batch_size=8,
    )
    await embedder.embed_queries(["licencia anual"])
    assert encoder.batches == [["licencia anual"]]
