"""One agent turn: build messages, loop over tool calls, stream the answer."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Generator, Iterator
from functools import partial
from typing import Any

from app import db
from app.agent import api_client, ollama_client, prompts, tools
from app.policy import Policy
from app.settings import Settings, load_policy

MAX_TOOL_ROUNDS = 4
TOOL_NAME = "get_inspection_result"


def _history_messages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map stored rows back to Ollama chat messages (never includes photos)."""
    out = []
    for row in rows:
        if row["role"] == "assistant" and row["tool_name"]:
            out.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": row["tool_name"],
                        "arguments": json.loads(row["content"] or "{}"),
                    }
                }],
            })
        else:
            out.append({"role": row["role"], "content": row["content"]})
    return out


def _provider_chat(settings: Settings) -> Callable[..., Any]:
    """The chat function for the configured provider: hosted API or local Ollama."""
    if settings.llm_provider == "api":
        return partial(api_client.chat, api_key=settings.api_key,
                       reasoning_effort=settings.api_reasoning_effort)
    return ollama_client.chat


def _endpoint(settings: Settings) -> tuple[str, str, float | None]:
    """Model name, base URL and temperature for the configured provider."""
    if settings.llm_provider == "api":
        return settings.api_model, settings.api_base_url, settings.api_temperature
    return settings.llm_model, settings.ollama_url, settings.temperature


def _stream_round(chat: Callable[..., Any], settings: Settings,
                  messages: list[dict[str, Any]],
                  tools_arg: list[dict[str, Any]] | None, seed: int | None,
                  think: bool | None
                  ) -> Generator[str, None, tuple[str, list[dict[str, Any]]]]:
    """Yield every chunk verbatim, except leading blank-only chunks are held
    back and flushed when the first non-blank chunk arrives. An all-blank
    answer yields nothing and the caller substitutes the fallback sentence.
    """
    parts: list[str] = []
    calls: list[dict[str, Any]] = []
    leading: list[str] = []
    flushing = False
    model, base_url, temperature = _endpoint(settings)
    for event, payload in chat(model, messages, tools=tools_arg,
                               stream=True, temperature=temperature,
                               seed=seed, think=think,
                               base_url=base_url):
        if event == "text":
            parts.append(payload)
            if not flushing:
                if payload.strip():
                    flushing = True
                    yield from leading
                    yield payload
                else:
                    leading.append(payload)
            else:
                yield payload
        elif event == "tool_calls":
            calls = payload
    return "".join(parts), calls


def _record_tool_exchange(conn: sqlite3.Connection, inspection_id: int,
                          messages: list[dict[str, Any]], name: str,
                          args: dict[str, Any], result: dict[str, Any],
                          call: dict[str, Any] | None = None) -> None:
    """Store one assistant tool call plus its result, and extend the context.

    `call` is the provider's own tool call; whatever it must see again in this turn
    (call id, Gemini's thought signature) is copied into the context, not the database.
    """
    extra = {key: call[key] for key in api_client.PASS_THROUGH_KEYS if call and key in call}
    db.add_message(conn, inspection_id, "assistant",
                   json.dumps(args, ensure_ascii=False), tool_name=name)
    db.add_message(conn, inspection_id, "tool",
                   json.dumps(result, ensure_ascii=False), tool_name=name)
    messages.append({"role": "assistant", "content": "",
                     "tool_calls": [{"function": {"name": name, "arguments": args},
                                     **extra}]})
    messages.append({"role": "tool", "content": json.dumps(result)})


def _finish_answer(conn: sqlite3.Connection, inspection_id: int, text: str) -> Iterator[str]:
    """Store the final answer, substituting the fallback when it is blank."""
    if not text.strip():
        text = prompts.FALLBACK_ANSWER
        yield text
    db.add_message(conn, inspection_id, "assistant", text)


def run_turn(conn: sqlite3.Connection, settings: Settings, inspection_id: int,
             kind: str, message: str | None = None, policy: Policy | None = None,
             chat_fn: Callable[..., Any] | None = None, seed: int | None = None
             ) -> Iterator[str]:
    """Run one turn and yield the answer text chunks as they arrive.

    The model may call get_inspection_result (at most 4 rounds, always for the
    current inspection); an unknown tool name gets an error reply so the model
    can correct itself. Past 4 rounds the model is asked once more without
    tools. A blank answer is replaced by the fallback sentence, so a stored
    assistant message is never blank; every new message is stored.
    """
    if kind == "explain":
        user_text = prompts.EXPLAIN_REQUEST
    elif kind == "user":
        user_text = message or ""
    else:
        raise ValueError(f"Unknown chat kind: {kind}.")
    policy = policy or load_policy()
    chat = chat_fn or _provider_chat(settings)

    detail = db.get_inspection(conn, inspection_id)
    rows = detail["messages"] if detail else []
    messages: list[dict[str, Any]] = (
        [{"role": "system", "content": prompts.system_prompt(settings.agent_drop_notice_rule)}]
        + (prompts.FEW_SHOT_EXAMPLES if settings.agent_few_shot else [])
        + _history_messages(rows)
        + [{"role": "user", "content": user_text}]
    )
    db.add_message(conn, inspection_id, "user", user_text)
    think = True if (kind == "user" and settings.llm_think_user) else settings.llm_think

    for _ in range(MAX_TOOL_ROUNDS):
        text, calls = yield from _stream_round(chat, settings, messages,
                                               [tools.TOOL_SPEC], seed, think)
        if not calls:
            yield from _finish_answer(conn, inspection_id, text)
            return
        for call in calls:
            name = call.get("name", "")
            if name != TOOL_NAME:
                _record_tool_exchange(conn, inspection_id, messages, name,
                                      call.get("arguments", {}) or {}, {
                    "error": f"Unknown tool '{name}'. "
                             f"The only available tool is {TOOL_NAME}."}, call)
                continue
            pinned = {"inspection_id": inspection_id}
            result = tools.get_inspection_result(conn, inspection_id, policy)
            _record_tool_exchange(conn, inspection_id, messages, name, pinned, result,
                                  call)
    text, _ = yield from _stream_round(chat, settings, messages, None, seed, think)
    yield from _finish_answer(conn, inspection_id, text)
