# Stub mínimo de pytesseract 0.3.13 (la librería no trae tipos ni hay stubs en typeshed).
# Cubre solo los símbolos que usa ingest/tesseract.py. Firmas copiadas de
# .venv/lib/python3.12/site-packages/pytesseract/pytesseract.py (líneas 98-111, 446 y 473).
# Si se actualiza pytesseract, revisar estas firmas contra el código instalado.

from packaging.version import Version
from PIL import Image

class TesseractError(RuntimeError):
    status: int
    message: str
    def __init__(self, status: int, message: str) -> None: ...

class TesseractNotFoundError(OSError):
    def __init__(self) -> None: ...

def get_tesseract_version() -> Version: ...
def image_to_string(
    image: Image.Image | str,
    lang: str | None = None,
    config: str = "",
    nice: int = 0,
    output_type: str = "string",
    timeout: float = 0,
) -> str: ...
