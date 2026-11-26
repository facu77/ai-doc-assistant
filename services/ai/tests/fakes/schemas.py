"""Esquemas cerrados de prueba: una llamada a herramienta como unión discriminada.

Cada herramienta declara sus argumentos con un modelo propio. La unión va envuelta en un
modelo contenedor porque la raíz de la salida estructurada tiene que ser un objeto: con una
unión en la raíz, `anthropic.transform_schema` devuelve un `anyOf` sin `type: object`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class BuscarDocumentos(BaseModel):
    herramienta: Literal["buscar_documentos"]
    query: str
    top_k: int


class ObtenerPagina(BaseModel):
    herramienta: Literal["obtener_pagina"]
    doc_id: str
    pagina: int


Herramienta = Annotated[BuscarDocumentos | ObtenerPagina, Field(discriminator="herramienta")]


class LlamadaHerramienta(BaseModel):
    llamada: Herramienta


# ------------------------------------------------ esquemas abiertos (se rechazan)


class ConArgumentosLibres(BaseModel):
    """El esquema original de la spec: `argumentos` es un dict libre."""

    herramienta: str
    argumentos: dict[str, object]


class Interno(BaseModel):
    extras: dict[str, int]


class ConDictAnidado(BaseModel):
    nombre: str
    interno: Interno


class ConCampoAny(BaseModel):
    nombre: str
    valor: object


class UnionEnLaRaiz(RootModel[Herramienta]):
    pass


class Vacio(BaseModel):
    pass


class ConModeloAnidadoVacio(BaseModel):
    """Objeto anidado sin propiedades (no es un dict: es un modelo sin campos)."""

    nombre: str
    vacio: Vacio


class ConExtraAllow(BaseModel):
    """Tiene propiedades, pero admite otras libres (`additionalProperties: true`)."""

    model_config = ConfigDict(extra="allow")

    nombre: str


class ConTupla(BaseModel):
    """`tuple[int, str]` sale como `prefixItems`, sin `items`."""

    par: tuple[int, str]


class ConLista(BaseModel):
    """Una lista de modelos cerrados sí es válida."""

    resultados: list[BuscarDocumentos]
