"""Adaptador de OpenAI (SDK `openai`, API de Chat Completions).

Firmas confirmadas en el SDK instalado (openai 3.59.0):
- `AsyncOpenAI(api_key=, timeout=, max_retries=, http_client=)` en `openai/_client.py`.
- `AsyncCompletions.create(messages=, model=, max_completion_tokens=, response_format=,
  stream=, stream_options=)` en `openai/resources/chat/completions/completions.py`.
  `max_tokens` está deprecado en favor de `max_completion_tokens`.
- Streaming: `stream=True` devuelve `AsyncStream[ChatCompletionChunk]`; con
  `stream_options={"include_usage": True}` el último chunk trae el uso y `choices=[]`.
- Salida estructurada: `response_format={"type": "json_schema", "json_schema": {...}}`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import httpx2
import openai
from openai.types.chat import ChatCompletionMessageParam
from openai.types.shared_params import ResponseFormatJSONSchema

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

PROVIDER = "openai"

# openai 3.59 ya no loguea el cuerpo de las requests en DEBUG (solo método y reintentos,
# `openai/_base_client.py:606`). Igual se fija en WARNING: es defensa en profundidad ante
# otra versión que vuelva a hacerlo. La política central de logging de los SDKs queda
# para `add-observability-security`.
logging.getLogger("openai").setLevel(logging.WARNING)


def _translate(exc: openai.OpenAIError) -> LLMError:
    if isinstance(exc, openai.APITimeoutError):
        return timeout_error(PROVIDER)
    if isinstance(exc, openai.APIConnectionError):
        return connection_error(PROVIDER)
    if isinstance(exc, openai.APIStatusError):
        return error_from_status(PROVIDER, exc.status_code, exc.response.headers)
    return unexpected_error(PROVIDER, exc)


class OpenAIProvider:
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
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,  # la política de reintentos es de ResilientLLMClient
            http_client=http_client,
        )

    @staticmethod
    def _messages(request: LLMRequest) -> list[ChatCompletionMessageParam]:
        messages: list[ChatCompletionMessageParam] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        return messages

    @staticmethod
    def _response_format(request: LLMRequest) -> ResponseFormatJSONSchema | None:
        if request.output_schema is None:
            return None
        return {
            "type": "json_schema",
            "json_schema": {
                "name": request.output_schema.__name__,
                "schema": request.output_schema.model_json_schema(),
                # `strict` exige additionalProperties=false en todo el esquema, y eso
                # rompe campos libres como `dict[str, object]`. Validamos nosotros.
                "strict": False,
            },
        }

    async def generate(self, request: LLMRequest) -> ProviderResult:
        response_format = self._response_format(request)
        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=self._messages(request),
                max_completion_tokens=request.max_tokens,
                response_format=response_format if response_format is not None else openai.omit,
            )
        except openai.OpenAIError as exc:
            raise _translate(exc) from exc
        text = ""
        if completion.choices:
            text = completion.choices[0].message.content or ""
        usage = completion.usage
        return ProviderResult(
            text=text,
            usage=Usage(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            ),
        )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamEvent, None]:
        response_format = self._response_format(request)
        usage = Usage(input_tokens=0, output_tokens=0)
        try:
            chunks = await self._client.chat.completions.create(
                model=self.model,
                messages=self._messages(request),
                max_completion_tokens=request.max_tokens,
                response_format=response_format if response_format is not None else openai.omit,
                stream=True,
                stream_options={"include_usage": True},
            )
            async with chunks:
                async for chunk in chunks:
                    if chunk.usage is not None:
                        usage = Usage(
                            input_tokens=chunk.usage.prompt_tokens,
                            output_tokens=chunk.usage.completion_tokens,
                        )
                    for choice in chunk.choices:
                        if choice.delta.content:
                            yield TextDelta(text=choice.delta.content)
        except openai.OpenAIError as exc:
            raise _translate(exc) from exc
        yield StreamEnd(usage=usage)

    async def aclose(self) -> None:
        await self._client.close()
