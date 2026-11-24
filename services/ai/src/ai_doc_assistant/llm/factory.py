"""Fábrica: de `LLMSettings` a un `LLMClient` listo, o un `LLMConfigError` al arrancar."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import SecretStr

from ai_doc_assistant.llm.client import LLMClient
from ai_doc_assistant.llm.errors import LLMConfigError
from ai_doc_assistant.llm.provider import LLMProvider
from ai_doc_assistant.llm.resilient import ResilientLLMClient
from ai_doc_assistant.llm.retry import RetryPolicy
from ai_doc_assistant.llm.settings import LLMSettings, load_llm_settings


def _require(secret: SecretStr | None, variable: str) -> str:
    if secret is None or not secret.get_secret_value().strip():
        # Solo se nombra la variable: ningún otro valor de configuración va al mensaje.
        raise LLMConfigError(f"falta la variable de entorno {variable} para este proveedor")
    return secret.get_secret_value()


def _fake(settings: LLMSettings) -> LLMProvider:
    from ai_doc_assistant.llm.providers.fake import FakeLLMProvider

    return FakeLLMProvider()


def _anthropic(settings: LLMSettings) -> LLMProvider:
    # Import diferido: el SDK solo se carga si se eligió este proveedor.
    from ai_doc_assistant.llm.providers.anthropic_provider import AnthropicProvider

    return AnthropicProvider(
        api_key=_require(settings.anthropic_api_key, "ANTHROPIC_API_KEY"),
        model=settings.model,
        timeout_seconds=settings.timeout_seconds,
    )


def _openai(settings: LLMSettings) -> LLMProvider:
    from ai_doc_assistant.llm.providers.openai_provider import OpenAIProvider

    return OpenAIProvider(
        api_key=_require(settings.openai_api_key, "OPENAI_API_KEY"),
        model=settings.model,
        timeout_seconds=settings.timeout_seconds,
    )


# Registro de proveedores: agregar uno es un archivo en providers/ y una línea acá.
PROVIDERS: dict[str, Callable[[LLMSettings], LLMProvider]] = {
    "anthropic": _anthropic,
    "fake": _fake,
    "openai": _openai,
}


def build_llm_client(settings: LLMSettings | None = None) -> LLMClient:
    """Arma el cliente del proveedor configurado. Llamala al arrancar el servicio."""
    resolved = settings if settings is not None else load_llm_settings()
    valid = ", ".join(sorted(PROVIDERS))
    if resolved.provider is None:
        raise LLMConfigError(
            f"falta la variable de entorno LLM_PROVIDER (valores válidos: {valid})"
        )
    builder = PROVIDERS.get(resolved.provider)
    if builder is None:
        raise LLMConfigError(
            f"LLM_PROVIDER={resolved.provider!r} no es válido (valores válidos: {valid})"
        )
    return ResilientLLMClient(
        builder(resolved),
        timeout_seconds=resolved.timeout_seconds,
        policy=RetryPolicy(max_attempts=resolved.max_retries),
    )
