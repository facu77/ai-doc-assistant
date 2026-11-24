"""`ResilientLLMClient`: timeout, reintentos, salida estructurada y log de uso, una sola vez
para todos los proveedores."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from typing import Literal

from pydantic import ValidationError

from ai_doc_assistant.llm.client import SchemaT
from ai_doc_assistant.llm.errors import (
    LLMError,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
)
from ai_doc_assistant.llm.models import LLMResponse, Usage
from ai_doc_assistant.llm.provider import LLMProvider, LLMRequest, StreamEnd, TextDelta
from ai_doc_assistant.llm.retry import RetryPolicy, is_transient

logger = logging.getLogger("ai_doc_assistant.llm")

Operation = Literal["complete", "stream", "structured"]

# Design: si la salida estructurada no valida, se reintenta *una* vez con el error como contexto.
STRUCTURED_ATTEMPTS = 2

_FIX_INSTRUCTION = (
    "\n\nTu respuesta anterior no cumplió el esquema JSON pedido. Errores: {errors}. "
    "Respondé solamente con un JSON válido para ese esquema."
)


def _as_llm_error(exc: Exception, provider: str) -> LLMError:
    """Cualquier excepción que escape de un adaptador se convierte en un error propio."""
    if isinstance(exc, LLMError):
        return exc
    if isinstance(exc, TimeoutError):
        return LLMTimeoutError(f"{provider} no respondió a tiempo")
    # Desconocida = no sabemos si es transitoria: no se reintenta.
    return LLMProviderError(f"error inesperado en el proveedor {provider}: {type(exc).__name__}")


def _summarize(error: ValidationError) -> str:
    """Resumen del error de validación sin los valores recibidos (pueden repetir el prompt)."""
    parts = []
    for item in error.errors(include_input=False, include_url=False, include_context=False):
        location = ".".join(str(part) for part in item["loc"]) or "(raíz)"
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts)


class ResilientLLMClient:
    """Implementa `LLMClient` sobre cualquier `LLMProvider`.

    `sleep` y `clock` se inyectan para que los tests de backoff corran con un reloj virtual.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        timeout_seconds: float,
        policy: RetryPolicy,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._provider = provider
        self._timeout = timeout_seconds
        self._policy = policy
        self._sleep = sleep
        self._clock = clock

    @property
    def provider(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._provider.model

    # ------------------------------------------------------------------ API pública

    async def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> LLMResponse:
        request = LLMRequest(prompt=prompt, system=system, max_tokens=max_tokens)
        return await self._generate(request, "complete")

    async def stream(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        request = LLMRequest(prompt=prompt, system=system, max_tokens=max_tokens)
        start = self._clock()
        attempt = 0
        while True:
            attempt += 1
            emitted = False
            usage: Usage | None = None
            try:
                events = self._provider.stream(request)
                try:
                    while True:
                        # Timeout entre fragmentos: un stream largo es válido, uno trabado no.
                        async with asyncio.timeout(self._timeout):
                            event = await anext(events, None)
                        if event is None:
                            break
                        if isinstance(event, TextDelta):
                            emitted = True
                            yield event.text
                        elif isinstance(event, StreamEnd):
                            usage = event.usage
                finally:
                    await events.aclose()
            except Exception as exc:
                error = _as_llm_error(exc, self._provider.name)
                # Después del primer token no se reintenta: el consumidor ya recibió texto y
                # un segundo intento podría generar otro distinto (texto duplicado o mezclado).
                if not emitted and await self._backoff(attempt, error):
                    continue
                self._fail(error, attempt, start, "stream")
                if error is exc:
                    raise
                raise error from exc
            self._log("stream", attempt, start, usage=usage)
            return

    async def complete_structured(
        self,
        prompt: str,
        schema: type[SchemaT],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> SchemaT:
        request = LLMRequest(
            prompt=prompt, system=system, max_tokens=max_tokens, output_schema=schema
        )
        summary = ""
        for _ in range(STRUCTURED_ATTEMPTS):
            response = await self._generate(request, "structured")
            try:
                return schema.model_validate_json(response.text)
            except ValidationError as exc:
                summary = _summarize(exc)
                fix = _FIX_INSTRUCTION.format(errors=summary)
                request = replace(request, prompt=prompt + fix)
        raise LLMValidationError(
            f"la respuesta no cumplió el esquema {schema.__name__} después de "
            f"{STRUCTURED_ATTEMPTS} intentos: {summary}",
            attempts=STRUCTURED_ATTEMPTS,
            schema_name=schema.__name__,
        )

    # ------------------------------------------------------------------ internos

    async def _generate(self, request: LLMRequest, operation: Operation) -> LLMResponse:
        start = self._clock()
        attempt = 0
        while True:
            attempt += 1
            try:
                # Red de seguridad: el SDK ya tiene su timeout HTTP, pero esto acota
                # también lo que pase fuera del cliente HTTP (DNS, un adaptador colgado).
                async with asyncio.timeout(self._timeout):
                    result = await self._provider.generate(request)
            except Exception as exc:
                error = _as_llm_error(exc, self._provider.name)
                if await self._backoff(attempt, error):
                    continue
                self._fail(error, attempt, start, operation)
                if error is exc:
                    raise
                raise error from exc
            latency_ms = self._log(operation, attempt, start, usage=result.usage)
            return LLMResponse(
                text=result.text,
                usage=result.usage,
                latency_ms=latency_ms,
                provider=self._provider.name,
                model=self._provider.model,
            )

    async def _backoff(self, attempt: int, error: LLMError) -> bool:
        """Espera y devuelve True si corresponde otro intento."""
        if attempt >= self._policy.max_attempts or not is_transient(error):
            return False
        await self._sleep(self._policy.delay_for(attempt, error))
        return True

    def _fail(self, error: LLMError, attempt: int, start: float, operation: Operation) -> None:
        error.attempts = attempt
        self._log(operation, attempt, start, usage=None, error=error)

    def _log(
        self,
        operation: Operation,
        attempts: int,
        start: float,
        *,
        usage: Usage | None,
        error: LLMError | None = None,
    ) -> float:
        """Un evento estructurado por llamada. Nunca incluye prompt ni respuesta."""
        latency_ms = max(0.0, (self._clock() - start) * 1000)
        event: dict[str, object] = {
            "provider": self._provider.name,
            "model": self._provider.model,
            "operation": operation,
            "input_tokens": usage.input_tokens if usage else None,
            "output_tokens": usage.output_tokens if usage else None,
            "latency_ms": round(latency_ms, 3),
            "attempts": attempts,
            "outcome": "error" if error else "ok",
        }
        if error is not None:
            event["error_type"] = type(error).__name__
        logger.info("llm_call", extra={"llm_call": event})
        return latency_ms
