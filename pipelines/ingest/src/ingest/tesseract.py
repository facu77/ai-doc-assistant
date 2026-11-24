"""Adaptador de Tesseract detrás del Protocol `OCREngine`. Único módulo que importa pytesseract.

pytesseract es un envoltorio del binario `tesseract`: guarda la imagen en un archivo temporal,
lanza el proceso y lee la salida. Requiere `tesseract-ocr` y el idioma `spa` instalados.
"""

from __future__ import annotations

from functools import cached_property

import pytesseract
from PIL import Image

from ingest.ocr import OCRError
from ingest.settings import IngestSettings


class TesseractEngine:
    def __init__(self, settings: IngestSettings | None = None) -> None:
        settings = settings or IngestSettings()
        self._lang = settings.ocr_lang
        self._timeout_s = settings.ocr_timeout_s
        # psm 3 (por defecto): segmentación automática en bloques. Con tablas puede leer una
        # columna entera antes que la otra (ver REPORT.md).
        self._psm = settings.ocr_psm

    @cached_property
    def name(self) -> str:
        try:
            version = str(pytesseract.get_tesseract_version())
        except (pytesseract.TesseractNotFoundError, SystemExit):
            # get_tesseract_version() hace SystemExit si no entiende la versión.
            version = "no disponible"
        return f"tesseract {version} ({self._lang}, psm {self._psm})"

    def recognize(self, image: Image.Image, *, dpi: int) -> str:
        # convert() devuelve una imagen sin `format`: pytesseract la guarda como PNG (sin
        # pérdida). Si se le pasa una imagen abierta desde un JPEG, la re-codifica en JPEG.
        grayscale = image.convert("L")
        try:
            return pytesseract.image_to_string(
                grayscale,
                lang=self._lang,
                config=f"--dpi {dpi} --psm {self._psm}",
                timeout=self._timeout_s,
            )
        except (pytesseract.TesseractError, pytesseract.TesseractNotFoundError) as exc:
            raise OCRError(f"tesseract falló: {exc}") from exc
        except RuntimeError as exc:  # pytesseract lanza RuntimeError genérico en el timeout
            raise OCRError(f"tesseract excedió {self._timeout_s} s") from exc
