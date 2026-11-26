"""Adaptador de pymupdf: abrir un PDF, leer la capa de texto y rasterizar una página.

Es el único módulo que importa `pymupdf`. pymupdf 1.28 trae `py.typed`, pero `mypy` ve como
`Any` casi todo lo que sale de un `Document`: `load_page` no tiene anotaciones, así que la
página, su `rect`, `get_text(...)`, el `Pixmap` de `get_pixmap` (y su `width`, `height` y
`samples`), `page_count`, `is_pdf` y `needs_pass` llegan sin tipo (verificado con
`reveal_type`). Por eso cada valor pasa por `_typed`, que comprueba el tipo en tiempo de
ejecución antes de entregarlo al resto del pipeline.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pymupdf
from PIL import Image


class PdfReadError(RuntimeError):
    """El archivo no es un PDF legible (corrupto, vacío o cifrado) o pymupdf falló al leerlo."""


@contextmanager
def _library_errors(what: str) -> Iterator[None]:
    """Traduce a `PdfReadError` lo que lanzan pymupdf y Pillow, y nada más.

    Así el pipeline atrapa solo `PdfReadError`: un `ValueError` de código propio (por
    ejemplo, una `ValidationError` al construir un modelo) no se disfraza de archivo ilegible.
    `TypeError` incluye lo que levanta `_typed` cuando pymupdf devuelve un tipo inesperado.
    """
    try:
        yield
    except PdfReadError:
        raise
    except (RuntimeError, ValueError, TypeError) as exc:
        raise PdfReadError(f"{what}: {type(exc).__name__}: {exc}") from exc


def _typed[T](value: object, expected: type[T], what: str) -> T:
    if not isinstance(value, expected):
        raise TypeError(f"pymupdf devolvió {type(value).__name__} para {what}")
    return value


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
        with _library_errors("encabezado del PDF"):
            # Se validan como int: en 1.28.2 `needs_pass` devuelve 0/1, no bool.
            is_pdf = _typed(doc.is_pdf, int, "is_pdf")
            needs_pass = _typed(doc.needs_pass, int, "needs_pass")
        if not is_pdf:
            raise PdfReadError("el archivo no es un PDF")
        if needs_pass:
            raise PdfReadError("el PDF está cifrado")
        yield doc
    finally:
        doc.close()


def page_count(doc: pymupdf.Document) -> int:
    with _library_errors("page_count"):
        return _typed(doc.page_count, int, "page_count")


def _page(doc: pymupdf.Document, index: int) -> pymupdf.Page:
    return _typed(doc.load_page(index), pymupdf.Page, "load_page")


def page_text(doc: pymupdf.Document, index: int) -> str:
    """Texto de la capa de texto de la página `index` (base 0), en orden del flujo de contenido."""
    with _library_errors(f"texto de la página {index + 1}"):
        return _typed(_page(doc, index).get_text("text"), str, "get_text")


def page_size_points(doc: pymupdf.Document, index: int) -> tuple[float, float]:
    """Ancho y alto de la página en puntos (1/72 de pulgada)."""
    with _library_errors(f"tamaño de la página {index + 1}"):
        rect = _typed(_page(doc, index).rect, pymupdf.Rect, "rect")
        width = _typed(rect.width, float, "rect.width")
        height = _typed(rect.height, float, "rect.height")
    return width, height


def render_page_gray(doc: pymupdf.Document, index: int, dpi: int) -> Image.Image:
    """Rasteriza la página completa (imágenes y texto) en escala de grises a `dpi`."""
    with _library_errors(f"rasterizado de la página {index + 1}"):
        pix = _typed(
            _page(doc, index).get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY),
            pymupdf.Pixmap,
            "pixmap",
        )
        size = (_typed(pix.width, int, "pixmap.width"), _typed(pix.height, int, "pixmap.height"))
        image = Image.frombytes("L", size, _typed(pix.samples, bytes, "pixmap.samples"))
    image.info["dpi"] = (dpi, dpi)
    return image
