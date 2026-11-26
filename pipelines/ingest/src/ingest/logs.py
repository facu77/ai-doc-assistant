"""Logs estructurados en JSON (una línea por evento) hacia stderr.

Solo se loguean metadatos (nombre de archivo, estado, páginas, tiempo), nunca el texto.
"""

from __future__ import annotations

import json
import logging
import sys

_STANDARD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update({k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS})
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("ingest")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False
