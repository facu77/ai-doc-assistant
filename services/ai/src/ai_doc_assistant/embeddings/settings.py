"""Configuración de embeddings (`EMBEDDINGS_*`), leída con pydantic-settings."""

from __future__ import annotations

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_doc_assistant.embeddings.errors import EmbeddingsConfigError

DEFAULT_EMBEDDINGS_MODEL = "intfloat/multilingual-e5-small"


class EmbeddingsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDINGS_", env_ignore_empty=True, extra="ignore"
    )

    provider: str | None = None
    # Cambiar el modelo cambia el espacio vectorial: hay que reindexar todo.
    model: str = DEFAULT_EMBEDDINGS_MODEL
    batch_size: int = Field(default=64, gt=0)


def load_embeddings_settings() -> EmbeddingsSettings:
    """Lee el entorno; un valor inválido es un `EmbeddingsConfigError` sin el valor recibido."""
    try:
        return EmbeddingsSettings()
    except ValidationError as exc:
        problems = [
            f"EMBEDDINGS_{str(err['loc'][0]).upper()}: {err['msg']}"
            for err in exc.errors(include_input=False, include_url=False)
            if err["loc"]
        ]
        raise EmbeddingsConfigError(
            "configuración de embeddings inválida: " + "; ".join(problems)
        ) from None
