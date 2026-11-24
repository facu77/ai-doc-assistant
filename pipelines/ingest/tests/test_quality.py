"""Requirement: Calidad de OCR medida (cálculo del CER y normalización del texto).

Los umbrales de CER sobre el corpus real están en `test_integration_tesseract.py`.
"""

from __future__ import annotations

import pytest

from ingest.normalize import normalize_for_cer, normalize_text
from ingest.quality import cer


def test_normalize_text_aplica_nfc_y_colapsa_espacios_por_linea() -> None:
    # "a" + acento combinante (NFD) -> "á" precompuesta (NFC).
    raw = "  Pa\u0301gina   uno\t\u00a0 \n\n\n\n  dos  tres  \n\n"
    assert normalize_text(raw) == "Página uno\n\ndos tres"


def test_normalize_for_cer_colapsa_todos_los_blancos() -> None:
    assert normalize_for_cer("Destino\nMonto  diario\n\n") == "Destino Monto diario"
    assert normalize_for_cer("Pa\u0301gina") == "Página"


def test_cer_es_la_distancia_de_edicion_sobre_la_longitud_de_la_referencia() -> None:
    # Una sustitución sobre 10 caracteres (la mayúscula cuenta como error).
    assert cer("Hola mundo", "hola mundo") == pytest.approx(0.1)
    # Los saltos de línea y espacios extra no cuentan: el CER se mide sobre texto normalizado.
    assert cer("Hola\nmundo", "Hola   mundo") == 0.0
    # Inserciones: el CER puede superar 1.
    assert cer("ab", "abcdef") == pytest.approx(2.0)


def test_cer_con_referencia_vacia_no_se_puede_medir() -> None:
    with pytest.raises(ValueError, match="referencia vacía"):
        cer("  \n ", "algo")
