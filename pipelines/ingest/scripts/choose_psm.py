"""Aplica la regla preregistrada de selección del psm (design.md) a tres reportes.

Uso: `uv run python scripts/choose_psm.py --psm3 a.json --psm4 b.json --psm6 c.json`
"""

from ingest.psm_selection import main

if __name__ == "__main__":
    raise SystemExit(main())
