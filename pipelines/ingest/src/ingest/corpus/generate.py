"""Generador reproducible del corpus ficticio (20 documentos y su texto de referencia).

Uso: `uv run make-corpus --out ../../data/corpus [--seed 20261124]`.

Cómo se simula un escaneo (design.md): se dibuja la página con reportlab, se rasteriza a
300 dpi, se rota, se le suma ruido gaussiano y se baja a 200 dpi. Los parámetros de cada
perfil (`SCAN_PROFILES`) se fijaron ANTES de medir el CER y no se ajustan para pasar los
umbrales de la spec.
"""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen.canvas import Canvas

from ingest.corpus.content import DOCUMENTS, DocSpec, Heading, PageSpec, Para, Row
from ingest.models import (
    CorpusEntry,
    CorpusManifest,
    GroundTruthDocument,
    GroundTruthPage,
    ScanProfile,
)
from ingest.pdf import open_pdf, render_page_gray

GENERATOR_VERSION = "1"
DEFAULT_SEED = 20261124
GROUND_TRUTH_DIR = "ground_truth"
MANIFEST_NAME = "manifest.json"

ScanCategory = Literal["clean_scan", "noisy_scan"]

# Fijados antes de medir (ver proposal.md, "Decisiones tomadas", punto 2).
SCAN_PROFILES: dict[ScanCategory, ScanProfile] = {
    "clean_scan": ScanProfile(
        min_rotation_deg=0.0,
        max_rotation_deg=0.5,
        noise_sigma=10.0,
        render_dpi=300,
        output_dpi=200,
        jpeg_quality=85,
    ),
    "noisy_scan": ScanProfile(
        min_rotation_deg=1.0,
        max_rotation_deg=2.0,
        noise_sigma=35.0,
        render_dpi=300,
        output_dpi=200,
        jpeg_quality=60,
    ),
}

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 72.0
TEXT_WIDTH = PAGE_WIDTH - 2 * MARGIN
BODY_FONT, BODY_SIZE, BODY_LEADING = "Helvetica", 11.0, 15.0
HEAD_FONT, HEAD_SIZE, HEAD_LEADING = "Helvetica-Bold", 13.0, 20.0
PARAGRAPH_GAP = 5.0
TABLE_COLUMN_X = (MARGIN, MARGIN + 250.0)
STAMP_FONT, STAMP_SIZE = "Helvetica-Bold", 10.0
STAMP_Y = 50.0


@dataclass(frozen=True)
class _Line:
    x: float
    y: float
    font: str
    size: float
    text: str


def layout_page(page: PageSpec) -> tuple[list[_Line], list[str]]:
    """Ubica cada línea en la página y devuelve también las líneas de referencia.

    La referencia de una fila de tabla son sus celdas separadas por un espacio: las tablas
    se tratan como texto plano (limitación documentada).
    """
    lines: list[_Line] = []
    reference: list[str] = []
    y = PAGE_HEIGHT - MARGIN
    for block in page.blocks:
        match block:
            case Heading(text=text):
                y -= HEAD_LEADING
                for part in simpleSplit(text, HEAD_FONT, HEAD_SIZE, TEXT_WIDTH):
                    lines.append(_Line(MARGIN, y, HEAD_FONT, HEAD_SIZE, part))
                    reference.append(part)
                    y -= HEAD_LEADING
                y += HEAD_LEADING - PARAGRAPH_GAP
            case Para(text=text):
                y -= BODY_LEADING
                for part in simpleSplit(text, BODY_FONT, BODY_SIZE, TEXT_WIDTH):
                    lines.append(_Line(MARGIN, y, BODY_FONT, BODY_SIZE, part))
                    reference.append(part)
                    y -= BODY_LEADING
                y += BODY_LEADING - PARAGRAPH_GAP
            case Row(cells=cells):
                y -= BODY_LEADING
                for x, cell in zip(TABLE_COLUMN_X, cells, strict=True):
                    lines.append(_Line(x, y, BODY_FONT, BODY_SIZE, cell))
                reference.append(" ".join(cells))
        if y < MARGIN:
            raise ValueError("el contenido no entra en la página")
    if page.stamp is not None:
        reference.append(page.stamp)
    return lines, reference


def _draw_lines(canvas: Canvas, lines: Sequence[_Line]) -> None:
    for line in lines:
        canvas.setFont(line.font, line.size)
        canvas.drawString(line.x, line.y, line.text)


