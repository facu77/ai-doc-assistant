"""Requirement: Timeout por llamada."""

from __future__ import annotations

import asyncio
import time

import pytest

from ai_doc_assistant.llm import LLMTimeoutError, ResilientLLMClient, RetryPolicy
from tests.fakes.llm import Hang, Reply, ScriptedProvider

# Guardia: si el timeout bajo prueba no funcionara, el test fallaría en 5 s en vez de
# colgarse una hora en el `Hang` del proveedor falso.
GUARDIA = 5.0


def _client(provider: ScriptedProvider, *, timeout: float, attempts: int) -> ResilientLLMClient:
    # Reloj y sleep reales: lo que se mide acá es el timeout de verdad.
    return ResilientLLMClient(
        provider, timeout_seconds=timeout, policy=RetryPolicy(max_attempts=attempts)
    )


async def test_proveedor_que_no_responde() -> None:
    """Scenario: Proveedor que no responde (LLM_TIMEOUT_SECONDS=1, sin reintentos)."""
    provider = ScriptedProvider([Hang()])
    inicio = time.perf_counter()
    with pytest.raises(LLMTimeoutError) as excinfo:
        await asyncio.wait_for(
            _client(provider, timeout=1.0, attempts=1).complete("prompt"), GUARDIA
        )
    transcurrido = time.perf_counter() - inicio
    assert transcurrido < 1.5
    assert transcurrido >= 0.9, "tiene que esperar el timeout, no fallar antes"
    assert excinfo.value.attempts == 1


async def test_timeout_en_streaming_antes_del_primer_token() -> None:
    """Scenario: Proveedor que no responde (en streaming)."""
    provider = ScriptedProvider([Hang()])
    inicio = time.perf_counter()

    async def consumir() -> None:
        async for _ in _client(provider, timeout=0.2, attempts=1).stream("prompt"):
            pass

    with pytest.raises(LLMTimeoutError):
        await asyncio.wait_for(consumir(), GUARDIA)
    assert time.perf_counter() - inicio < 0.7


async def test_timeout_se_reintenta_si_hay_intentos() -> None:
    """Requirement: el timeout es transitorio y entra en la política de reintentos."""
    provider = ScriptedProvider([Hang(), Reply(text="segundo intento")])
    client = ResilientLLMClient(
        provider,
        timeout_seconds=0.1,
        policy=RetryPolicy(max_attempts=2, random=lambda: 0.0),
    )
    respuesta = await asyncio.wait_for(client.complete("prompt"), GUARDIA)
    assert respuesta.text == "segundo intento"
    assert provider.attempts == 2
