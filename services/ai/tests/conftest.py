from __future__ import annotations

import os

import pytest

_CONFIG_PREFIXES = ("LLM_", "EMBEDDINGS_")
_CONFIG_NAMES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Borra la configuración de LLM/embeddings del entorno real para que el test la controle."""
    for name in list(os.environ):
        if name.startswith(_CONFIG_PREFIXES) or name in _CONFIG_NAMES:
            monkeypatch.delenv(name, raising=False)
    return monkeypatch
