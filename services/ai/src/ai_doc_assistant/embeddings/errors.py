"""Errores propios de los embeddings."""

from __future__ import annotations


class EmbeddingsError(Exception):
    """Base de los errores de embeddings."""


class EmbeddingsConfigError(EmbeddingsError):
    """Configuración inválida: se levanta al arrancar."""
