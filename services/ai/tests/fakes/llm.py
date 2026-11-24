"""Dobles de prueba con comportamiento para el cliente LLM.

`ScriptedProvider` implementa el contrato `LLMProvider` siguiendo un guion: cada llamada
consume un paso (responder, fallar, colgarse). No es un mock: el cliente bajo prueba
tiene que reintentar, esperar y medir de verdad para que los tests pasen.

`FakeClock` reemplaza al reloj y al `sleep` del cliente: el backoff "espera" segundos
virtuales, así que los tests de reintentos corren en milisegundos.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Sequence
from dataclasses import dataclass, field

from ai_doc_assistant.llm import LLMError, LLMProviderError, ResilientLLMClient, RetryPolicy, Usage
from ai_doc_assistant.llm.provider import (
    LLMRequest,
    ProviderResult,
    StreamEnd,
    StreamEvent,
    TextDelta,
)


class FakeClock:
    """Reloj virtual: `sleep` avanza el tiempo sin esperar de verdad."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)  # cede el control como haría un sleep real


@dataclass(frozen=True)
class Reply:
    """Responde con `text`. En streaming lo entrega en `chunks` (si no, palabra por palabra)."""

    text: str = "respuesta de prueba"
    input_tokens: int = 7
    output_tokens: int = 3
    chunks: Sequence[str] | None = None
    latency: float = 0.0  # segundos virtuales que "tarda" el proveedor

    def stream_chunks(self) -> list[str]:
        if self.chunks is not None:
            return list(self.chunks)
        words = self.text.split(" ")
        return [w + " " for w in words[:-1]] + [words[-1]]


@dataclass(frozen=True)
class Fail:
    """Falla con `error`. En streaming, primero emite `after_chunks` y después falla."""

    error: Exception
    after_chunks: Sequence[str] = ()


@dataclass(frozen=True)
class Hang:
    """No responde nunca (hasta que alguien cancele la tarea)."""


Step = Reply | Fail | Hang


@dataclass
class ScriptedProvider:
    """Proveedor programable: cada intento consume el siguiente paso del guion."""

    steps: list[Step]
    clock: Callable[[], float] = field(default_factory=lambda: FakeClock())
    name: str = "guionado"
    model: str = "modelo-de-prueba"
    requests: list[LLMRequest] = field(default_factory=list)
    attempt_times: list[float] = field(default_factory=list)

    @property
    def attempts(self) -> int:
        return len(self.requests)

    def _next(self, request: LLMRequest) -> Step:
        self.requests.append(request)
        self.attempt_times.append(self.clock())
        if not self.steps:
            raise AssertionError("el guion del proveedor falso se agotó: el test pidió de más")
        return self.steps.pop(0)

    async def generate(self, request: LLMRequest) -> ProviderResult:
        step = self._next(request)
        if isinstance(step, Hang):
            await asyncio.sleep(3600)
            raise AssertionError("Hang terminó sin cancelación")
        if isinstance(step, Fail):
            raise step.error
        if step.latency and isinstance(self.clock, FakeClock):
            await self.clock.sleep(step.latency)
        return ProviderResult(
            text=step.text,
            usage=Usage(input_tokens=step.input_tokens, output_tokens=step.output_tokens),
        )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamEvent, None]:
        step = self._next(request)
        if isinstance(step, Hang):
            await asyncio.sleep(3600)
            raise AssertionError("Hang terminó sin cancelación")
        if isinstance(step, Fail):
            for chunk in step.after_chunks:
                yield TextDelta(text=chunk)
            raise step.error
        for chunk in step.stream_chunks():
            yield TextDelta(text=chunk)
        yield StreamEnd(
            usage=Usage(input_tokens=step.input_tokens, output_tokens=step.output_tokens)
        )


def make_client(
    provider: ScriptedProvider,
    *,
    max_attempts: int = 3,
    timeout_seconds: float = 5.0,
    clock: FakeClock | None = None,
    jitter: float = 0.5,
) -> ResilientLLMClient:
    """Cliente bajo prueba con reloj virtual y jitter fijo (reproducible)."""
    fake_clock = clock if clock is not None else FakeClock()
    return ResilientLLMClient(
        provider,
        timeout_seconds=timeout_seconds,
        policy=RetryPolicy(max_attempts=max_attempts, random=lambda: jitter),
        sleep=fake_clock.sleep,
        clock=fake_clock,
    )


def error_503() -> LLMError:
    return LLMProviderError("el proveedor respondió 503", status_code=503, transient=True)
