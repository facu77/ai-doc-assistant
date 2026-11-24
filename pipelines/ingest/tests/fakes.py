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
