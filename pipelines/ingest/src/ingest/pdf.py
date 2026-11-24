"""Adaptador de pymupdf: abrir un PDF, leer la capa de texto y rasterizar una página.

Es el único módulo que importa `pymupdf`. Varias funciones de pymupdf no tienen anotaciones
(`Page.get_text` recibe `*args, **kwargs`), así que acá se valida el tipo de cada valor que
devuelven y el resto del pipeline trabaja con `str` e `Image.Image`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pymupdf
from PIL import Image


class PdfReadError(RuntimeError):
    """El archivo no es un PDF legible (corrupto, vacío o cifrado)."""


@contextmanager
def open_pdf(source: Path | bytes) -> Iterator[pymupdf.Document]:
    try:
        if isinstance(source, Path):
            doc = pymupdf.open(source)
        else:
            doc = pymupdf.open(stream=source, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise PdfReadError(str(exc)) from exc
    try:
        if not doc.is_pdf:
            raise PdfReadError("el archivo no es un PDF")
        if doc.needs_pass:
            raise PdfReadError("el PDF está cifrado")
        yield doc
    finally:
        doc.close()


def page_count(doc: pymupdf.Document) -> int:
    count = doc.page_count
    if not isinstance(count, int):
        raise TypeError(f"page_count inesperado: {type(count).__name__}")
    return count


def page_text(doc: pymupdf.Document, index: int) -> str:
    """Texto de la capa de texto de la página `index` (base 0), en orden del flujo de contenido."""
    page = doc.load_page(index)
    text = page.get_text("text")
    if not isinstance(text, str):
        raise TypeError(f"get_text devolvió {type(text).__name__}")
    return text


def render_page_gray(doc: pymupdf.Document, index: int, dpi: int) -> Image.Image:
    """Rasteriza la página completa (imágenes y texto) en escala de grises a `dpi`."""
    page = doc.load_page(index)
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    image.info["dpi"] = (dpi, dpi)
    return image
