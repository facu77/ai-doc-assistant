"""Tests de contrato contra el código real de los SDKs (sin red).

Un fake solo prueba lo que el autor del fake cree que hace el SDK. Acá se llama a la
función real que transforma el esquema, y se mira el cuerpo que el SDK real serializa.
Este test habría detectado el bug original: `dict[str, object]` sale de
`anthropic.transform_schema` como un objeto vacío y cerrado, y el modelo no puede llenar nada.
"""

from __future__ import annotations

import json

import anthropic
import pytest
from ai_doc_assistant.llm.schema import ensure_closed_schema

from ai_doc_assistant.llm import LLMSchemaError, ResilientLLMClient, RetryPolicy
from ai_doc_assistant.llm.provider import LLMRequest
from ai_doc_assistant.llm.providers.anthropic_provider import AnthropicProvider
from ai_doc_assistant.llm.providers.openai_provider import OpenAIProvider
from tests.fakes.http import FakeServer, anthropic_message, openai_completion
from tests.fakes.schemas import ConArgumentosLibres, LlamadaHerramienta

VARIANTES = {
    "BuscarDocumentos": {"herramienta", "query", "top_k"},
    "ObtenerPagina": {"herramienta", "doc_id", "pagina"},
}
PAGINA = {"llamada": {"herramienta": "obtener_pagina", "doc_id": "d1", "pagina": 2}}


def _assert_variantes_completas(schema: dict[str, object]) -> None:
    defs = schema["$defs"]
    assert isinstance(defs, dict)
    for nombre, campos in VARIANTES.items():
        variante = defs[nombre]
        assert set(variante["properties"]) == campos
        assert set(variante["required"]) == campos


def test_transform_schema_de_anthropic_conserva_la_union_cerrada() -> None:
    """Contrato: propiedades anidadas y `required` sobreviven a `anthropic.transform_schema`."""
    schema = anthropic.transform_schema(LlamadaHerramienta)
    _assert_variantes_completas(schema)
    llamada = schema["properties"]["llamada"]
    # `oneOf` + discriminador de Pydantic sale como `anyOf` de las dos variantes.
    assert llamada["anyOf"] == [
        {"$ref": "#/$defs/BuscarDocumentos"},
        {"$ref": "#/$defs/ObtenerPagina"},
    ]
    assert schema["required"] == ["llamada"]


def test_transform_schema_vacia_un_dict_libre() -> None:
    """Contrato: por esto se rechazan los dicts libres (el bug que motivó la decisión)."""
    schema = anthropic.transform_schema(ConArgumentosLibres)
    argumentos = schema["properties"]["argumentos"]
    assert argumentos["properties"] == {}
    assert argumentos["additionalProperties"] is False
    with pytest.raises(LLMSchemaError, match="argumentos"):
        ensure_closed_schema(ConArgumentosLibres)


def test_esquema_cerrado_pasa_la_validacion() -> None:
    ensure_closed_schema(LlamadaHerramienta)


async def test_anthropic_serializa_el_esquema_cerrado_completo() -> None:
    """Contrato: el cuerpo que arma el SDK real de Anthropic lleva la unión completa."""
    server = FakeServer([anthropic_message(json.dumps(PAGINA))])
    provider = AnthropicProvider(
        api_key="clave-fake-para-tests",
        model="claude-haiku-5-5",
        timeout_seconds=5,
        http_client=server.client(),
    )
    await provider.generate(LLMRequest(prompt="p", output_schema=LlamadaHerramienta))
    (body,) = server.json_bodies()
    output_config = body["output_config"]
    assert isinstance(output_config, dict)
    _assert_variantes_completas(output_config["format"]["schema"])
    await provider.aclose()


async def test_openai_serializa_el_esquema_cerrado_completo() -> None:
    """Contrato: el adaptador de OpenAI usa `model_json_schema()`; el SDK real lo serializa."""
    server = FakeServer([openai_completion(json.dumps(PAGINA))])
    provider = OpenAIProvider(
        api_key="clave-fake-para-tests",
        model="modelo-openai-de-prueba",
        timeout_seconds=5,
        http_client=server.client(),
    )
    await provider.generate(LLMRequest(prompt="p", output_schema=LlamadaHerramienta))
    (body,) = server.json_bodies()
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    _assert_variantes_completas(response_format["json_schema"]["schema"])
    await provider.aclose()


@pytest.mark.parametrize("adaptador", ["anthropic", "openai"])
async def test_esquema_abierto_no_llega_al_proveedor(adaptador: str) -> None:
    """Scenario: Esquema con objetos sin propiedades (con los SDKs reales: cero requests)."""
    server = FakeServer([])
    provider: AnthropicProvider | OpenAIProvider
    if adaptador == "anthropic":
        provider = AnthropicProvider(
            api_key="clave-fake-para-tests",
            model="claude-haiku-5-5",
            timeout_seconds=5,
            http_client=server.client(),
        )
    else:
        provider = OpenAIProvider(
            api_key="clave-fake-para-tests",
            model="modelo-openai-de-prueba",
            timeout_seconds=5,
            http_client=server.client(),
        )
    client = ResilientLLMClient(provider, timeout_seconds=5, policy=RetryPolicy(max_attempts=3))
    with pytest.raises(LLMSchemaError):
        await client.complete_structured("prompt", ConArgumentosLibres)
    assert server.requests == []
    await client.aclose()
