"""Tests de integración contra proveedores reales (pagos). Se saltean sin clave en el entorno.

Correr con: `make test-integration` (o `uv run pytest -m integration`).
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from ai_doc_assistant.llm import LLMSettings, build_llm_client
from tests.fakes.schemas import BuscarDocumentos, LlamadaHerramienta, ObtenerPagina

pytestmark = pytest.mark.integration


class Saludo(BaseModel):
    saludo: str
    idioma: str


def _settings(provider: str, key_var: str, model: str | None) -> LLMSettings:
    if not os.environ.get(key_var):
        pytest.skip(f"{key_var} no está definida")
    if not model:  # `OPENAI_INTEGRATION_MODEL=` vacía (como en .env.example) también saltea
        pytest.skip("falta el modelo para este proveedor")
    return LLMSettings(provider=provider, model=model, timeout_seconds=60, max_retries=2)


@pytest.fixture(params=["anthropic", "openai"])
def real_settings(request: pytest.FixtureRequest) -> LLMSettings:
    if request.param == "anthropic":
        return _settings("anthropic", "ANTHROPIC_API_KEY", "claude-haiku-5-5")
    # Para OpenAI no hay modelo por defecto en el repo: se elige explícitamente.
    return _settings("openai", "OPENAI_API_KEY", os.environ.get("OPENAI_INTEGRATION_MODEL"))


async def test_completado_y_streaming_reales(real_settings: LLMSettings) -> None:
    client = build_llm_client(real_settings)
    respuesta = await client.complete("Respondé solo con la palabra: hola", max_tokens=20)
    assert respuesta.text.strip()
    assert respuesta.usage.input_tokens > 0
    assert respuesta.usage.output_tokens > 0
    fragmentos = [f async for f in client.stream("Contá del 1 al 5 separado por comas")]
    assert "".join(fragmentos).strip()


async def test_salida_estructurada_real(real_settings: LLMSettings) -> None:
    client = build_llm_client(real_settings)
    saludo = await client.complete_structured(
        "Generá un saludo corto en español rioplatense.", Saludo, max_tokens=200
    )
    assert saludo.value.saludo
    assert saludo.usage.output_tokens > 0


async def test_union_discriminada_real(real_settings: LLMSettings) -> None:
    """Scenario: Respuesta válida, contra la API real (el esquema cerrado viaja completo)."""
    client = build_llm_client(real_settings)
    resultado = await client.complete_structured(
        "Herramientas: buscar_documentos(query, top_k) y obtener_pagina(doc_id, pagina). "
        "El usuario pide: 'mostrame la página 3 del documento politica-vacaciones'. "
        "Elegí la herramienta y sus argumentos.",
        LlamadaHerramienta,
        max_tokens=300,
    )
    llamada = resultado.value.llamada
    assert isinstance(llamada, ObtenerPagina | BuscarDocumentos)
    if isinstance(llamada, ObtenerPagina):
        assert llamada.pagina == 3
        assert llamada.doc_id
    await client.aclose()
