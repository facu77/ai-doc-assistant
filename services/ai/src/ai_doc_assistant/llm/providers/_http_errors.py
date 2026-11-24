"""Clasificación común de errores HTTP para los adaptadores (no depende de ningún SDK)."""

from __future__ import annotations

from collections.abc import Mapping

from ai_doc_assistant.llm.errors import (
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from ai_doc_assistant.llm.retry import parse_retry_after


def error_from_status(provider: str, status_code: int, headers: Mapping[str, str]) -> LLMError:
    """429 → rate limit; 408 → timeout; 5xx → transitorio; el resto de 4xx → permanente."""
    if status_code == 429:
        return LLMRateLimitError(
            f"{provider} respondió 429 (límite de tasa)", retry_after=parse_retry_after(headers)
        )
    if status_code == 408:
        return LLMTimeoutError(f"{provider} respondió 408 (timeout del lado del servidor)")
    return LLMProviderError(
        f"{provider} respondió {status_code}",
        status_code=status_code,
        transient=status_code >= 500,
    )


def connection_error(provider: str) -> LLMError:
    # Un corte de conexión no es un rechazo del proveedor: vale la pena otro intento.
    return LLMProviderError(f"no se pudo conectar con {provider}", transient=True)


def timeout_error(provider: str) -> LLMError:
    return LLMTimeoutError(f"{provider} no respondió a tiempo")


def unexpected_error(provider: str, exc: Exception) -> LLMError:
    return LLMProviderError(f"error del SDK de {provider}: {type(exc).__name__}")
