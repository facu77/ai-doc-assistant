"""Requirement: Selección de proveedor por configuración."""

from __future__ import annotations

import asyncio
import time

import httpx2
import pytest

from ai_doc_assistant.llm import (
    PROVIDERS,
    LLMClient,
    LLMConfigError,
    LLMProviderError,
    LLMSettings,
    LLMTimeoutError,
    build_llm_client,
    load_llm_settings,
)
from ai_doc_assistant.llm.providers import anthropic_provider
from ai_doc_assistant.llm.providers.anthropic_provider import AnthropicProvider
from tests.fakes.http import FakeServer, status
from tests.fakes.llm import Hang, ScriptedProvider


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


def test_openai_sin_modelo_falla_al_arrancar(isolated_env: pytest.MonkeyPatch) -> None:
    """Scenario: Proveedor sin modelo por defecto (OpenAI no tiene default en el repo)."""
    isolated_env.setenv("LLM_PROVIDER", "openai")
    isolated_env.setenv("OPENAI_API_KEY", "clave-fake-para-tests")
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        build_llm_client(load_llm_settings())
    isolated_env.setenv("LLM_MODEL", "modelo-openai-de-prueba")
    client = build_llm_client(load_llm_settings())
    assert (client.provider, client.model) == ("openai", "modelo-openai-de-prueba")


# --- La fábrica conecta las variables de entorno de punta a punta


class _AnthropicConServidorFalso(AnthropicProvider):
    """El adaptador real, con el transporte HTTP falso: el resto lo arma la fábrica."""

    server = FakeServer([])

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            http_client=self.server.client(),
        )


async def test_fabrica_aplica_max_retries_y_timeout_al_adaptador(
    isolated_env: pytest.MonkeyPatch,
) -> None:
    """Requirement: Reintentos acotados + Timeout por llamada, desde el entorno."""
    _AnthropicConServidorFalso.server = FakeServer([status(503), status(503), status(503)])
    isolated_env.setattr(anthropic_provider, "AnthropicProvider", _AnthropicConServidorFalso)
    isolated_env.setenv("LLM_PROVIDER", "anthropic")
    isolated_env.setenv("ANTHROPIC_API_KEY", "clave-fake-para-tests")
    isolated_env.setenv("LLM_MAX_RETRIES", "2")
    isolated_env.setenv("LLM_TIMEOUT_SECONDS", "4.5")
    client = build_llm_client(load_llm_settings())
    with pytest.raises(LLMProviderError) as excinfo:
        await client.complete("prompt")
    server = _AnthropicConServidorFalso.server
    assert len(server.requests) == 2
    assert excinfo.value.attempts == 2
    assert server.requests[0].extensions["timeout"]["read"] == 4.5
    await client.aclose()


async def test_fabrica_aplica_el_timeout_del_cliente(isolated_env: pytest.MonkeyPatch) -> None:
    """Requirement: Timeout por llamada (la red de seguridad usa LLM_TIMEOUT_SECONDS)."""
    provider = ScriptedProvider([Hang()])
    isolated_env.setitem(PROVIDERS, "guionado", lambda settings: provider)
    isolated_env.setenv("LLM_PROVIDER", "guionado")
    isolated_env.setenv("LLM_TIMEOUT_SECONDS", "0.2")
    isolated_env.setenv("LLM_MAX_RETRIES", "1")
    client = build_llm_client(load_llm_settings())
    inicio = time.perf_counter()
    with pytest.raises(LLMTimeoutError):
        await asyncio.wait_for(client.complete("prompt"), 5.0)
    assert time.perf_counter() - inicio < 1.0
    assert provider.attempts == 1


async def test_aclose_cierra_el_proveedor(isolated_env: pytest.MonkeyPatch) -> None:
    provider = ScriptedProvider([])
    isolated_env.setitem(PROVIDERS, "guionado", lambda settings: provider)
    isolated_env.setenv("LLM_PROVIDER", "guionado")
    client = build_llm_client(load_llm_settings())
    await client.aclose()
    assert provider.closed
    await build_llm_client(LLMSettings(provider="fake")).aclose()
