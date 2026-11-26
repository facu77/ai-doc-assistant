"""Adaptador de Tesseract detrás del Protocol `OCREngine`. Único módulo que importa pytesseract.

pytesseract es un envoltorio del binario `tesseract`: guarda la imagen en un archivo temporal,
lanza el proceso y lee la salida. Requiere `tesseract-ocr` y el idioma `spa` instalados.
"""

from __future__ import annotations

import shutil
import subprocess
from functools import cached_property

import pytesseract
from PIL import Image

from ingest.ocr import OCRError
from ingest.settings import IngestSettings

VERSION_TIMEOUT_S = 10.0
"""`pytesseract.get_tesseract_version()` llama a `check_output` sin timeout: si el binario
se cuelga, se cuelga la ingesta. Por eso la versión se consulta acá, con timeout."""

UNAVAILABLE = "tesseract no disponible"


def _tesseract_version() -> str:
    """Primera línea de `tesseract --version` (p. ej. "tesseract 5.3.4"), con timeout."""
    binary = shutil.which("tesseract")
    if binary is None:
        return UNAVAILABLE
    try:
        # Binario resuelto con `which` y argumentos fijos: no entra nada del usuario.
        result = subprocess.run(  # noqa: S603
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=VERSION_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return UNAVAILABLE
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0].strip() if lines else UNAVAILABLE


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
        return f"{_tesseract_version()} ({self._lang}, psm {self._psm})"

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
