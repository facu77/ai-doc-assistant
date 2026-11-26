"""Requirement: Salida estructurada."""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import BaseModel

from ai_doc_assistant.llm import (
    LLMProviderError,
    LLMSchemaError,
    LLMSettings,
    LLMValidationError,
    StructuredResponse,
    build_llm_client,
)
from tests.fakes.llm import Fail, FakeClock, Reply, ScriptedProvider, error_503, make_client
from tests.fakes.schemas import (
    BuscarDocumentos,
    ConArgumentosLibres,
    ConCampoAny,
    ConDictAnidado,
    ConExtraAllow,
    ConLista,
    ConModeloAnidadoVacio,
    ConTupla,
    LlamadaHerramienta,
    ObtenerPagina,
    UnionEnLaRaiz,
)

PAGINA = {
    "llamada": {"herramienta": "obtener_pagina", "doc_id": "politica-vacaciones", "pagina": 3}
}
BUSQUEDA = {"llamada": {"herramienta": "buscar_documentos", "query": "vacaciones", "top_k": 5}}


async def test_respuesta_valida() -> None:
    """Scenario: Respuesta válida (esquema cerrado, unión discriminada por herramienta)."""
    clock = FakeClock()
    provider = ScriptedProvider([Reply(text=json.dumps(PAGINA), latency=0.2)], clock=clock)
    resultado = await make_client(provider, clock=clock).complete_structured(
        "prompt", LlamadaHerramienta
    )
    assert isinstance(resultado, StructuredResponse)
    llamada = resultado.value.llamada
    assert isinstance(llamada, ObtenerPagina)
    assert llamada.doc_id == "politica-vacaciones"
    assert llamada.pagina == 3
    assert resultado.usage.input_tokens == 7
    assert resultado.usage.output_tokens == 3
    assert resultado.attempts == 1
    assert resultado.latency_ms == pytest.approx(200.0)
    assert resultado.provider == "guionado"
    assert resultado.model == "modelo-de-prueba"
    # El esquema viaja al proveedor para que use su modo de salida estructurada.
    assert provider.requests[0].output_schema is LlamadaHerramienta


async def test_el_discriminador_elige_la_herramienta() -> None:
    """Scenario: Respuesta válida (la otra variante de la unión)."""
    provider = ScriptedProvider([Reply(text=json.dumps(BUSQUEDA))])
    resultado = await make_client(provider).complete_structured("prompt", LlamadaHerramienta)
    assert resultado.value.llamada == BuscarDocumentos(
        herramienta="buscar_documentos", query="vacaciones", top_k=5
    )


async def test_herramienta_desconocida_no_valida() -> None:
    """Un nombre de herramienta fuera de la unión es una respuesta inválida."""
    otra = {"llamada": {"herramienta": "borrar_todo", "doc_id": "x", "pagina": 1}}
    provider = ScriptedProvider([Reply(text=json.dumps(otra)), Reply(text=json.dumps(otra))])
    with pytest.raises(LLMValidationError):
        await make_client(provider).complete_structured("prompt", LlamadaHerramienta)


async def test_respuesta_invalida_en_todos_los_intentos(caplog: pytest.LogCaptureFixture) -> None:
    """Scenario: Respuesta inválida."""
    caplog.set_level(logging.INFO)
    prompt = "Elegí una herramienta para secreto-de-prueba"
    provider = ScriptedProvider(
        [Reply(text="esto no es JSON"), Reply(text='{"llamada": {"herramienta": 42}}')]
    )
    with pytest.raises(LLMValidationError) as excinfo:
        await make_client(provider).complete_structured(prompt, LlamadaHerramienta)
    error = excinfo.value
    assert error.attempts == 2
    assert str(error).startswith(
        "la respuesta no cumplió el esquema LlamadaHerramienta después de 2 intentos"
    )
    assert "secreto-de-prueba" not in str(error)
    assert provider.attempts == 2
    # Al rendirse se loguea el evento con resultado de error.
    eventos = [getattr(r, "llm_call", None) for r in caplog.records]
    (evento,) = [e for e in eventos if isinstance(e, dict)]
    assert evento["operation"] == "structured"
    assert evento["outcome"] == "error"
    assert evento["error_type"] == "LLMValidationError"
    assert evento["attempts"] == 2
    assert evento["input_tokens"] == 14
    assert evento["output_tokens"] == 6


