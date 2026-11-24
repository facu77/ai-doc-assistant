"""`Embedder` local con sentence-transformers (por defecto `intfloat/multilingual-e5-small`).

Firmas confirmadas en el paquete instalado (sentence-transformers 6.3.0,
`sentence_transformers/sentence_transformer/model.py`):
- `SentenceTransformer(model_name_or_path, *, device=...)`.
- `encode(inputs, prompt_name=None, prompt=None, batch_size=32, show_progress_bar=None,
  ..., convert_to_numpy=True, convert_to_tensor=False, normalize_embeddings=False, ...)`
  → `np.ndarray` de forma `[n, dim]`. (El primer parámetro se llamaba `sentences`.)
- `get_embedding_dimension()`; `get_sentence_embedding_dimension()` quedó deprecado.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence

from ai_doc_assistant.embeddings.base import Vector

EncodeBatch = Callable[[list[str]], list[Vector]]

E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "


class LocalEmbedder:
    """Agrega el prefijo del rol, parte en lotes y corre el modelo fuera del event loop.

    `encode_batch` es una función síncrona que embebe un lote (en producción, un
    `SentenceTransformer.encode` con normalización). Inyectarla permite testear lotes,
    orden y prefijos sin cargar el modelo.
    """

    def __init__(
        self,
        *,
        model_id: str,
        dimension: int,
        encode_batch: EncodeBatch,
        batch_size: int,
        query_prefix: str = E5_QUERY_PREFIX,
        passage_prefix: str = E5_PASSAGE_PREFIX,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size tiene que ser al menos 1")
        self._model_id = model_id
        self._dimension = dimension
        self._encode_batch = encode_batch
        self._batch_size = batch_size
        self._query_prefix = query_prefix
        self._passage_prefix = passage_prefix

    @classmethod
    def from_pretrained(cls, model_id: str, *, batch_size: int) -> LocalEmbedder:
        """Carga el modelo en CPU (lo descarga la primera vez). Es bloqueante y lento:
        llamalo al arrancar, o con `asyncio.to_thread` desde código async."""
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_id, device="cpu")
        dimension = model.get_embedding_dimension()
        if dimension is None:
            raise ValueError(f"el modelo {model_id} no informa la dimensión de sus vectores")

        def encode_batch(texts: list[str]) -> list[Vector]:
            array = model.encode(
                texts,
                batch_size=len(texts),
                show_progress_bar=False,
                convert_to_numpy=True,
                convert_to_tensor=False,
                # Norma 1: así el coseno es el producto interno (más barato en el índice).
                normalize_embeddings=True,
            )
            vectors: list[Vector] = array.tolist()
            return vectors

        return cls(
            model_id=model_id,
            dimension=dimension,
            encode_batch=encode_batch,
            batch_size=batch_size,
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_queries(self, texts: Sequence[str]) -> list[Vector]:
        return await self._embed([self._query_prefix + t for t in texts])

    async def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return await self._embed([self._passage_prefix + t for t in texts])

    async def _embed(self, texts: list[str]) -> list[Vector]:
        vectors: list[Vector] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            # `encode` es síncrono y usa CPU a fondo: en un hilo aparte el event loop
            # sigue atendiendo otras requests. Un lote por vez acota la memoria.
            vectors.extend(await asyncio.to_thread(self._encode_batch, batch))
        return vectors
