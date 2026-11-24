"""`Embedder` fake: vectores deterministas derivados de un hash. Sin modelo, sin red.

No captura significado (dos paráfrasis quedan lejos): sirve para tests y CI de lo que
viene después del embedding (índice, búsqueda), no para medir calidad.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Sequence

from ai_doc_assistant.embeddings.base import Vector

FAKE_EMBEDDINGS_MODEL = "fake-hash-embedder"


class FakeEmbedder:
    def __init__(self, dimension: int = 384, model_id: str = FAKE_EMBEDDINGS_MODEL) -> None:
        self._dimension = dimension
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def _vector(self, text: str) -> Vector:
        # shake_256 da tantos bytes como pidamos: 4 por componente.
        raw = hashlib.shake_256(text.encode()).digest(4 * self._dimension)
        values = [(n / 2**31) - 1.0 for n in struct.unpack(f"<{self._dimension}I", raw)]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    async def embed_queries(self, texts: Sequence[str]) -> list[Vector]:
        return [self._vector(f"query: {t}") for t in texts]

    async def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return [self._vector(f"passage: {t}") for t in texts]
