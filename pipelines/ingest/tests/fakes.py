"""Motores de OCR falsos para la suite rápida (sin Tesseract).

Son fakes con comportamiento, no mocks: registran cada imagen que reciben (tamaño y dpi), así
los tests verifican QUÉ páginas pasaron por OCR y a qué resolución, que es la lógica bajo prueba.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

from ingest.ocr import OCRError


@dataclass(frozen=True)
class OCRCall:
    width: int
    height: int
    dpi: int


@dataclass
class FakeOCREngine:
    """Devuelve un texto distinto en cada llamada: `<texto> <número de llamada>`."""

    text: str = "Texto reconocido por el OCR falso, llamada"
    name: str = "fake-ocr"
    calls: list[OCRCall] = field(default_factory=list)

    def recognize(self, image: Image.Image, *, dpi: int) -> str:
        self.calls.append(OCRCall(width=image.width, height=image.height, dpi=dpi))
        return f"{self.text} {len(self.calls)}"


@dataclass
class FailingOCREngine:
    """Falla siempre, como un Tesseract sin el idioma instalado o que excede el timeout."""

    name: str = "failing-ocr"
    calls: int = 0

    def recognize(self, image: Image.Image, *, dpi: int) -> str:
        self.calls += 1
        raise OCRError("motor de OCR caído (falso)")


@dataclass
class DirtyTextOCREngine:
    """Devuelve texto con la suciedad típica de Tesseract: blancos, tabs, líneas vacías y el
    salto de página (form feed, \\x0c) que agrega al final."""

    text: str = "  Página\t uno \n\n\n\x0c"
    name: str = "dirty-ocr"

    def recognize(self, image: Image.Image, *, dpi: int) -> str:
        return self.text


@dataclass
class PixelMeanOCREngine:
    """Sensible a la imagen: "lee" el brillo medio de los píxeles que recibe.

    Detecta si el pipeline rasteriza la página equivocada o manda una imagen en blanco,
    cosas que un fake que ignora la imagen no puede ver.
    """

    name: str = "pixel-mean-ocr"
    means: list[float] = field(default_factory=list)

    def recognize(self, image: Image.Image, *, dpi: int) -> str:
        gray = image.convert("L")
        histogram = gray.histogram()
        mean = sum(value * count for value, count in enumerate(histogram)) / sum(histogram)
        self.means.append(mean)
        return f"media {mean:.1f}"
