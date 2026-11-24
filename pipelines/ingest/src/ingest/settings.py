"""Configuración del pipeline, leída de variables de entorno con prefijo `INGEST_`.

La CLI puede pisar cada valor con un flag.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGEST_", extra="ignore", frozen=True)

    min_native_chars: int = Field(
        default=50,
        ge=0,
        description="Mínimo de caracteres no blancos para tratar la página como nativa.",
    )
    min_printable_ratio: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Proporción mínima de imprimibles para tratar la página como nativa.",
    )
    ocr_dpi: int = Field(default=300, gt=0, description="dpi al rasterizar páginas para OCR.")
    ocr_lang: str = Field(default="spa+eng", description="Idiomas de Tesseract.")
    ocr_timeout_s: float = Field(default=120.0, gt=0, description="Timeout por página de OCR.")
