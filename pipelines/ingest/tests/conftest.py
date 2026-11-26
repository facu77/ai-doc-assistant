"""Fixtures: archivos de prueba construidos en `tmp_path` y la ubicación del corpus versionado."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from tests.fakes import FakeOCREngine

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = REPO_ROOT / "data" / "corpus"
VALIDATION_DIR = REPO_ROOT / "data" / "corpus-validation"

NATIVE_PARAGRAPH = (
    "Acme S.A. otorga 14 días corridos de vacaciones con menos de 5 años de antigüedad, "
    "según la política de licencias vigente desde marzo de 2026."
)


def text_image(lines: Sequence[str], *, size: tuple[int, int] = (1240, 400)) -> Image.Image:
    """Imagen en escala de grises con texto negro sobre blanco (para simular un escaneo)."""
    image = Image.new("L", size, color=255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    for index, line in enumerate(lines):
        draw.text((40, 40 + index * 60), line, fill=0, font=font)
    return image


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def write_pdf(path: Path, pages: Sequence[str | Image.Image], *, stamp: str | None = None) -> Path:
    """Escribe un PDF. Cada página es texto nativo (`str`) o una imagen a página completa.

    `stamp` agrega una línea con capa de texto sobre cada página de imagen.
    """
    canvas = Canvas(str(path), pagesize=A4, invariant=1)
    width, height = A4
    for page in pages:
        if isinstance(page, str):
            canvas.setFont("Helvetica", 11)
            text = canvas.beginText(72, height - 72)
            for line in page.splitlines():
                text.textLine(line)
            canvas.drawText(text)
        else:
            canvas.drawImage(ImageReader(BytesIO(_png_bytes(page))), 0, 0, width, height)
            if stamp is not None:
                canvas.setFont("Helvetica-Bold", 10)
                canvas.drawString(72, 50, stamp)
        canvas.showPage()
    canvas.save()
    return path


def native_page(number: int) -> str:
    return f"Página {number} de la política de prueba.\n{NATIVE_PARAGRAPH}"


@pytest.fixture
def fake_ocr() -> FakeOCREngine:
    return FakeOCREngine()


@pytest.fixture
def in_dir(tmp_path: Path) -> Path:
    path = tmp_path / "in"
    path.mkdir()
    return path


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "out"


@pytest.fixture
def corpus_dir() -> Path:
    if not CORPUS_DIR.is_dir():
        pytest.fail(f"no existe el corpus versionado en {CORPUS_DIR}; corré `uv run make-corpus`")
    return CORPUS_DIR
