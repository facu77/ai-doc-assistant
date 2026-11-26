"""Adaptador de Tesseract sin el binario: se reemplaza `pytesseract.image_to_string`.

Hallazgo 3 de la revisión: el adaptador traduce los fallos de pytesseract a `OCRError`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

import pytesseract
import pytest
from PIL import Image

from ingest.ocr import OCRError
from ingest.settings import IngestSettings
from ingest.tesseract import TesseractEngine


@dataclass
class _Recorder:
    result: str = "texto"
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(self, image: Image.Image, **kwargs: object) -> str:
        self.calls.append({"mode": image.mode, "format": image.format, **kwargs})
        return self.result


def _jpeg_image() -> Image.Image:
    buffer = BytesIO()
    Image.new("L", (40, 20), color=255).save(buffer, format="JPEG")
    buffer.seek(0)
    return Image.open(buffer)


def test_pasa_idiomas_dpi_psm_y_timeout_a_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder(result="Hola")
    monkeypatch.setattr(pytesseract, "image_to_string", recorder)
    engine = TesseractEngine(IngestSettings(ocr_lang="spa", ocr_psm=4, ocr_timeout_s=7))

    text = engine.recognize(_jpeg_image(), dpi=300)

    assert text == "Hola"
    [call] = recorder.calls
    assert call["lang"] == "spa"
    assert call["config"] == "--dpi 300 --psm 4"
    assert call["timeout"] == 7
    # La imagen llega en escala de grises y sin formato: pytesseract la guarda en PNG, no
    # re-codifica en JPEG.
    assert call["mode"] == "L"
    assert call["format"] is None


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(RuntimeError("Tesseract process timeout"), id="timeout"),
        pytest.param(pytesseract.TesseractError(1, "Failed loading language 'spa'"), id="error"),
        pytest.param(pytesseract.TesseractNotFoundError(), id="no-instalado"),
    ],
)
def test_los_fallos_de_pytesseract_se_traducen_a_ocr_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def failing(image: Image.Image, **kwargs: object) -> str:
        raise error

    monkeypatch.setattr(pytesseract, "image_to_string", failing)

    with pytest.raises(OCRError):
        TesseractEngine().recognize(Image.new("L", (10, 10), color=255), dpi=300)
