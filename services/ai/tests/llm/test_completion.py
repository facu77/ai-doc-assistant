"""Requirement: Completado y streaming."""

from __future__ import annotations

import pytest
from ai_doc_assistant.llm import LLMProviderError, LLMSettings, build_llm_client

from tests.fakes.llm import Fail, FakeClock, Reply, ScriptedProvider, error_503, make_client


async def test_respuesta_completa_con_el_proveedor_fake() -> None:
    """Scenario: Respuesta completa."""
    client = build_llm_client(LLMSettings(provider="fake"))
    respuesta = await client.complete("¿Cuántos días de licencia anual tengo?")
    assert respuesta.text
    assert respuesta.usage.input_tokens > 0
    assert respuesta.usage.output_tokens > 0
    assert respuesta.latency_ms >= 0
    assert respuesta.provider == "fake"
    assert respuesta.model == "fake-llm"


async def test_el_fake_es_determinista() -> None:
    """Scenario: Respuesta completa (el proveedor fake es determinista para CI)."""
    client = build_llm_client(LLMSettings(provider="fake"))
    a = await client.complete("mismo prompt")
    b = await client.complete("mismo prompt")
    c = await client.complete("otro prompt distinto")
    assert a.text == b.text
    assert a.text != c.text


async def test_latencia_medida_con_el_reloj() -> None:
    """Scenario: Respuesta completa (latencia en milisegundos)."""
    clock = FakeClock()
    provider = ScriptedProvider([Reply(text="hola", latency=0.25)], clock=clock)
    respuesta = await make_client(provider, clock=clock).complete("prompt")
    assert respuesta.latency_ms == pytest.approx(250.0)
    assert respuesta.usage.input_tokens == 7
    assert respuesta.usage.output_tokens == 3
    assert respuesta.provider == "guionado"
    assert respuesta.model == "modelo-de-prueba"


async def test_streaming_concatena_igual_que_el_completado() -> None:
    """Scenario: Streaming."""
    client = build_llm_client(LLMSettings(provider="fake"))
    prompt = "Resumí la política de vacaciones"
    fragmentos = [f async for f in client.stream(prompt)]
    completa = await client.complete(prompt)
    assert len(fragmentos) > 1, "el streaming tiene que ser incremental"
    assert "".join(fragmentos) == completa.text


async def test_streaming_entrega_los_fragmentos_en_orden() -> None:
    """Scenario: Streaming (orden de los fragmentos)."""
    provider = ScriptedProvider([Reply(chunks=["uno ", "dos ", "tres"])])
    fragmentos = [f async for f in make_client(provider).stream("prompt")]
    assert fragmentos == ["uno ", "dos ", "tres"]


async def test_streaming_reintenta_si_falla_antes_del_primer_token() -> None:
    """Requirement: Reintentos acotados (streaming: solo antes del primer token)."""
    provider = ScriptedProvider([Fail(error_503()), Reply(chunks=["hola ", "mundo"])])
    fragmentos = [f async for f in make_client(provider).stream("prompt")]
    assert fragmentos == ["hola ", "mundo"]
    assert provider.attempts == 2


async def test_streaming_no_reintenta_despues_del_primer_token() -> None:
    """Requirement: Reintentos acotados (no se puede reintentar tras emitir tokens)."""
    provider = ScriptedProvider(
        [Fail(error_503(), after_chunks=["parcial "]), Reply(chunks=["no ", "debería"])]
    )
    recibidos: list[str] = []

    async def consumir() -> None:
        async for fragmento in make_client(provider).stream("prompt"):
            recibidos.append(fragmento)

    with pytest.raises(LLMProviderError) as excinfo:
        await consumir()
    assert recibidos == ["parcial "]
    assert provider.attempts == 1
    assert excinfo.value.attempts == 1
