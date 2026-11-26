"""Proveedor `fake`: determinista, sin red y sin clave. Es el de los tests y la CI."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncGenerator, Mapping

from ai_doc_assistant.llm.models import Usage
from ai_doc_assistant.llm.provider import (
    LLMRequest,
    ProviderResult,
    StreamEnd,
    StreamEvent,
    TextDelta,
)

FAKE_MODEL = "fake-llm"


def _count_tokens(text: str) -> int:
    # Aproximación: una "palabra" por token. Alcanza para que el uso no sea cero.
    return max(1, len(text.split()))


def _example_for(schema: Mapping[str, object], defs: Mapping[str, object]) -> object:
    """Un valor mínimo que cumple el JSON Schema (subconjunto que genera Pydantic)."""
    ref = schema.get("$ref")
    if isinstance(ref, str):
        target = defs.get(ref.rsplit("/", 1)[-1])
        return _example_for(target, defs) if isinstance(target, Mapping) else None
    if "const" in schema:
        return schema["const"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    for key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(key)
        if isinstance(options, list) and options and isinstance(options[0], Mapping):
            return _example_for(options[0], defs)
    kind = schema.get("type")
    if kind == "object":
        properties = schema.get("properties")
        required = schema.get("required")
        result: dict[str, object] = {}
        if isinstance(properties, Mapping) and isinstance(required, list):
            for name in required:
                prop = properties.get(name)
                if isinstance(name, str) and isinstance(prop, Mapping):
                    result[name] = _example_for(prop, defs)
        return result
    examples: dict[object, object] = {
        "string": "fake",
        "integer": 0,
        "number": 0.0,
        "boolean": False,
        "array": [],
        "null": None,
    }
    return examples.get(kind)


class FakeLLMProvider:
    """Responde siempre lo mismo para el mismo prompt, sin repetir el prompt."""

    name = "fake"
    model = FAKE_MODEL

    def _text(self, request: LLMRequest) -> str:
        if request.output_schema is not None:
            schema = request.output_schema.model_json_schema()
            defs = schema.get("$defs", {})
            return json.dumps(_example_for(schema, defs if isinstance(defs, Mapping) else {}))
        digest = hashlib.sha256(request.prompt.encode()).hexdigest()[:12]
        return f"Respuesta simulada del proveedor fake (huella {digest})."

    def _usage(self, request: LLMRequest, text: str) -> Usage:
        prompt_tokens = _count_tokens(request.prompt) + _count_tokens(request.system or "")
        return Usage(input_tokens=prompt_tokens, output_tokens=_count_tokens(text))

    async def generate(self, request: LLMRequest) -> ProviderResult:
        text = self._text(request)
        return ProviderResult(text=text, usage=self._usage(request, text))

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamEvent, None]:
        text = self._text(request)
        words = text.split(" ")
        for index, word in enumerate(words):
            yield TextDelta(text=word if index == len(words) - 1 else word + " ")
        yield StreamEnd(usage=self._usage(request, text))

    async def aclose(self) -> None:
        """Nada que cerrar: no hay conexiones."""
