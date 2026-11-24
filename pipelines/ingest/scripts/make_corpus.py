"""Genera el corpus ficticio. Equivale a `uv run make-corpus`.

Uso: `uv run python scripts/make_corpus.py --out ../../data/corpus`
"""

from ingest.corpus.generate import main

if __name__ == "__main__":
    raise SystemExit(main())
