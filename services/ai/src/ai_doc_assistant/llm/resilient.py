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

from ai_doc_assistant.llm.errors import (
    LLMError,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
)
from ai_doc_assistant.llm.models import LLMResponse, SchemaT, StructuredResponse, Usage
from ai_doc_assistant.llm.provider import (
    LLMProvider,
    LLMRequest,
    ProviderResult,
    StreamEnd,
    TextDelta,
)
from ai_doc_assistant.llm.retry import RetryPolicy
from ai_doc_assistant.llm.schema import ensure_closed_schema

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
        start = self._clock()
        try:
            result, attempts = await self._generate(request)
        except LLMError as error:
            self._log("complete", error.attempts, start, usage=None, error=error)
            raise
        latency_ms = self._log("complete", attempts, start, usage=result.usage)
        return LLMResponse(
            text=result.text,
            usage=result.usage,
            latency_ms=latency_ms,
            provider=self._provider.name,
            model=self._provider.model,
        )

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
                error.attempts = attempt
                self._log("stream", attempt, start, usage=None, error=error)
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
    ) -> StructuredResponse[SchemaT]:
        # Antes de gastar una request: un esquema abierto nunca va a validar como se espera.
        ensure_closed_schema(schema)
        request = LLMRequest(
            prompt=prompt, system=system, max_tokens=max_tokens, output_schema=schema
        )
        start = self._clock()
        attempts = 0
        input_tokens = output_tokens = 0
        summary = ""
        for _ in range(STRUCTURED_ATTEMPTS):
            try:
                result, used = await self._generate(request)
            except LLMError as error:
                error.attempts += attempts
                usage = Usage(input_tokens=input_tokens, output_tokens=output_tokens)
                self._log("structured", error.attempts, start, usage=usage, error=error)
                raise
            attempts += used
            input_tokens += result.usage.input_tokens
            output_tokens += result.usage.output_tokens
            try:
                value = schema.model_validate_json(result.text)
            except ValidationError as exc:
                summary = _summarize(exc)
                fix = _FIX_INSTRUCTION.format(errors=summary)
                request = replace(request, prompt=prompt + fix)
                continue
            usage = Usage(input_tokens=input_tokens, output_tokens=output_tokens)
            latency_ms = self._log("structured", attempts, start, usage=usage)
            return StructuredResponse[SchemaT](
                value=value,
                usage=usage,
                latency_ms=latency_ms,
                attempts=attempts,
                provider=self._provider.name,
                model=self._provider.model,
            )
        invalid = LLMValidationError(
            f"la respuesta no cumplió el esquema {schema.__name__} después de "
            f"{attempts} intentos: {summary}",
            attempts=attempts,
            schema_name=schema.__name__,
        )
        usage = Usage(input_tokens=input_tokens, output_tokens=output_tokens)
        self._log("structured", attempts, start, usage=usage, error=invalid)
        raise invalid

    async def aclose(self) -> None:
        await self._provider.aclose()

    # ------------------------------------------------------------------ internos

    async def _generate(self, request: LLMRequest) -> tuple[ProviderResult, int]:
        """Una llamada con timeout y reintentos. Devuelve el resultado y los intentos usados.

        Si se rinde, levanta un `LLMError` con `attempts` completo. No loguea: eso lo hace
        la operación pública, una vez por llamada del consumidor.
        """
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
                error.attempts = attempt
                if error is exc:
                    raise
                raise error from exc
            return result, attempt

    async def _backoff(self, attempt: int, error: LLMError) -> bool:
        """Espera y devuelve True si corresponde otro intento."""
        if not self._policy.should_retry(attempt, error):
            return False
        await self._sleep(self._policy.delay_for(attempt, error))
        return True

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
