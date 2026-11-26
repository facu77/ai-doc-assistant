"""Interfaz del motor de OCR.

El pipeline depende de este Protocol, nunca de `pytesseract`: así los tests usan un motor
falso (sin Tesseract instalado) y otro motor (uno en la nube, por ejemplo) se puede comparar
sin tocar el dominio.
"""

from __future__ import annotations

from typing import Protocol

from PIL import Image


class OCRError(RuntimeError):
    """El motor de OCR no pudo reconocer la imagen (proceso caído, timeout, idioma ausente)."""


class OCREngine(Protocol):
    @property
    def name(self) -> str:
        """Identificador del motor y su configuración, para el reporte."""
        ...

    def recognize(self, image: Image.Image, *, dpi: int) -> str:
        """Devuelve el texto reconocido en `image`, rasterizada a `dpi`.

        Lanza `OCRError` si el motor falla.
        """
        ...
