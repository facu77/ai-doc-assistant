"""CER (Character Error Rate) contra el texto de referencia.

CER = (sustituciones + borrados + inserciones) / caracteres de la referencia, es decir la
distancia de Levenshtein a nivel de caracteres dividida por la longitud de la referencia.
Puede superar 1 si el OCR inventa mucho texto.
"""

from __future__ import annotations

import jiwer

from ingest.normalize import normalize_for_cer


def cer(reference: str, hypothesis: str) -> float:
    ref = normalize_for_cer(reference)
    if not ref:
        raise ValueError("referencia vacía: el CER no está definido")
    hyp = normalize_for_cer(hypothesis)
    if not hyp:
        return 1.0  # todo borrado: N borrados / N caracteres
    return float(jiwer.cer(reference=ref, hypothesis=hyp))
