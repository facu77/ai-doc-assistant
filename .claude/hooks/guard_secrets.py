"""PreToolUse hook: bloquea escrituras con patrones de claves o sobre archivos .env.

Recibe el JSON del evento por stdin. Para bloquear, sale con código 2 y escribe el
motivo en stderr; Claude Code muestra ese texto como razón de la denegación.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import PurePath

ALLOWED_ENV_FILES = {".env.example", ".env.sample", ".env.template"}

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "clave de Anthropic": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "clave estilo OpenAI": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "token de GitHub": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})"),
    "token de Slack": re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "clave privada": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "secreto asignado en el código": re.compile(
        r"""(?ix)
        \b(?:api[_-]?key|secret|password|passwd|token|access[_-]?key)\b
        \s*[:=]\s*
        ["'](?!\s*$)(?!.*(?:changeme|example|dummy|fake|placeholder|xxx|<))[^"'\s]{16,}["']
        """
    ),
}


def block(reason: str) -> None:
    print(f"guard_secrets: {reason}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return  # entrada inesperada: no decidir, sigue el flujo normal de permisos

    tool_input = event.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or "")
    name = PurePath(file_path).name

    if (name == ".env" or name.startswith(".env.")) and name not in ALLOWED_ENV_FILES:
        block(f"no se permite escribir {name}; los secretos van fuera del repo (ver .env.example).")

    content = "\n".join(
        str(tool_input.get(key) or "") for key in ("content", "new_string")
    )
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(content):
            block(
                f"el contenido para {file_path or 'el archivo'} parece incluir un/a {label}. "
                "Usá variables de entorno y datos ficticios."
            )


if __name__ == "__main__":
    main()
