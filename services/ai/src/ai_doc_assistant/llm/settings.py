"""Configuración del cliente LLM, leída de variables de entorno con pydantic-settings."""

from __future__ import annotations

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_doc_assistant.llm.errors import LLMConfigError

DEFAULT_LLM_MODEL = "claude-haiku-5-5"


class LLMSettings(BaseSettings):
    """`LLM_*` más las claves de cada proveedor (sin prefijo, como las nombran los SDKs).

    Las claves son `SecretStr`: su `repr` y su `str` muestran `**********`, así que un
    log o un traceback accidental no las filtra.
    """

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        # `ANTHROPIC_API_KEY=` (vacía, como en .env.example) cuenta como no definida.
        env_ignore_empty=True,
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
    )

    provider: str | None = None
    model: str = DEFAULT_LLM_MODEL
    timeout_seconds: float = Field(default=30.0, gt=0)
    # Intentos totales, como dice la spec: 3 = 1 intento + hasta 2 reintentos; 1 = sin reintentos.
    max_retries: int = Field(default=3, ge=1)
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")


def _env_name(field: str) -> str:
    return field if field.isupper() else f"LLM_{field}".upper()


def load_llm_settings() -> LLMSettings:
    """Lee la configuración del entorno. Un valor inválido es un `LLMConfigError`.

    El `ValidationError` de Pydantic incluye el valor recibido (`input_value=...`); acá se
    arma un mensaje solo con el nombre de la variable y el motivo, para no filtrar nada.
    """
    try:
        return LLMSettings()
    except ValidationError as exc:
        problems = [
            f"{_env_name(str(err['loc'][0]))}: {err['msg']}"
            for err in exc.errors(include_input=False, include_url=False)
            if err["loc"]
        ]
        raise LLMConfigError("configuración de LLM inválida: " + "; ".join(problems)) from None
