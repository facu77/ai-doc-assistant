"""Interfaz `Embedder`: separada del LLM porque son proveedores distintos."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

Vector = list[float]


class Embedder(Protocol):
    """Convierte textos en vectores de dimensión fija.

    La interfaz obliga a declarar el rol del texto: la familia e5 se entrenó con los
    prefijos `"query: "` y `"passage: "`, y sin ellos cae la calidad de recuperación.
    Devuelve un vector por texto, en el mismo orden de la entrada.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    async def embed_queries(self, texts: Sequence[str]) -> list[Vector]: ...

    async def embed_passages(self, texts: Sequence[str]) -> list[Vector]: ...
