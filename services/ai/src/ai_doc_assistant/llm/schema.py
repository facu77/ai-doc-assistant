"""Validación de esquemas para la salida estructurada: solo se aceptan esquemas cerrados.

Regla: la raíz es un objeto, y todo objeto declara sus propiedades y no admite propiedades
libres. Las uniones se escriben con un modelo por variante, discriminadas por un campo
`Literal`, y se envuelven en un modelo contenedor (una unión en la raíz no es un objeto).
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ai_doc_assistant.llm.errors import LLMSchemaError

_ROOT = "(raíz)"


def _child(path: str, name: str) -> str:
    return name if path == _ROOT else f"{path}.{name}"


def _walk(
    node: Mapping[str, object],
    path: str,
    defs: Mapping[str, object],
    seen: set[str],
    problems: list[str],
) -> None:
    ref = node.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", 1)[-1]
        target = defs.get(name)
        if name not in seen and isinstance(target, Mapping):
            seen.add(name)
            _walk(target, path, defs, seen, problems)
        return
    composite = False
    for key in ("anyOf", "oneOf", "allOf"):
        options = node.get(key)
        if isinstance(options, list):
            composite = True
            for option in options:
                if isinstance(option, Mapping):
                    _walk(option, path, defs, seen, problems)
    if composite or "const" in node or "enum" in node:
        return
    kind = node.get("type")
    if kind is None:
        problems.append(f"{path}: acepta cualquier valor (Any); declará su tipo")
    elif kind == "object":
        properties = node.get("properties")
        if not isinstance(properties, Mapping) or not properties:
            problems.append(f"{path}: objeto sin propiedades declaradas (dict libre)")
        additional = node.get("additionalProperties")
        if additional is True or isinstance(additional, Mapping):
            problems.append(f"{path}: admite propiedades libres (additionalProperties)")
        if isinstance(properties, Mapping):
            for name, prop in properties.items():
                if isinstance(prop, Mapping):
                    _walk(prop, _child(path, str(name)), defs, seen, problems)
    elif kind == "array":
        items = node.get("items")
        if isinstance(items, Mapping):
            _walk(items, f"{path}[]", defs, seen, problems)
        else:
            # Una tupla (`tuple[int, str]`) sale como `prefixItems`. `anthropic.transform_schema`
            # no lo soporta y lo deja como texto en la descripción: el array queda sin tipo.
            problems.append(f"{path}: array sin `items` (las tuplas no se soportan; usá una lista)")


def ensure_closed_schema(schema: type[BaseModel]) -> None:
    """Levanta `LLMSchemaError` si `schema` no es cerrado. No llama a ningún proveedor."""
    json_schema: Mapping[str, object] = schema.model_json_schema()
    raw_defs = json_schema.get("$defs")
    defs: Mapping[str, object] = raw_defs if isinstance(raw_defs, Mapping) else {}
    problems: list[str] = []
    if json_schema.get("type") != "object":
        problems.append(f"{_ROOT}: tiene que ser un objeto (envolvé la unión en un modelo)")
    else:
        _walk(json_schema, _ROOT, defs, set(), problems)
    if problems:
        raise LLMSchemaError(
            f"el esquema {schema.__name__} no es cerrado: "
            + "; ".join(problems)
            + ". Declará un modelo Pydantic por herramienta, sin dicts libres."
        )