def _page_as_pdf(lines: Sequence[_Line]) -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=A4, invariant=1)
    _draw_lines(canvas, lines)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def simulate_scan(lines: Sequence[_Line], profile: ScanProfile, rng: np.random.Generator) -> bytes:
    """Rasteriza, rota, agrega ruido y baja la resolución. Devuelve un JPEG en escala de grises."""
    with open_pdf(_page_as_pdf(lines)) as doc:
        image = render_page_gray(doc, 0, profile.render_dpi)

    magnitude = rng.uniform(profile.min_rotation_deg, profile.max_rotation_deg)
    sign = 1.0 if rng.random() < 0.5 else -1.0
    image = image.rotate(
        sign * magnitude, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=255
    )

    pixels = np.asarray(image, dtype=np.float32)
    noisy = pixels + rng.normal(0.0, profile.noise_sigma, size=pixels.shape)
    image = Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8))

    scale = profile.output_dpi / profile.render_dpi
    size = (round(image.width * scale), round(image.height * scale))
    image = image.resize(size, resample=Image.Resampling.LANCZOS)

    buffer = BytesIO()
    dpi = (profile.output_dpi, profile.output_dpi)
    image.save(buffer, format="JPEG", quality=profile.jpeg_quality, dpi=dpi)
    return buffer.getvalue()


def _profile_for(doc: DocSpec) -> ScanProfile:
    # Las páginas escaneadas de los documentos mixtos usan el perfil limpio.
    return SCAN_PROFILES["noisy_scan" if doc.category == "noisy_scan" else "clean_scan"]


def render_document(doc: DocSpec, rng: np.random.Generator) -> tuple[bytes, list[list[str]]]:
    """Devuelve los bytes del archivo y las líneas de referencia de cada página."""
    profile = _profile_for(doc)
    layouts = [layout_page(page) for page in doc.pages]

    if doc.filename.endswith(".jpg"):
        if len(doc.pages) != 1 or doc.pages[0].kind != "scan":
            raise ValueError(f"{doc.filename}: una imagen suelta es una sola página escaneada")
        lines, reference = layouts[0]
        return simulate_scan(lines, profile, rng), [reference]

    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=A4, invariant=1)
    canvas.setTitle(doc.title)
    canvas.setAuthor("Acme S.A. (empresa ficticia)")
    for page, (lines, _) in zip(doc.pages, layouts, strict=True):
        if page.kind == "native":
            _draw_lines(canvas, lines)
        else:
            jpeg = simulate_scan(lines, profile, rng)
            canvas.drawImage(ImageReader(BytesIO(jpeg)), 0, 0, PAGE_WIDTH, PAGE_HEIGHT)
            if page.stamp is not None:
                canvas.setFillColorRGB(0.1, 0.1, 0.45)
                canvas.setFont(STAMP_FONT, STAMP_SIZE)
                canvas.drawString(MARGIN, STAMP_Y, page.stamp)
                canvas.setFillColorRGB(0, 0, 0)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue(), [reference for _, reference in layouts]


def generate_corpus(out_dir: Path, seed: int = DEFAULT_SEED) -> CorpusManifest:
    """Escribe los 20 documentos en `out_dir` y su referencia en `out_dir/ground_truth/`."""
    gt_dir = out_dir / GROUND_TRUTH_DIR
    gt_dir.mkdir(parents=True, exist_ok=True)
    entries: list[CorpusEntry] = []
    for index, doc in enumerate(DOCUMENTS):
        # Un generador por documento: cambiar un documento no altera el ruido de los demás.
        rng = np.random.default_rng([seed, index])
        data, references = render_document(doc, rng)
        (out_dir / doc.filename).write_bytes(data)
        truth = GroundTruthDocument(
            source=doc.filename,
            category=doc.category,
            title=doc.title,
            pages=[
                GroundTruthPage(page_number=number, kind=page.kind, text="\n".join(reference))
                for number, (page, reference) in enumerate(
                    zip(doc.pages, references, strict=True), start=1
                )
            ],
        )
        (gt_dir / f"{doc.filename}.json").write_text(
            truth.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        entries.append(
            CorpusEntry(
                source=doc.filename,
                category=doc.category,
                page_count=len(doc.pages),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    manifest = CorpusManifest(
        seed=seed,
        generator_version=GENERATOR_VERSION,
        scan_profiles=dict(SCAN_PROFILES),
        documents=entries,
    )
    (gt_dir / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera el corpus ficticio de Acme S.A.")
    parser.add_argument("--out", type=Path, required=True, help="Directorio de salida.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Semilla del ruido.")
    args = parser.parse_args(argv)
    out_dir: Path = args.out
    seed: int = args.seed
    manifest = generate_corpus(out_dir, seed)
    print(f"{len(manifest.documents)} documentos en {out_dir} (semilla {seed})")
    return 0
