"""Errores propios del cliente LLM.

Los consumidores solo ven estas clases: las excepciones de los SDKs quedan encadenadas
como `__cause__` (`raise ... from exc`) para depurar, pero nunca salen del módulo.
Ningún mensaje incluye el prompt ni la respuesta.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base de todos los errores del cliente LLM.

    `attempts` lo completa el cliente al rendirse: cuántos intentos hizo en total.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.attempts = 0


class LLMConfigError(LLMError):
    """Configuración inválida: se levanta al arrancar, no en la primera llamada."""


class LLMTimeoutError(LLMError):
    """El proveedor no respondió dentro de `LLM_TIMEOUT_SECONDS`. Es transitorio."""


class LLMRateLimitError(LLMError):
    """El proveedor respondió 429. `retry_after` son los segundos que pidió esperar."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMProviderError(LLMError):
    """Error del proveedor (HTTP u otro).

    `transient` distingue un 5xx o un corte de conexión (vale la pena reintentar) de un
    400/401/403/404 (reintentar daría el mismo resultado).
    """

    def __init__(
        self, message: str, *, status_code: int | None = None, transient: bool = False
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.transient = transient


class LLMValidationError(LLMError):
    """La salida estructurada no cumplió el esquema después de todos los intentos."""

    def __init__(self, message: str, *, attempts: int, schema_name: str) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.schema_name = schema_name
