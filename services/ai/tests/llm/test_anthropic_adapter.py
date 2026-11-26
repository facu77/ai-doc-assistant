"""Adaptador de Anthropic contra un servidor HTTP falso (SDK real, sin red).

Requirements: Errores tipados y aislamiento del SDK; Reintentos; Timeout; Salida estructurada.
"""

from __future__ import annotations

import json
import logging

import anthropic
import pytest
from pydantic import BaseModel

from ai_doc_assistant.llm import (
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    ResilientLLMClient,
    RetryPolicy,
)
from ai_doc_assistant.llm.providers.anthropic_provider import AnthropicProvider
from tests.fakes.http import (
    FakeServer,
    anthropic_message,
    anthropic_stream,
    anthropic_stream_error,
    raise_timeout,
    status,
)
from tests.fakes.llm import FakeClock


class Clasificacion(BaseModel):
    categoria: str
    confianza: float


def _client(
    server: FakeServer, *, attempts: int = 3, clock: FakeClock | None = None
) -> ResilientLLMClient:
    fake_clock = clock if clock is not None else FakeClock()
    provider = AnthropicProvider(
        api_key="clave-fake-para-tests",
        model="claude-haiku-5-5",
        timeout_seconds=7.5,
        http_client=server.client(),
    )
    return ResilientLLMClient(
        provider,
        timeout_seconds=7.5,
        policy=RetryPolicy(max_attempts=attempts, random=lambda: 0.0),
        sleep=fake_clock.sleep,
        clock=fake_clock,
    )


async def test_completado_traduce_respuesta_y_uso() -> None:
    server = FakeServer([anthropic_message("hola desde claude", input_tokens=12, output_tokens=5)])
    respuesta = await _client(server).complete("Decí hola", system="Sos breve.")
    assert respuesta.text == "hola desde claude"
    assert respuesta.usage.input_tokens == 12
    assert respuesta.usage.output_tokens == 5
    assert respuesta.provider == "anthropic"
    assert respuesta.model == "claude-haiku-5-5"

    (body,) = server.json_bodies()
    assert body["model"] == "claude-haiku-5-5"
    assert body["system"] == "Sos breve."
    assert body["messages"] == [{"role": "user", "content": "Decí hola"}]
    assert isinstance(body["max_tokens"], int)
    # Los modelos actuales rechazan los parámetros de muestreo con un 400.
    for prohibido in ("temperature", "top_p", "top_k"):
        assert prohibido not in body


async def test_timeout_explicito_llega_al_cliente_http() -> None:
    """Requirement: Timeout por llamada (se pasa al cliente HTTP del SDK)."""
    server = FakeServer([anthropic_message("ok")])
    await _client(server).complete("prompt")
    timeouts = server.requests[0].extensions["timeout"]
    assert timeouts["read"] == 7.5


async def test_los_reintentos_del_sdk_estan_desactivados() -> None:
    """Design: la política de reintentos es nuestra; el SDK hace un solo intento."""
    server = FakeServer([status(503), anthropic_message("no debería llegar")])
    with pytest.raises(LLMProviderError):
        await _client(server, attempts=1).complete("prompt")
    assert len(server.requests) == 1


async def test_503_dos_veces_y_despues_responde() -> None:
    """Scenario: Error transitorio que se recupera (con el SDK real)."""
    server = FakeServer([status(503), status(503), anthropic_message("listo")])
    respuesta = await _client(server, attempts=3).complete("prompt")
    assert respuesta.text == "listo"
    assert len(server.requests) == 3


@pytest.mark.parametrize("codigo", [400, 401])
async def test_excepcion_del_sdk_queda_como_causa(codigo: int) -> None:
    """Scenario: Excepción del SDK (y Scenario: Error no reintentable)."""
    server = FakeServer([status(codigo), anthropic_message("no debería llegar")])
    with pytest.raises(LLMError) as excinfo:
        await _client(server).complete("prompt")
    error = excinfo.value
    assert isinstance(error, LLMProviderError)
    assert error.status_code == codigo
    assert isinstance(error.__cause__, anthropic.APIStatusError)
    assert not isinstance(error, anthropic.AnthropicError)
    assert len(server.requests) == 1


async def test_429_con_retry_after() -> None:
    """Scenario: Respeto de Retry-After (con el SDK real)."""
    clock = FakeClock()
    server = FakeServer(
        [status(429, headers={"retry-after": "2"}), anthropic_message("ok")], clock=clock
    )
    respuesta = await _client(server, clock=clock).complete("prompt")
    assert respuesta.text == "ok"
    assert server.request_times[1] - server.request_times[0] >= 2.0


async def test_429_agotado_es_rate_limit_tipado() -> None:
    server = FakeServer([status(429, headers={"retry-after": "3"})])
    with pytest.raises(LLMRateLimitError) as excinfo:
        await _client(server, attempts=1).complete("prompt")
    assert excinfo.value.retry_after == 3.0
    assert isinstance(excinfo.value.__cause__, anthropic.RateLimitError)


