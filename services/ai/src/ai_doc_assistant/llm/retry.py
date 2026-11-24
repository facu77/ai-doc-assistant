"""Política de reintentos: qué errores se reintentan y cuánto se espera entre intentos."""

from __future__ import annotations

import email.utils
import random as _random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from ai_doc_assistant.llm.errors import (
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


def is_transient(error: LLMError) -> bool:
    """Transitorio = otro intento idéntico puede salir bien (timeout, 429, 5xx, corte de red)."""
    if isinstance(error, LLMTimeoutError | LLMRateLimitError):
        return True
    return isinstance(error, LLMProviderError) and error.transient


def _default_random() -> float:
    # El jitter no es criptográfico: solo reparte los reintentos en el tiempo.
    return _random.random()  # noqa: S311


@dataclass(frozen=True)
class RetryPolicy:
    """Backoff exponencial con *full jitter*, acotado, y respeto de `Retry-After`.

    `max_attempts` son los intentos totales. La espera antes del intento `n + 1` es un
    valor al azar entre 0 y `min(max_delay, base_delay * 2**(n-1))`: el azar evita que
    muchos clientes que fallaron juntos reintenten todos en el mismo instante.
    """

    max_attempts: int
    base_delay: float = 0.5
    max_delay: float = 8.0
    random: Callable[[], float] = field(default=_default_random)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts tiene que ser al menos 1")

    def delay_for(self, attempt: int, error: LLMError) -> float:
        """Segundos a esperar después del intento número `attempt` (1, 2, ...) fallido."""
        ceiling = min(self.max_delay, self.base_delay * 2.0 ** (attempt - 1))
        delay = ceiling * self.random()
        if isinstance(error, LLMRateLimitError) and error.retry_after is not None:
            # El proveedor dijo cuánto esperar: nunca menos que eso.
            delay = max(delay, error.retry_after)
        return delay


def parse_retry_after(headers: Mapping[str, str], *, now: float | None = None) -> float | None:
    """Segundos de espera según `retry-after-ms`, `retry-after` (segundos) o una fecha HTTP."""
    millis = headers.get("retry-after-ms")
    if millis is not None:
        try:
            return max(0.0, float(millis) / 1000)
        except ValueError:
            pass
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    parsed = email.utils.parsedate_tz(value)
    if parsed is None:
        return None
    current = time.time() if now is None else now
    return max(0.0, float(email.utils.mktime_tz(parsed)) - current)
