"""Interfaz pública que usan los consumidores (RAG, agente, evaluación)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from ai_doc_assistant.llm.models import LLMResponse, SchemaT, StructuredResponse


class LLMClient(Protocol):
    """Acceso a un modelo de lenguaje sin saber qué proveedor hay detrás.

    Es un `Protocol` (tipado estructural): cualquier clase con estos métodos lo cumple,
    sin heredar nada. Los consumidores reciben un `LLMClient` inyectado.
    """

    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> LLMResponse:
        """Respuesta completa, con uso de tokens y latencia."""
        ...

    def stream(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        """Fragmentos de texto en orden; concatenados dan la respuesta completa."""
        ...

    async def complete_structured(
        self,
        prompt: str,
        schema: type[SchemaT],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> StructuredResponse[SchemaT]:
        """Respuesta validada contra `schema` (un esquema cerrado), con uso e intentos.

        Un esquema abierto es `LLMSchemaError` sin llamar al proveedor; una respuesta que no
        valida después de los intentos es `LLMValidationError`.
        """
        ...

    async def aclose(self) -> None:
        """Libera las conexiones del proveedor. Llamala al apagar el servicio."""
        ...