async def test_reintento_con_el_error_de_validacion_como_contexto() -> None:
    """Design: si no valida, se reintenta una vez con el error de validación como contexto."""
    incompleto = {"llamada": {"herramienta": "obtener_pagina", "doc_id": "x"}}
    provider = ScriptedProvider(
        [Reply(text=json.dumps(incompleto)), Reply(text=json.dumps(PAGINA))]
    )
    resultado = await make_client(provider).complete_structured(
        "prompt original", LlamadaHerramienta
    )
    assert isinstance(resultado.value.llamada, ObtenerPagina)
    segundo = provider.requests[1].prompt
    assert segundo.startswith("prompt original")
    assert "pagina" in segundo, "el reintento le dice al modelo qué campo falló"
    # StructuredResponse suma el uso y cuenta los intentos de todas las rondas.
    assert resultado.attempts == 2
    assert resultado.usage.input_tokens == 14
    assert resultado.usage.output_tokens == 6


async def test_los_errores_transitorios_se_reintentan_aparte() -> None:
    """La validación y los errores transitorios son políticas distintas."""
    provider = ScriptedProvider([Fail(error_503()), Reply(text=json.dumps(PAGINA))])
    resultado = await make_client(provider).complete_structured("prompt", LlamadaHerramienta)
    assert isinstance(resultado.value.llamada, ObtenerPagina)
    assert resultado.attempts == 2  # 1 intento con 503 + 1 que validó


@pytest.mark.parametrize(
    ("schema", "campo"),
    [
        (ConArgumentosLibres, "argumentos"),
        (ConDictAnidado, "extras"),
        (ConCampoAny, "valor"),
        (UnionEnLaRaiz, "(raíz)"),
        (ConModeloAnidadoVacio, "vacio: objeto sin propiedades declaradas"),
        (ConExtraAllow, "(raíz): admite propiedades libres"),
        (ConTupla, "par: array sin `items`"),
    ],
)
async def test_esquema_abierto_se_rechaza_antes_de_llamar(
    schema: type[BaseModel], campo: str
) -> None:
    """Scenario: Esquema con objetos sin propiedades."""
    provider = ScriptedProvider([Reply(text="{}")])
    with pytest.raises(LLMSchemaError) as excinfo:
        await make_client(provider).complete_structured("prompt", schema)
    assert provider.attempts == 0, "no se llama al proveedor con un esquema abierto"
    assert campo in str(excinfo.value)


async def test_el_fake_rechaza_esquemas_abiertos() -> None:
    """Scenario: Esquema con objetos sin propiedades (también con el proveedor fake)."""
    client = build_llm_client(LLMSettings(provider="fake"))
    with pytest.raises(LLMSchemaError):
        await client.complete_structured("prompt", ConArgumentosLibres)


async def test_el_fake_produce_un_objeto_valido_para_el_esquema() -> None:
    """Scenario: Respuesta válida (el proveedor fake sirve para CI del agente)."""
    client = build_llm_client(LLMSettings(provider="fake"))
    resultado = await client.complete_structured("prompt", LlamadaHerramienta)
    assert isinstance(resultado.value, LlamadaHerramienta)
    assert resultado.provider == "fake"


async def test_lista_de_modelos_cerrados_es_valida() -> None:
    payload = {"resultados": [{"herramienta": "buscar_documentos", "query": "q", "top_k": 1}]}
    provider = ScriptedProvider([Reply(text=json.dumps(payload))])
    resultado = await make_client(provider).complete_structured("prompt", ConLista)
    assert resultado.value.resultados[0].top_k == 1


async def test_se_rinde_por_error_del_proveedor_en_la_segunda_ronda(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ronda 1 no valida; en la ronda 2 el proveedor falla 3 veces con 503."""
    caplog.set_level(logging.INFO)
    provider = ScriptedProvider(
        [Reply(text="no json"), Fail(error_503()), Fail(error_503()), Fail(error_503())]
    )
    with pytest.raises(LLMProviderError) as excinfo:
        await make_client(provider, max_attempts=3).complete_structured(
            "prompt", LlamadaHerramienta
        )
    assert excinfo.value.attempts == 4
    assert provider.attempts == 4
    eventos = [e for e in (getattr(r, "llm_call", None) for r in caplog.records) if e]
    (evento,) = eventos
    assert isinstance(evento, dict)
    assert evento["operation"] == "structured"
    assert evento["outcome"] == "error"
    assert evento["error_type"] == "LLMProviderError"
    assert evento["attempts"] == 4
    # Los tokens de la ronda 1 (la que respondió, aunque no validó) quedan en el log.
    assert evento["input_tokens"] == 7
    assert evento["output_tokens"] == 3
