"""Normalización de texto: la de salida conserva líneas, la del CER las aplana."""

from __future__ import annotations

import re
import unicodedata

# Cualquier blanco salvo el salto de línea: espacios, tabs, form feed, espacio duro (U+00A0).
_HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")


def normalize_text(text: str) -> str:
    """NFC, blancos colapsados dentro de cada línea y como máximo una línea vacía seguida.

    Se conservan los saltos de línea a propósito: `add-rag-core` usa la estructura de títulos
    y párrafos para su experimento de chunking.
    """
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = _HORIZONTAL_SPACE.sub(" ", raw_line).strip()
        if line or (lines and lines[-1]):
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def normalize_for_cer(text: str) -> str:
    """NFC y todos los blancos (saltos de línea incluidos) colapsados a un espacio.

    Así el CER mide caracteres reconocidos, no diferencias de maquetación (dónde corta cada
    línea, cuántos espacios separan las columnas de una tabla).
    """
    return " ".join(unicodedata.normalize("NFC", text).split())
