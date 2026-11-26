"""Codificador falso para `LocalEmbedder`: registra cada lote y genera vectores rastreables."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


@dataclass
class RecordingEncoder:
    """Reemplaza a `SentenceTransformer.encode` para un lote.

    Cada vector codifica el texto que lo generó (su largo y un hash simple), así un test
    puede verificar que el orden de salida coincide con el de entrada.
    """

    dimension: int = 384
    block_seconds: float = 0.0  # simula trabajo de CPU bloqueante
    batches: list[list[str]] = field(default_factory=list)

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        if self.block_seconds:
            time.sleep(self.block_seconds)  # bloqueante a propósito
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        seed = sum(ord(c) * (i + 1) for i, c in enumerate(text))
        raw = [math.sin(seed + i) for i in range(self.dimension)]
        norm = math.sqrt(sum(x * x for x in raw))
        return [x / norm for x in raw]

    def vector_for(self, text: str) -> list[float]:
        return self._vector(text)


@dataclass
class FakeSentenceTransformer:
    """Imita la parte de `SentenceTransformer` que usa `LocalEmbedder.from_pretrained`."""

    model_id: str
    dimension: int = 384
    calls: list[tuple[list[str], dict[str, object]]] = field(default_factory=list)

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, inputs: list[str], **kwargs: object) -> FakeArray:
        self.calls.append((list(inputs), dict(kwargs)))
        encoder = RecordingEncoder(dimension=self.dimension)
        return FakeArray([encoder.vector_for(t) for t in inputs])


@dataclass
class FakeArray:
    """Lo único que se usa del `np.ndarray` que devuelve `encode`."""

    rows: list[list[float]]

    def tolist(self) -> list[list[float]]:
        return self.rows
