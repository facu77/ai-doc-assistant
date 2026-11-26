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
    """Backoff exponencial con *full jitter*, acotado, y respeto de `Retry-After` con tope.

    `max_attempts` son los intentos totales. Sin `Retry-After`, la espera antes del intento
    `n + 1` es un valor al azar entre 0 y `min(max_delay, base_delay * 2**(n-1))`: el azar
    evita que muchos clientes que fallaron juntos reintenten en el mismo instante.

    Con `Retry-After`, se espera ese valor más un jitter de hasta `retry_after_jitter`
    segundos. Si el proveedor pide más de `max_retry_after`, no se espera: el consumidor
    recibe `LLMRateLimitError` enseguida, con el `retry_after` original.
    """

    max_attempts: int
    base_delay: float = 0.5
    max_delay: float = 8.0
    max_retry_after: float = 30.0
    retry_after_jitter: float = 0.5
    random: Callable[[], float] = field(default=_default_random)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts tiene que ser al menos 1")

    def should_retry(self, attempt: int, error: LLMError) -> bool:
        """¿Corresponde otro intento después de que falló el intento número `attempt`?"""
        if attempt >= self.max_attempts or not is_transient(error):
            return False
        retry_after = error.retry_after if isinstance(error, LLMRateLimitError) else None
        return retry_after is None or retry_after <= self.max_retry_after

    def delay_for(self, attempt: int, error: LLMError) -> float:
        """Segundos a esperar después del intento número `attempt` (1, 2, ...) fallido."""
        if isinstance(error, LLMRateLimitError) and error.retry_after is not None:
            # El proveedor dijo cuánto esperar: nunca menos, y con un poco de azar para
            # que los clientes que recibieron el mismo valor no vuelvan todos juntos.
            return error.retry_after + self.retry_after_jitter * self.random()
        ceiling = min(self.max_delay, self.base_delay * 2.0 ** (attempt - 1))
        return ceiling * self.random()


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
