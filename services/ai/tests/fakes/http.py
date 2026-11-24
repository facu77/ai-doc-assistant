"""Servidor HTTP falso para los SDKs de Anthropic y OpenAI.

Los adaptadores reciben un `httpx2.AsyncClient` con un `MockTransport`: el SDK real arma la
request, la "manda" y parsea la respuesta, y levanta sus propias excepciones (401, 429,
503, timeout). Así se testea la traducción de errores sin red y sin clave real.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import httpx2

Responder = Callable[[httpx2.Request], httpx2.Response]


@dataclass
class FakeServer:
    """Devuelve las respuestas en orden y registra cada request (con su hora)."""

    responses: list[Responder]
    clock: Callable[[], float] = lambda: 0.0
    requests: list[httpx2.Request] = field(default_factory=list)
    request_times: list[float] = field(default_factory=list)

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        self.request_times.append(self.clock())
        if not self.responses:
            raise AssertionError("el servidor falso no tiene más respuestas")
        return self.responses.pop(0)(request)

    def client(self) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(transport=httpx2.MockTransport(self.handle))

    def json_bodies(self) -> list[dict[str, object]]:
        bodies: list[dict[str, object]] = []
        for request in self.requests:
            parsed: dict[str, object] = json.loads(request.content)
            bodies.append(parsed)
        return bodies


def status(code: int, *, headers: dict[str, str] | None = None) -> Responder:
    body = {"type": "error", "error": {"type": "api_error", "message": f"falla simulada {code}"}}
    return lambda request: httpx2.Response(code, json=body, headers=headers, request=request)


def raise_timeout() -> Responder:
    def responder(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("timeout simulado", request=request)

    return responder


# ---------------------------------------------------------------- Anthropic


def anthropic_message(text: str, *, input_tokens: int = 11, output_tokens: int = 4) -> Responder:
    body = {
        "id": "msg_prueba",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    return lambda request: httpx2.Response(200, json=body, request=request)


def _sse(events: Sequence[tuple[str, dict[str, object]]]) -> bytes:
    lines = [f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events]
    return "".join(lines).encode()


def anthropic_stream(
    chunks: Sequence[str], *, input_tokens: int = 11, output_tokens: int = 4
) -> Responder:
    message: dict[str, object] = {
        "id": "msg_prueba",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": 1},
    }
    events: list[tuple[str, dict[str, object]]] = [
        ("message_start", {"type": "message_start", "message": message}),
        (
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        ),
    ]
    for chunk in chunks:
        events.append(
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": chunk},
                },
            )
        )
    events += [
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": output_tokens},
            },
        ),
        ("message_stop", {"type": "message_stop"}),
    ]
    payload = _sse(events)
    return lambda request: httpx2.Response(
        200, content=payload, headers={"content-type": "text/event-stream"}, request=request
    )


# ---------------------------------------------------------------- OpenAI


def openai_completion(
    text: str, *, prompt_tokens: int = 9, completion_tokens: int = 5
) -> Responder:
    body = {
        "id": "chatcmpl-prueba",
        "object": "chat.completion",
        "created": 0,
        "model": "modelo-openai-de-prueba",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return lambda request: httpx2.Response(200, json=body, request=request)


def openai_stream(
    chunks: Sequence[str], *, prompt_tokens: int = 9, completion_tokens: int = 5
) -> Responder:
    def chunk(delta: dict[str, object], usage: dict[str, int] | None) -> str:
        data: dict[str, object] = {
            "id": "chatcmpl-prueba",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "modelo-openai-de-prueba",
            "choices": [] if usage else [{"index": 0, "delta": delta, "finish_reason": None}],
            "usage": usage,
        }
        return f"data: {json.dumps(data)}\n\n"

    parts = [chunk({"role": "assistant", "content": c}, None) for c in chunks]
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    parts.append(chunk({}, usage))
    parts.append("data: [DONE]\n\n")
    payload = "".join(parts).encode()
    return lambda request: httpx2.Response(
        200, content=payload, headers={"content-type": "text/event-stream"}, request=request
    )
