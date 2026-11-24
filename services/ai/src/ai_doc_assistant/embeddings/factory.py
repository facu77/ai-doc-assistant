"""Fábrica de `Embedder` a partir de `EmbeddingsSettings`."""

from __future__ import annotations

from collections.abc import Callable

from ai_doc_assistant.embeddings.base import Embedder
from ai_doc_assistant.embeddings.errors import EmbeddingsConfigError
from ai_doc_assistant.embeddings.fake import FakeEmbedder
from ai_doc_assistant.embeddings.local import LocalEmbedder
from ai_doc_assistant.embeddings.settings import EmbeddingsSettings, load_embeddings_settings


def _local(settings: EmbeddingsSettings) -> Embedder:
    return LocalEmbedder.from_pretrained(settings.model, batch_size=settings.batch_size)


def _fake(settings: EmbeddingsSettings) -> Embedder:
    return FakeEmbedder()


PROVIDERS: dict[str, Callable[[EmbeddingsSettings], Embedder]] = {
    "fake": _fake,
    "local": _local,
}


def build_embedder(settings: EmbeddingsSettings | None = None) -> Embedder:
    """Arma el embedder configurado. Con `local` carga el modelo: es bloqueante y tarda
    unos segundos, así que va al arrancar (o en `asyncio.to_thread`)."""
    resolved = settings if settings is not None else load_embeddings_settings()
    valid = ", ".join(sorted(PROVIDERS))
    if resolved.provider is None:
        raise EmbeddingsConfigError(
            f"falta la variable de entorno EMBEDDINGS_PROVIDER (valores válidos: {valid})"
        )
    builder = PROVIDERS.get(resolved.provider)
    if builder is None:
        raise EmbeddingsConfigError(
            f"EMBEDDINGS_PROVIDER={resolved.provider!r} no es válido (valores válidos: {valid})"
        )
    return builder(resolved)
