"""Adaptador de OpenAI contra un servidor HTTP falso (SDK real, sin red).

Requirements: Errores tipados y aislamiento del SDK; Reintentos; Salida estructurada.
"""

from __future__ import annotations

import json

import openai
import pytest
from pydantic import BaseModel

from ai_doc_assistant.llm import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    ResilientLLMClient,
    RetryPolicy,
)
from ai_doc_assistant.llm.providers.openai_provider import OpenAIProvider
from tests.fakes.http import FakeServer, openai_completion, openai_stream, raise_timeout, status
from tests.fakes.llm import FakeClock


class Clasificacion(BaseModel):
    categoria: str
    confianza: float


def _client(
    server: FakeServer, *, attempts: int = 3, clock: FakeClock | None = None
) -> ResilientLLMClient:
    fake_clock = clock if clock is not None else FakeClock()
    provider = OpenAIProvider(
        api_key="clave-fake-para-tests",
        model="modelo-openai-de-prueba",
        timeout_seconds=6.0,
        http_client=server.client(),
    )
    return ResilientLLMClient(
        provider,
        timeout_seconds=6.0,
        policy=RetryPolicy(max_attempts=attempts, random=lambda: 0.0),
        sleep=fake_clock.sleep,
        clock=fake_clock,
    )


async def test_completado_traduce_respuesta_y_uso() -> None:
    server = FakeServer([openai_completion("hola", prompt_tokens=9, completion_tokens=2)])
    respuesta = await _client(server).complete("Decí hola", system="Sos breve.")
    assert respuesta.text == "hola"
    assert respuesta.usage.input_tokens == 9
    assert respuesta.usage.output_tokens == 2
    assert respuesta.provider == "openai"
    assert respuesta.model == "modelo-openai-de-prueba"
    (body,) = server.json_bodies()
    assert body["messages"] == [
        {"role": "system", "content": "Sos breve."},
        {"role": "user", "content": "Decí hola"},
    ]
    assert server.requests[0].extensions["timeout"]["read"] == 6.0


async def test_reintentos_del_sdk_desactivados_y_5xx_transitorio() -> None:
    """Scenario: Error transitorio que se recupera (con el SDK real)."""
    server = FakeServer([status(500), status(503), openai_completion("listo")])
    respuesta = await _client(server).complete("prompt")
    assert respuesta.text == "listo"
    assert len(server.requests) == 3


@pytest.mark.parametrize("codigo", [400, 401])
async def test_excepcion_del_sdk_queda_como_causa(codigo: int) -> None:
    """Scenario: Excepción del SDK (y Scenario: Error no reintentable)."""
    server = FakeServer([status(codigo), openai_completion("no debería llegar")])
    with pytest.raises(LLMProviderError) as excinfo:
        await _client(server).complete("prompt")
    assert excinfo.value.status_code == codigo
    assert isinstance(excinfo.value.__cause__, openai.APIStatusError)
    assert len(server.requests) == 1


async def test_429_con_retry_after() -> None:
    """Scenario: Respeto de Retry-After (con el SDK real)."""
    clock = FakeClock()
    server = FakeServer(
        [status(429, headers={"retry-after": "2"}), openai_completion("ok")], clock=clock
    )
    await _client(server, clock=clock).complete("prompt")
    assert server.request_times[1] - server.request_times[0] >= 2.0


async def test_429_agotado_es_rate_limit_tipado() -> None:
    server = FakeServer([status(429, headers={"retry-after-ms": "1500"})])
    with pytest.raises(LLMRateLimitError) as excinfo:
        await _client(server, attempts=1).complete("prompt")
    assert excinfo.value.retry_after == 1.5


async def test_timeout_de_red_es_timeout_tipado() -> None:
    server = FakeServer([raise_timeout()])
    with pytest.raises(LLMTimeoutError) as excinfo:
        await _client(server, attempts=1).complete("prompt")
    assert isinstance(excinfo.value.__cause__, openai.APITimeoutError)


async def test_streaming() -> None:
    """Scenario: Streaming (con el SDK real)."""
    server = FakeServer([openai_stream(["Hola", ", ", "mundo"])])
    fragmentos = [f async for f in _client(server).stream("prompt")]
    assert fragmentos == ["Hola", ", ", "mundo"]
    (body,) = server.json_bodies()
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}


async def test_salida_estructurada_usa_response_format() -> None:
    """Scenario: Respuesta válida (formato de salida del SDK de OpenAI)."""
    payload = json.dumps({"categoria": "licencias", "confianza": 0.75})
    server = FakeServer([openai_completion(payload)])
    resultado = await _client(server).complete_structured("Clasificá", Clasificacion)
    assert resultado == Clasificacion(categoria="licencias", confianza=0.75)
    (body,) = server.json_bodies()
    formato = body["response_format"]
    assert isinstance(formato, dict)
    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["name"] == "Clasificacion"
