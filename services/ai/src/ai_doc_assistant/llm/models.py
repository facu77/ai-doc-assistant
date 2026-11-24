"""Modelos de salida del cliente LLM (Pydantic en el borde)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
