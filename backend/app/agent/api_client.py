"""Client for hosted LLMs that speak the OpenAI chat-completions protocol.

Works with Google Gemini (its OpenAI-compatible endpoint), OpenAI, OpenRouter and
any other provider exposing POST {base_url}/chat/completions. It returns the same
shapes as ollama_client.chat, so the agent loop does not care which one answers.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

import httpx

# Fields a provider attaches to a tool call that must be sent back unchanged on the
# next request of the same turn (Gemini keeps its thought signature in extra_content).
PASS_THROUGH_KEYS = ("id", "extra_content")


def to_api_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the loop's messages to the OpenAI wire format.

    The loop stores tool calls the Ollama way: arguments as a dict, no call id, and
    tool results without a reference to their call. This API wants arguments as a
    JSON string and every tool result tied to a call id, so ids are filled in here
    (kept when the provider gave one, generated for calls replayed from history).
    """
    out: list[dict[str, Any]] = []
    waiting: list[str] = []
    made = 0
    for message in messages:
        role = message["role"]
        if role == "assistant" and message.get("tool_calls"):
            calls = []
            for call in message["tool_calls"]:
                func = call["function"]
                made += 1
                call_id = call.get("id") or f"call_{made}"
                waiting.append(call_id)
                entry: dict[str, Any] = {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": func["name"],
                        "arguments": json.dumps(func.get("arguments") or {},
                                                ensure_ascii=False),
                    },
                }
                if "extra_content" in call:
                    entry["extra_content"] = call["extra_content"]
                calls.append(entry)
            converted: dict[str, Any] = {"role": "assistant", "tool_calls": calls}
            if message.get("content"):
                converted["content"] = message["content"]
            out.append(converted)
        elif role == "tool":
            call_id = waiting.pop(0) if waiting else f"call_{made}"
            out.append({"role": "tool", "tool_call_id": call_id,
                        "content": message["content"]})
        else:
            out.append({"role": role, "content": message["content"]})
    return out


def build_body(model: str, messages: list[dict[str, Any]], tools: list[dict] | None,
               stream: bool, temperature: float | None, seed: int | None,
               reasoning_effort: str | None) -> dict[str, Any]:
    """Build the request body, leaving out every option that is not set."""
    body: dict[str, Any] = {
        "model": model,
        "messages": to_api_messages(messages),
        "stream": stream,
    }
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    if tools:
        body["tools"] = tools
    return body


def _parse_arguments(raw: str) -> dict[str, Any]:
    """Tool arguments arrive as a JSON string; keep the text when it does not parse."""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_unparsed": raw}
    return parsed if isinstance(parsed, dict) else {"_unparsed": raw}


def _normalize_call(call: dict[str, Any]) -> dict[str, Any]:
    """Flatten one complete tool call to name/arguments plus the pass-through keys."""
    func = call.get("function") or {}
    out: dict[str, Any] = {
        "name": func.get("name") or "",
        "arguments": _parse_arguments(func.get("arguments") or ""),
    }
    for key in PASS_THROUGH_KEYS:
        if call.get(key):
            out[key] = call[key]
    return out


def iter_events(lines: Iterable[str]) -> Iterator[tuple[str, Any]]:
    """Turn server-sent event lines into ("text", chunk) and ("tool_calls", [...]).

    A tool call may arrive whole or spread over several chunks (name first, then
    pieces of the arguments string); pieces are joined before the call is reported.
    """
    partial: list[dict[str, Any]] = []
    by_index: dict[int, dict[str, Any]] = {}
    for line in lines:
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        if chunk.get("error"):
            raise RuntimeError(f"LLM API error in stream: {str(chunk['error'])[:300]}")
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                yield ("text", delta["content"])
            for piece in delta.get("tool_calls") or []:
                index = piece.get("index", 0)
                slot = by_index.get(index)
                # Some providers number every call 0; a new id means a new call.
                if slot is None or (piece.get("id") and slot["id"] and piece["id"] != slot["id"]):
                    slot = {"id": "", "function": {"name": "", "arguments": ""}}
                    by_index[index] = slot
                    partial.append(slot)
                if piece.get("id"):
                    slot["id"] = piece["id"]
                if piece.get("extra_content"):
                    slot["extra_content"] = piece["extra_content"]
                func = piece.get("function") or {}
                if func.get("name"):
                    slot["function"]["name"] = func["name"]
                slot["function"]["arguments"] += func.get("arguments") or ""
    if partial:
        yield ("tool_calls", [_normalize_call(call) for call in partial])


def chat(model: str, messages: list[dict[str, Any]], tools: list[dict] | None = None,
         stream: bool = False, temperature: float | None = None, seed: int | None = None,
         think: bool | None = None, base_url: str = "", timeout: float = 120.0,
         api_key: str = "", reasoning_effort: str | None = None
         ) -> dict[str, Any] | Iterator[tuple[str, Any]]:
    """Call the provider: a message dict when stream=False, events otherwise.

    `think` exists only so this function can stand in for ollama_client.chat; hosted
    models take `reasoning_effort` instead, so `think` is ignored.
    """
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set. Put it in backend/.env "
                           "(see backend/.env.example) and restart the backend.")
    body = build_body(model, messages, tools, stream, temperature, seed, reasoning_effort)
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    if not stream:
        resp = httpx.post(url, json=body, headers=headers, timeout=timeout)
        _raise_for_error(resp)
        message = resp.json()["choices"][0]["message"]
        return {
            "role": message.get("role", "assistant"),
            "content": message.get("content") or "",
            "tool_calls": [_normalize_call(c) for c in message.get("tool_calls") or []],
        }
    return _stream(url, body, headers, timeout)


def _raise_for_error(resp: httpx.Response) -> None:
    """Raise with the provider's own explanation (it never contains the key)."""
    if resp.status_code >= 400:
        raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:300]}")


def _stream(url: str, body: dict[str, Any], headers: dict[str, str],
            timeout: float) -> Iterator[tuple[str, Any]]:
    """Open the streaming request and yield its events."""
    with httpx.stream("POST", url, json=body, headers=headers, timeout=timeout) as resp:
        if resp.status_code >= 400:
            resp.read()
        _raise_for_error(resp)
        yield from iter_events(resp.iter_lines())