async def test_timeout_de_red_es_timeout_tipado() -> None:
    server = FakeServer([raise_timeout()])
    with pytest.raises(LLMTimeoutError) as excinfo:
        await _client(server, attempts=1).complete("prompt")
    assert isinstance(excinfo.value.__cause__, anthropic.APITimeoutError)


async def test_streaming() -> None:
    """Scenario: Streaming (con el SDK real)."""
    server = FakeServer([anthropic_stream(["Hola", ", ", "mundo"])])
    fragmentos = [f async for f in _client(server).stream("prompt")]
    assert fragmentos == ["Hola", ", ", "mundo"]
    (body,) = server.json_bodies()
    assert body["stream"] is True


async def test_streaming_reintenta_503_antes_del_primer_token() -> None:
    server = FakeServer([status(503), anthropic_stream(["ok"])])
    fragmentos = [f async for f in _client(server).stream("prompt")]
    assert fragmentos == ["ok"]
    assert len(server.requests) == 2


async def test_salida_estructurada_usa_output_config() -> None:
    """Scenario: Respuesta válida (formato de salida del SDK de Anthropic)."""
    payload = json.dumps({"categoria": "licencias", "confianza": 0.9})
    server = FakeServer([anthropic_message(payload)])
    resultado = await _client(server).complete_structured("Clasificá", Clasificacion)
    assert resultado.value == Clasificacion(categoria="licencias", confianza=0.9)
    assert resultado.usage.input_tokens == 11
    (body,) = server.json_bodies()
    output_config = body["output_config"]
    assert isinstance(output_config, dict)
    formato = output_config["format"]
    assert formato["type"] == "json_schema"
    assert set(formato["schema"]["properties"]) == {"categoria", "confianza"}


async def test_los_logs_del_sdk_no_filtran_el_prompt(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Registro de uso sin contenido sensible (ni siquiera en DEBUG del SDK)."""
    caplog.set_level(logging.DEBUG)
    server = FakeServer([anthropic_message("ok")])
    await _client(server).complete("prompt con secreto-de-prueba")
    assert "secreto-de-prueba" not in caplog.text


@pytest.mark.parametrize("tipo", ["overloaded_error", "api_error"])
async def test_error_sse_transitorio_antes_del_primer_token_se_reintenta(tipo: str) -> None:
    """Un evento SSE `error` llega con HTTP 200: el tipo del cuerpo decide si es transitorio."""
    server = FakeServer([anthropic_stream_error(tipo), anthropic_stream(["ok"])])
    fragmentos = [f async for f in _client(server).stream("prompt")]
    assert fragmentos == ["ok"]
    assert len(server.requests) == 2


async def test_error_sse_de_rate_limit_es_rate_limit_tipado() -> None:
    server = FakeServer([anthropic_stream_error("rate_limit_error")])
    with pytest.raises(LLMRateLimitError):
        async for _ in _client(server, attempts=1).stream("prompt"):
            pass


async def test_error_sse_permanente_no_se_reintenta() -> None:
    server = FakeServer([anthropic_stream_error("invalid_request_error"), anthropic_stream(["x"])])
    with pytest.raises(LLMProviderError) as excinfo:
        async for _ in _client(server).stream("prompt"):
            pass
    assert excinfo.value.transient is False
    assert len(server.requests) == 1


async def test_error_sse_despues_del_primer_token_no_se_reintenta() -> None:
    server = FakeServer(
        [
            anthropic_stream_error("overloaded_error", chunks_before=["parcial"]),
            anthropic_stream(["x"]),
        ]
    )
    recibidos: list[str] = []

    async def consumir() -> None:
        async for fragmento in _client(server).stream("prompt"):
            recibidos.append(fragmento)

    with pytest.raises(LLMProviderError) as excinfo:
        await consumir()
    assert recibidos == ["parcial"]
    assert excinfo.value.transient is True
    assert len(server.requests) == 1


async def test_retry_after_mayor_al_tope_no_espera() -> None:
    """Scenario: Retry-After mayor que el tope (con el SDK real)."""
    clock = FakeClock()
    server = FakeServer([status(429, headers={"retry-after": "120"}), anthropic_message("ok")])
    with pytest.raises(LLMRateLimitError) as excinfo:
        await _client(server, clock=clock).complete("prompt")
    assert excinfo.value.retry_after == 120.0
    assert clock.sleeps == []
    assert len(server.requests) == 1


async def test_aclose_cierra_el_cliente_http() -> None:
    server = FakeServer([])
    http_client = server.client()
    provider = AnthropicProvider(
        api_key="clave-fake-para-tests",
        model="claude-haiku-5-5",
        timeout_seconds=5,
        http_client=http_client,
    )
    client = ResilientLLMClient(provider, timeout_seconds=5, policy=RetryPolicy(max_attempts=1))
    await client.aclose()
    assert http_client.is_closed
