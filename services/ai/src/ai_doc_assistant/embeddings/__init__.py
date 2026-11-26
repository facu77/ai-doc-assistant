"""Embeddings: textos → vectores con un modelo identificado y de dimensión fija.

Importar este paquete no carga sentence-transformers ni PyTorch: se cargan recién en
`LocalEmbedder.from_pretrained`.
"""

from ai_doc_assistant.embeddings.base import Embedder, Vector
from ai_doc_assistant.embeddings.errors import EmbeddingsConfigError, EmbeddingsError
from ai_doc_assistant.embeddings.factory import PROVIDERS, build_embedder
from ai_doc_assistant.embeddings.fake import FakeEmbedder
from ai_doc_assistant.embeddings.local import LocalEmbedder
from ai_doc_assistant.embeddings.settings import (
    DEFAULT_EMBEDDINGS_MODEL,
    EmbeddingsSettings,
    load_embeddings_settings,
)

__all__ = [
    "DEFAULT_EMBEDDINGS_MODEL",
    "PROVIDERS",
    "Embedder",
    "EmbeddingsConfigError",
    "EmbeddingsError",
    "EmbeddingsSettings",
    "FakeEmbedder",
    "LocalEmbedder",
    "Vector",
    "build_embedder",
    "load_embeddings_settings",
]
