"""Requirement: Reintentos acotados ante errores transitorios."""

from __future__ import annotations

import pytest
from ai_doc_assistant.llm import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    RetryPolicy,
)

from tests.fakes.llm import Fail, FakeClock, Reply, ScriptedProvider, error_503, make_client


async def test_error_transitorio_que_se_recupera() -> None:
    """Scenario: Error transitorio que se recupera."""
    provider = ScriptedProvider([Fail(error_503()), Fail(error_503()), Reply(text="por fin")])
    respuesta = await make_client(provider, max_attempts=3).complete("prompt")
    assert respuesta.text == "por fin"
    assert provider.attempts == 3


async def test_reintentos_agotados() -> None:
    """Scenario: Reintentos agotados."""
    provider = ScriptedProvider([Fail(error_503()) for _ in range(3)])
    with pytest.raises(LLMProviderError) as excinfo:
        await make_client(provider, max_attempts=3).complete("prompt")
    assert provider.attempts == 3
    assert excinfo.value.attempts == 3
    assert excinfo.value.status_code == 503


@pytest.mark.parametrize("codigo", [400, 401])
async def test_error_no_reintentable(codigo: int) -> None:
    """Scenario: Error no reintentable."""
    error = LLMProviderError(f"el proveedor respondió {codigo}", status_code=codigo)
    provider = ScriptedProvider([Fail(error), Reply()])
    clock = FakeClock()
    with pytest.raises(LLMProviderError) as excinfo:
        await make_client(provider, max_attempts=3, clock=clock).complete("prompt")
    assert provider.attempts == 1
    assert excinfo.value.attempts == 1
    assert excinfo.value.status_code == codigo
    assert clock.sleeps == [], "no hay backoff si no se reintenta"


async def test_respeta_retry_after() -> None:
    """Scenario: Respeto de Retry-After."""
    clock = FakeClock()
    rate_limit = LLMRateLimitError("429 del proveedor", retry_after=2.0)
    provider = ScriptedProvider([Fail(rate_limit), Reply()], clock=clock)
    # jitter=0 haría que el backoff propio sea ~0 s: lo que manda es el Retry-After.
    await make_client(provider, clock=clock, jitter=0.0).complete("prompt")
    assert provider.attempts == 2
    assert provider.attempt_times[1] - provider.attempt_times[0] >= 2.0


async def test_timeout_es_transitorio() -> None:
    """Requirement: reintentar timeout, límite de tasa y error del servidor."""
    provider = ScriptedProvider([Fail(LLMTimeoutError("timeout")), Reply(text="ok")])
    respuesta = await make_client(provider).complete("prompt")
    assert respuesta.text == "ok"
    assert provider.attempts == 2


async def test_excepcion_desconocida_no_se_reintenta() -> None:
    """Un error que no sabemos clasificar no es transitorio: se falla rápido."""
    provider = ScriptedProvider([Fail(RuntimeError("bug del adaptador")), Reply()])
    with pytest.raises(LLMProviderError):
        await make_client(provider).complete("prompt")
    assert provider.attempts == 1


def test_backoff_exponencial_con_tope() -> None:
    """Design: backoff exponencial con base de 0,5 s y tope de 8 s."""
    policy = RetryPolicy(max_attempts=10, random=lambda: 1.0)
    error = LLMProviderError("503", status_code=503, transient=True)
    delays = [policy.delay_for(intento, error) for intento in range(1, 8)]
    assert delays == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0, 8.0]


def test_jitter_reparte_la_espera() -> None:
    """Design: jitter. Con azar 0,25 la espera es una fracción del techo exponencial."""
    policy = RetryPolicy(max_attempts=5, random=lambda: 0.25)
    error = LLMProviderError("503", status_code=503, transient=True)
    assert policy.delay_for(3, error) == pytest.approx(0.5)  # 0,25 * 2,0


def test_retry_after_pisa_al_backoff_si_es_mayor() -> None:
    policy = RetryPolicy(max_attempts=5, random=lambda: 1.0)
    assert policy.delay_for(1, LLMRateLimitError("429", retry_after=2.0)) == 2.0
    assert policy.delay_for(5, LLMRateLimitError("429", retry_after=2.0)) == 8.0


async def test_backoff_real_entre_intentos() -> None:
    """Los intentos quedan separados por el backoff (reloj virtual)."""
    clock = FakeClock()
    provider = ScriptedProvider([Fail(error_503()), Fail(error_503()), Reply()], clock=clock)
    await make_client(provider, clock=clock, jitter=1.0).complete("prompt")
    assert clock.sleeps == [0.5, 1.0]
    assert provider.attempt_times == [0.0, 0.5, 1.5]
