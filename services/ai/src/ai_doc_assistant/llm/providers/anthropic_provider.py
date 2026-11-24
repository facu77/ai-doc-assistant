"""Adaptador de Anthropic (SDK `anthropic`, API de Messages).

Firmas confirmadas en el SDK instalado (anthropic 2.14.0):
- `AsyncAnthropic(api_key=, timeout=, max_retries=, http_client=)` en `anthropic/_client.py`.
- `AsyncMessages.create(max_tokens=, messages=, model=, system=, output_config=)` y
  `AsyncMessages.stream(...)` → `AsyncMessageStreamManager` (con `text_stream` y
  `get_final_message()`), en `anthropic/resources/messages/messages.py`.
- Salida estructurada: `output_config={"format": {"type": "json_schema", "schema": ...}}`,
  con el esquema adaptado por `anthropic.transform_schema` (exportado en `anthropic/__init__.py`).
- No se envían `temperature`, `top_p` ni `top_k`: los modelos actuales los rechazan con 400.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import anthropic
import httpx2
from anthropic.types import MessageParam, OutputConfigParam, TextBlock

from ai_doc_assistant.llm.errors import LLMError
from ai_doc_assistant.llm.models import Usage
from ai_doc_assistant.llm.provider import (
    LLMRequest,
    ProviderResult,
    StreamEnd,
    StreamEvent,
    TextDelta,
)
from ai_doc_assistant.llm.providers._http_errors import (
    connection_error,
    error_from_status,
    timeout_error,
    unexpected_error,
)

PROVIDER = "anthropic"

# En DEBUG el SDK loguea las opciones de cada request, cuerpo (y prompt) incluido.
# Se fija su logger en WARNING para que un LOG_LEVEL=DEBUG global no filtre prompts.
logging.getLogger("anthropic").setLevel(logging.WARNING)


def _translate(exc: anthropic.AnthropicError) -> LLMError:
    # El orden importa: APITimeoutError es subclase de APIConnectionError.
    if isinstance(exc, anthropic.APITimeoutError):
        return timeout_error(PROVIDER)
    if isinstance(exc, anthropic.APIConnectionError):
        return connection_error(PROVIDER)
    if isinstance(exc, anthropic.APIStatusError):
        return error_from_status(PROVIDER, exc.status_code, exc.response.headers)
    return unexpected_error(PROVIDER, exc)


class AnthropicProvider:
    name = PROVIDER

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            # Los reintentos son de `ResilientLLMClient`; si el SDK también reintentara,
            # los intentos se multiplicarían (3 nuestros x 3 del SDK = 9 requests).
            max_retries=0,
            http_client=http_client,
        )

    def _params(self, request: LLMRequest) -> tuple[list[MessageParam], OutputConfigParam | None]:
        messages: list[MessageParam] = [{"role": "user", "content": request.prompt}]
        output_config: OutputConfigParam | None = None
        if request.output_schema is not None:
            output_config = {
                "format": {
                    "type": "json_schema",
                    "schema": anthropic.transform_schema(request.output_schema),
                }
            }
        return messages, output_config

    async def generate(self, request: LLMRequest) -> ProviderResult:
        messages, output_config = self._params(request)
        try:
            message = await self._client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                messages=messages,
                system=request.system if request.system is not None else anthropic.omit,
                output_config=output_config if output_config is not None else anthropic.omit,
            )
        except anthropic.AnthropicError as exc:
            raise _translate(exc) from exc
        text = "".join(block.text for block in message.content if isinstance(block, TextBlock))
        usage = Usage(
            input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens
        )
        return ProviderResult(text=text, usage=usage)

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamEvent, None]:
        messages, output_config = self._params(request)
        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=request.max_tokens,
                messages=messages,
                system=request.system if request.system is not None else anthropic.omit,
                output_config=output_config if output_config is not None else anthropic.omit,
            ) as stream:
                async for text in stream.text_stream:
                    yield TextDelta(text=text)
                final = await stream.get_final_message()
        except anthropic.AnthropicError as exc:
            raise _translate(exc) from exc
        yield StreamEnd(
            usage=Usage(
                input_tokens=final.usage.input_tokens, output_tokens=final.usage.output_tokens
            )
        )
