"""Reporte de ingesta: totales calculados a partir de los documentos, en JSON y Markdown."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from statistics import fmean

from ingest.models import Category, CategoryCER, DocumentReport, ExtractionMethod, IngestReport

JSON_REPORT_NAME = "ingest_report.json"
MARKDOWN_REPORT_NAME = "ingest_report.md"

CATEGORY_ORDER: tuple[Category, ...] = ("native", "clean_scan", "noisy_scan", "mixed")
CATEGORY_LABELS: dict[Category, str] = {
    "native": "Nativo",
    "clean_scan": "Escaneo limpio",
    "noisy_scan": "Escaneo ruidoso",
    "mixed": "Mixto",
}
METHOD_ORDER: tuple[ExtractionMethod, ...] = ("native", "ocr")


def build_report(
    documents: Sequence[DocumentReport],
    *,
    pipeline_version: str,
    ocr_engine: str,
    config_hash: str,
    total_seconds: float,
    pages_processed: int,
) -> IngestReport:
    """Arma el reporte. Todos los totales salen de sumar `documents`, nunca de otra fuente."""
    statuses = Counter(doc.status for doc in documents)
    methods = Counter(page.method for doc in documents for page in doc.pages)

    by_category: dict[Category, CategoryCER] = {}
    for category in CATEGORY_ORDER:
        cers = [d.cer for d in documents if d.category == category and d.cer is not None]
        if cers:
            by_category[category] = CategoryCER(
                documents=len(cers), mean_cer=fmean(cers), max_cer=max(cers)
            )
    all_cers = [d.cer for d in documents if d.cer is not None]

    return IngestReport(
        pipeline_version=pipeline_version,
        ocr_engine=ocr_engine,
        config_hash=config_hash,
        documents_total=len(documents),
        processed=statuses["processed"],
        skipped=statuses["skipped"],
        errors=statuses["error"],
        warnings=sum(1 for d in documents if d.status != "error" and d.error is not None),
        pages_total=sum(doc.page_count for doc in documents),
        pages_by_method={method: methods[method] for method in METHOD_ORDER},
        cer_by_category=by_category,
        mean_cer=fmean(all_cers) if all_cers else None,
        total_seconds=total_seconds,
        pages_processed=pages_processed,
        seconds_per_page=total_seconds / pages_processed if pages_processed else None,
        documents=list(documents),
    )


def _pct(value: float | None) -> str:
    return "n/d" if value is None else f"{value * 100:.2f} %"


def _methods(doc: DocumentReport) -> str:
    return " ".join("N" if page.method == "native" else "O" for page in doc.pages) or "-"


def render_markdown(report: IngestReport) -> str:
    per_page = "n/d" if report.seconds_per_page is None else f"{report.seconds_per_page:.3f} s"
    lines = [
        "# Reporte de ingesta",
        "",
        "## Resumen",
        "",
        "| Campo | Valor |",
        "| --- | --- |",
        f"| Versión del pipeline | {report.pipeline_version} |",
        f"| Motor de OCR | {report.ocr_engine} |",
        f"| Huella de configuración | `{report.config_hash[:12]}` |",
        f"| Documentos | {report.documents_total} |",
        f"| Procesados | {report.processed} |",
        f"| Omitidos (sin cambios) | {report.skipped} |",
        f"| Con error | {report.errors} |",
        f"| Con aviso | {report.warnings} |",
        f"| Páginas | {report.pages_total} |",
        f"| CER medio (documentos con referencia) | {_pct(report.mean_cer)} |",
        f"| Tiempo total | {report.total_seconds:.2f} s |",
        f"| Páginas procesadas en esta corrida | {report.pages_processed} |",
        f"| Tiempo por página procesada | {per_page} |",
        "",
        "## Páginas por método",
        "",
        "| Método | Páginas |",
        "| --- | --- |",
        *(f"| `{method}` | {count} |" for method, count in report.pages_by_method.items()),
        "",
        "## CER por categoría",
        "",
    ]
    if report.cer_by_category:
        lines += [
            "| Categoría | Documentos | CER medio | CER máximo |",
            "| --- | --- | --- | --- |",
        ]
        lines += [
            f"| {CATEGORY_LABELS[category]} | {stats.documents} | {_pct(stats.mean_cer)} "
            f"| {_pct(stats.max_cer)} |"
            for category, stats in report.cer_by_category.items()
        ]
    else:
        lines.append("Sin texto de referencia: no se midió el CER.")
    lines += [
        "",
        "## Documentos",
        "",
        "Método por página: `N` nativa, `O` OCR.",
        "",
        "| Documento | Categoría | Estado | Páginas | Método por página | CER | Tiempo |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for doc in report.documents:
        category = CATEGORY_LABELS[doc.category] if doc.category else "-"
        lines.append(
            f"| {doc.source} | {category} | {doc.status} | {doc.page_count} | {_methods(doc)} "
            f"| {_pct(doc.cer)} | {doc.seconds:.2f} s |"
        )
    lines += ["", "## Errores", ""]
    failed = [doc for doc in report.documents if doc.status == "error"]
    if failed:
        lines += [
            f"- `{doc.source}`: `{doc.error}`. {doc.error_detail or ''}".rstrip() for doc in failed
        ]
    else:
        lines.append("Sin errores.")
    lines += [
        "",
        "## Avisos",
        "",
        "Documentos ingeridos igual, con un aviso (por ejemplo, sin CER).",
        "",
    ]
    warned = [doc for doc in report.documents if doc.status != "error" and doc.error]
    if warned:
        lines += [
            f"- `{doc.source}` ({doc.status}): `{doc.error}`. {doc.error_detail}" for doc in warned
        ]
    else:
        lines.append("Sin avisos.")
    return "\n".join(lines) + "\n"


def write_report(report: IngestReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    md_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
