"""Requirement: Selección de proveedor por configuración."""

from __future__ import annotations

import pytest

from ai_doc_assistant.llm import (
    LLMClient,
    LLMConfigError,
    build_llm_client,
    load_llm_settings,
)


async def _consumidor(client: LLMClient) -> str:
    """Un consumidor tipado contra el Protocol: no sabe qué proveedor hay detrás."""
    return f"{client.provider}/{client.model}"


async def test_cambio_de_proveedor_por_variable_de_entorno(
    isolated_env: pytest.MonkeyPatch,
) -> None:
    """Scenario: Cambio de proveedor por variable de entorno."""
    isolated_env.setenv("LLM_PROVIDER", "fake")
    fake_client = build_llm_client(load_llm_settings())
    assert fake_client.provider == "fake"
    respuesta = await fake_client.complete("hola")
    assert respuesta.provider == "fake"

    isolated_env.setenv("LLM_PROVIDER", "anthropic")
    isolated_env.setenv("ANTHROPIC_API_KEY", "clave-fake-para-tests")
    anthropic_client = build_llm_client(load_llm_settings())
    assert anthropic_client.provider == "anthropic"
    assert anthropic_client.model == "claude-haiku-5-5"

    # El mismo consumidor funciona con los dos sin cambios.
    assert await _consumidor(fake_client) == "fake/fake-llm"
    assert await _consumidor(anthropic_client) == "anthropic/claude-haiku-5-5"


def test_proveedor_desconocido_lista_los_validos(isolated_env: pytest.MonkeyPatch) -> None:
    """Scenario: Proveedor desconocido."""
    isolated_env.setenv("LLM_PROVIDER", "desconocido")
    with pytest.raises(LLMConfigError) as excinfo:
        build_llm_client(load_llm_settings())
    mensaje = str(excinfo.value)
    assert "desconocido" in mensaje
    for valido in ("anthropic", "fake", "openai"):
        assert valido in mensaje


def test_falta_la_clave_nombra_la_variable_sin_mostrar_otros_valores(
    isolated_env: pytest.MonkeyPatch,
) -> None:
    """Scenario: Falta la clave del proveedor."""
    isolated_env.setenv("LLM_PROVIDER", "openai")
    isolated_env.setenv("LLM_MODEL", "modelo-que-no-debe-aparecer")
    isolated_env.setenv("ANTHROPIC_API_KEY", "clave-fake-que-no-debe-aparecer")
    with pytest.raises(LLMConfigError) as excinfo:
        build_llm_client(load_llm_settings())
    mensaje = str(excinfo.value)
    assert "OPENAI_API_KEY" in mensaje
    assert "modelo-que-no-debe-aparecer" not in mensaje
    assert "clave-fake-que-no-debe-aparecer" not in mensaje


def test_clave_vacia_cuenta_como_faltante(isolated_env: pytest.MonkeyPatch) -> None:
    """Scenario: Falta la clave del proveedor (`ANTHROPIC_API_KEY=` como en .env.example)."""
    isolated_env.setenv("LLM_PROVIDER", "anthropic")
    isolated_env.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(LLMConfigError, match="ANTHROPIC_API_KEY"):
        build_llm_client(load_llm_settings())


def test_sin_proveedor_falla_al_arrancar(isolated_env: pytest.MonkeyPatch) -> None:
    """Requirement: validar la configuración al arrancar (LLM_PROVIDER ausente)."""
    with pytest.raises(LLMConfigError, match="LLM_PROVIDER"):
        build_llm_client(load_llm_settings())


def test_valor_invalido_nombra_la_variable_sin_mostrar_el_valor(
    isolated_env: pytest.MonkeyPatch,
) -> None:
    """Requirement: validar la configuración al arrancar (tipo inválido)."""
    isolated_env.setenv("LLM_PROVIDER", "fake")
    isolated_env.setenv("LLM_TIMEOUT_SECONDS", "valor-raro-1234")
    with pytest.raises(LLMConfigError) as excinfo:
        load_llm_settings()
    assert "LLM_TIMEOUT_SECONDS" in str(excinfo.value)
    assert "valor-raro-1234" not in str(excinfo.value)


def test_valores_por_defecto(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("LLM_PROVIDER", "fake")
    settings = load_llm_settings()
    assert settings.model == "claude-haiku-5-5"
    assert settings.timeout_seconds == 30
    assert settings.max_retries == 3
