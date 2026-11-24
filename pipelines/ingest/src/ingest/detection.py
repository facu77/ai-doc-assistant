"""Detección por página: ¿la capa de texto sirve o hay que hacer OCR?

Regla (design.md): la página es nativa si tiene al menos `min_chars` caracteres extraíbles
(no blancos) y al menos `min_printable_ratio` de ellos son imprimibles. Lo segundo atrapa
capas de texto rotas, por ejemplo fuentes sin tabla ToUnicode que se extraen como U+FFFD.
"""

from __future__ import annotations

import unicodedata

_REPLACEMENT_CHAR = "�"
# Uso privado, sustitutos y puntos de código sin asignar: aparecen en capas de texto rotas.
_GARBAGE_CATEGORIES = frozenset({"Co", "Cs", "Cn"})


def _extractable(text: str) -> list[str]:
    return [char for char in text if not char.isspace()]


def _is_printable(char: str) -> bool:
    return (
        char.isprintable()
        and char != _REPLACEMENT_CHAR
        and unicodedata.category(char) not in _GARBAGE_CATEGORIES
    )


def printable_ratio(text: str) -> float:
    """Proporción de caracteres imprimibles entre los no blancos (0.0 si no hay ninguno)."""
    chars = _extractable(text)
    if not chars:
        return 0.0
    return sum(1 for char in chars if _is_printable(char)) / len(chars)


def extractable_count(text: str) -> int:
    return len(_extractable(text))


def is_native_text(text: str, *, min_chars: int, min_printable_ratio: float) -> bool:
    return extractable_count(text) >= min_chars and printable_ratio(text) >= min_printable_ratio
