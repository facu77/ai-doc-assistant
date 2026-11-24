"""Requirement: Salida estructurada."""

from __future__ import annotations

import json

import pytest
from ai_doc_assistant.llm import LLMSettings, LLMValidationError, build_llm_client
from pydantic import BaseModel

from tests.fakes.llm import Fail, Reply, ScriptedProvider, error_503, make_client


class LlamadaHerramienta(BaseModel):
    herramienta: str
    argumentos: dict[str, object]


async def test_respuesta_valida() -> None:
    """Scenario: Respuesta válida."""
    payload = {"herramienta": "buscar_documentos", "argumentos": {"consulta": "vacaciones"}}
    provider = ScriptedProvider([Reply(text=json.dumps(payload))])
    resultado = await make_client(provider).complete_structured("prompt", LlamadaHerramienta)
    assert isinstance(resultado, LlamadaHerramienta)
    assert resultado.herramienta == "buscar_documentos"
    assert resultado.argumentos == {"consulta": "vacaciones"}
    # El esquema viaja al proveedor para que use su modo de salida estructurada.
    assert provider.requests[0].output_schema is LlamadaHerramienta


async def test_respuesta_invalida_en_todos_los_intentos() -> None:
    """Scenario: Respuesta inválida."""
    prompt = "Elegí una herramienta para secreto-de-prueba"
    provider = ScriptedProvider([Reply(text="esto no es JSON"), Reply(text='{"herramienta": 42}')])
    with pytest.raises(LLMValidationError) as excinfo:
        await make_client(provider).complete_structured(prompt, LlamadaHerramienta)
    error = excinfo.value
    assert error.attempts == 2
    assert "2" in str(error)
    assert "secreto-de-prueba" not in str(error)
    assert provider.attempts == 2


async def test_reintento_con_el_error_de_validacion_como_contexto() -> None:
    """Design: si no valida, se reintenta una vez con el error de validación como contexto."""
    valido = json.dumps({"herramienta": "resumir", "argumentos": {}})
    provider = ScriptedProvider([Reply(text='{"herramienta": "resumir"}'), Reply(text=valido)])
    resultado = await make_client(provider).complete_structured(
        "prompt original", LlamadaHerramienta
    )
    assert resultado.herramienta == "resumir"
    segundo = provider.requests[1].prompt
    assert segundo.startswith("prompt original")
    assert "argumentos" in segundo, "el reintento le dice al modelo qué campo falló"


async def test_los_errores_transitorios_se_reintentan_aparte() -> None:
    """La validación y los errores transitorios son políticas distintas."""
    valido = json.dumps({"herramienta": "resumir", "argumentos": {}})
    provider = ScriptedProvider([Fail(error_503()), Reply(text=valido)])
    resultado = await make_client(provider).complete_structured("prompt", LlamadaHerramienta)
    assert resultado.herramienta == "resumir"


async def test_el_fake_produce_un_objeto_valido_para_el_esquema() -> None:
    """Scenario: Respuesta válida (el proveedor fake sirve para CI del agente)."""
    client = build_llm_client(LLMSettings(provider="fake"))
    resultado = await client.complete_structured("prompt", LlamadaHerramienta)
    assert isinstance(resultado, LlamadaHerramienta)
