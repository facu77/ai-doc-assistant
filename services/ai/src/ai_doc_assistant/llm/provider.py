"""Contrato interno entre el cliente resiliente y cada adaptador de proveedor.

Un adaptador hace **una** llamada al proveedor y traduce el resultado y los errores a
tipos propios. No reintenta, no mide latencia y no loguea: de eso se encarga
`ResilientLLMClient`, una sola vez para todos los proveedores. Agregar un proveedor es
escribir un archivo nuevo que cumpla este `Protocol` y registrarlo en la fábrica.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from ai_doc_assistant.llm.models import Usage


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system: str | None = None
    max_tokens: int = 1024
    # Si viene, el adaptador usa el modo de salida estructurada de su proveedor.
    output_schema: type[BaseModel] | None = None


@dataclass(frozen=True)
class ProviderResult:
    text: str
    usage: Usage


@dataclass(frozen=True)
class TextDelta:
    """Un fragmento de texto del streaming."""

    text: str


@dataclass(frozen=True)
class StreamEnd:
    """Fin del streaming, con el uso total de la llamada."""

    usage: Usage


StreamEvent = TextDelta | StreamEnd


class LLMProvider(Protocol):
    """Lo que tiene que cumplir un adaptador. Las excepciones que levanta son `LLMError`."""

    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def generate(self, request: LLMRequest) -> ProviderResult: ...

    def stream(self, request: LLMRequest) -> AsyncGenerator[StreamEvent, None]: ...

    async def aclose(self) -> None: ...
