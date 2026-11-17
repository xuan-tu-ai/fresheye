"""Minimal Ollama /api/chat client with tool calls and streaming."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def _normalize_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten Ollama tool calls to plain name/arguments dicts."""
    calls = []
    for call in message.get("tool_calls") or []:
        func = call.get("function", {})
        calls.append({"name": func.get("name", ""), "arguments": func.get("arguments", {})})
    return calls


def build_body(model: str, messages: list[dict[str, str]], tools: list[dict] | None,
               stream: bool, temperature: float, seed: int | None,
               think: bool | None) -> dict[str, Any]:
    """Build the /api/chat request body, omitting unset optional keys."""
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": temperature},
    }
    if seed is not None:
        body["options"]["seed"] = seed
    if think is not None:
        body["think"] = think
    if tools:
        body["tools"] = tools
    return body


def chat(model: str, messages: list[dict[str, str]], tools: list[dict] | None = None,
         stream: bool = False, temperature: float = 0.0, seed: int | None = None,
         think: bool | None = None,
         base_url: str = DEFAULT_BASE_URL, timeout: float = 120.0
         ) -> dict[str, Any] | Iterator[tuple[str, Any]]:
    """Call Ollama chat: a message dict when stream=False, events otherwise.

    The streamed events are ("text", chunk) pairs while the answer arrives,
    plus a final ("tool_calls", [...]) event when the model calls tools.
    """
    body = build_body(model, messages, tools, stream, temperature, seed, think)
    if not stream:
        resp = httpx.post(f"{base_url}/api/chat", json=body, timeout=timeout)
        resp.raise_for_status()
        message = resp.json()["message"]
        return {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),
            "tool_calls": _normalize_tool_calls(message),
        }
    return _stream(body, base_url, timeout)


def _stream(body: dict[str, Any], base_url: str,
            timeout: float) -> Iterator[tuple[str, Any]]:
    """Yield text chunks, then the tool calls if the model made any."""
    calls: list[dict[str, Any]] = []
    with httpx.stream("POST", f"{base_url}/api/chat", json=body, timeout=timeout) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.strip():
                continue
            chunk = json.loads(line)["message"]
            text = chunk.get("content", "")
            if text:
                yield ("text", text)
            found = _normalize_tool_calls(chunk)
            if found:
                calls.extend(found)
    if calls:
        yield ("tool_calls", calls)
