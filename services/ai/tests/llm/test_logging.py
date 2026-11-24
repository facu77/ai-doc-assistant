"""Requirement: Registro de uso sin contenido sensible."""

from __future__ import annotations

import logging

import pytest
from pydantic import BaseModel

from ai_doc_assistant.llm import LLMProviderError, LLMSettings, build_llm_client
from tests.fakes.llm import Fail, FakeClock, Reply, ScriptedProvider, error_503, make_client

SECRETO = "secreto-de-prueba"
CAMPOS_DE_USO = {
    "provider",
    "model",
    "operation",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "attempts",
    "outcome",
}


class Respuesta(BaseModel):
    respuesta: str


def _llm_calls(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    eventos: list[dict[str, object]] = []
    for record in caplog.records:
        evento = getattr(record, "llm_call", None)
        if isinstance(evento, dict):
            eventos.append(evento)
    return eventos


def _assert_sin_secreto(caplog: pytest.LogCaptureFixture) -> None:
    for record in caplog.records:
        assert SECRETO not in record.getMessage()
        assert SECRETO not in str(vars(record))
    assert SECRETO not in caplog.text


async def test_log_de_una_llamada(caplog: pytest.LogCaptureFixture) -> None:
    """Scenario: Log de una llamada."""
    caplog.set_level(logging.DEBUG)
    clock = FakeClock()
    provider = ScriptedProvider(
        [Fail(error_503()), Reply(text=f"eco {SECRETO}", latency=0.1)], clock=clock
    )
    await make_client(provider, clock=clock).complete(f"Mi clave es {SECRETO}")

    eventos = _llm_calls(caplog)
    assert len(eventos) == 1
    evento = eventos[0]
    assert set(evento) >= CAMPOS_DE_USO
    assert evento["provider"] == "guionado"
    assert evento["model"] == "modelo-de-prueba"
    assert evento["operation"] == "complete"
    assert evento["input_tokens"] == 7
    assert evento["output_tokens"] == 3
    assert evento["attempts"] == 2
    assert evento["outcome"] == "ok"
    latencia = evento["latency_ms"]
    assert isinstance(latencia, float)
    assert latencia > 0
    _assert_sin_secreto(caplog)


async def test_log_de_una_llamada_fallida(caplog: pytest.LogCaptureFixture) -> None:
    """Scenario: Log de una llamada (resultado de error)."""
    caplog.set_level(logging.DEBUG)
    provider = ScriptedProvider([Fail(LLMProviderError("401", status_code=401))])
    with pytest.raises(LLMProviderError):
        await make_client(provider).complete(f"prompt con {SECRETO}")
    (evento,) = _llm_calls(caplog)
    assert evento["outcome"] == "error"
    assert evento["error_type"] == "LLMProviderError"
    assert evento["attempts"] == 1
    _assert_sin_secreto(caplog)


async def test_log_de_streaming_y_salida_estructurada(caplog: pytest.LogCaptureFixture) -> None:
    """Scenario: Log de una llamada (streaming y salida estructurada, proveedor fake)."""
    caplog.set_level(logging.DEBUG)
    client = build_llm_client(LLMSettings(provider="fake"))
    async for _ in client.stream(f"stream {SECRETO}"):
        pass
    await client.complete_structured(f"estructurada {SECRETO}", Respuesta)
    operaciones = [e["operation"] for e in _llm_calls(caplog)]
    assert operaciones == ["stream", "structured"]
    _assert_sin_secreto(caplog)
