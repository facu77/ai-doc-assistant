"""Modelos de salida del cliente LLM (Pydantic en el borde)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

# Para las firmas de `complete_structured` (el TypeVar se liga por método).
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class Usage(BaseModel):
    """Tokens consumidos por una llamada."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class LLMResponse(BaseModel):
    """Respuesta completa de un completado.

    `latency_ms` mide lo que espera el consumidor: incluye reintentos y backoff.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    usage: Usage
    latency_ms: float = Field(ge=0)
    provider: str
    model: str


class StructuredResponse[T: BaseModel](BaseModel):
    """Salida estructurada ya validada, con los metadatos de toda la operación.

    `usage` suma todas las rondas (también la que no validó), `attempts` cuenta todas las
    requests al proveedor (reintentos transitorios incluidos) y `latency_ms` es el total.
    """

    model_config = ConfigDict(frozen=True)

    value: T
    usage: Usage
    latency_ms: float = Field(ge=0)
    attempts: int = Field(ge=1)
    provider: str
    model: str
