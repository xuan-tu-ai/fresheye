"""Hosted-LLM client and provider switch; no test here touches the network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import db, settings as settings_module
from app.agent import api_client, loop, ollama_client
from app.policy import Policy
from app.settings import Settings

POLICY = Policy(conf_threshold=0.95, strangeness_threshold=0.35, knn_k=10, max_images=3)


def _settings(provider: str = "api") -> Settings:
    """Settings for a provider that is never called over the network."""
    return Settings(
        checkpoint=Path("checkpoint"), final_config=Path("final_config"),
        data_dir=Path("data"), app_data_dir=Path("app_data"), port=8200,
        ollama_url="http://127.0.0.1:11434", llm_model="local-model",
        llm_think=False, agent_few_shot=False, agent_drop_notice_rule=False,
        llm_think_user=False, temperature=0.0,
        llm_provider=provider, api_base_url="https://llm.example/v1",
        api_model="hosted-model", api_reasoning_effort="low", api_key="secret-key",
    )


def test_messages_convert_to_openai_shape() -> None:
    """Arguments become a JSON string and each tool result points at its call."""
    converted = api_client.to_api_messages([
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "hỏi"},
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "get_inspection_result",
                                      "arguments": {"inspection_id": 7}}}]},
        {"role": "tool", "content": '{"decision": "ANSWER"}'},
        {"role": "assistant", "content": "đáp"},
    ])
    call = converted[2]["tool_calls"][0]
    print(f"[api] converted call {call}")
    assert converted[0] == {"role": "system", "content": "rules"}
    assert "content" not in converted[2]
    assert call["type"] == "function" and call["id"]
    assert json.loads(call["function"]["arguments"]) == {"inspection_id": 7}
    assert converted[3] == {"role": "tool", "tool_call_id": call["id"],
                            "content": '{"decision": "ANSWER"}'}
    assert converted[4] == {"role": "assistant", "content": "đáp"}


def test_provider_fields_are_sent_back_unchanged() -> None:
    """The provider's own call id and extra_content survive the round trip."""
    signature = {"google": {"thought_signature": "abc123"}}
    converted = api_client.to_api_messages([
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "t", "arguments": {}},
                         "id": "provider-id", "extra_content": signature}]},
        {"role": "tool", "content": "{}"},
    ])
    assert converted[0]["tool_calls"][0]["id"] == "provider-id"
    assert converted[0]["tool_calls"][0]["extra_content"] == signature
    assert converted[1]["tool_call_id"] == "provider-id"


def test_body_omits_unset_options() -> None:
    """Temperature, seed, effort and tools appear only when given."""
    bare = api_client.build_body("m", [{"role": "user", "content": "x"}], None, True,
                                 None, None, None)
    full = api_client.build_body("m", [{"role": "user", "content": "x"}],
                                 [{"type": "function"}], False, 0.2, 42, "low")
    print(f"[api] bare keys {sorted(bare)}, full keys {sorted(full)}")
    assert sorted(bare) == ["messages", "model", "stream"]
    assert full["temperature"] == 0.2 and full["seed"] == 42
    assert full["reasoning_effort"] == "low" and full["tools"] == [{"type": "function"}]


def _sse(*chunks: dict) -> list[str]:
    """Server-sent event lines for the given chunks, closed by the DONE marker."""
    lines = []
    for chunk in chunks:
        lines += [f"data: {json.dumps(chunk, ensure_ascii=False)}", ""]
    return lines + ["data: [DONE]", ""]


def _delta(**delta: object) -> dict:
    return {"choices": [{"index": 0, "delta": delta}]}


def test_stream_yields_text_chunks_in_order() -> None:
    """Text arrives chunk by chunk, spaces included; role-only chunks add nothing."""
    events = list(api_client.iter_events(_sse(
        _delta(role="assistant"), _delta(content="Cá "), _delta(content="tươi"),
        _delta(content=None), {"choices": []})))
    assert events == [("text", "Cá "), ("text", "tươi")]


def test_stream_joins_a_tool_call_split_over_chunks() -> None:
    """Name first, then the arguments string in pieces: one call comes out."""
    events = list(api_client.iter_events(_sse(
        _delta(tool_calls=[{"index": 0, "id": "c1", "type": "function",
                            "function": {"name": "get_inspection_result",
                                         "arguments": ""}}]),
        _delta(tool_calls=[{"index": 0, "function": {"arguments": '{"inspec'}}]),
        _delta(tool_calls=[{"index": 0, "function": {"arguments": 'tion_id": 3}'}}]))))
    print(f"[api] stream events {events}")
    assert events == [("tool_calls", [{"name": "get_inspection_result",
                                       "arguments": {"inspection_id": 3}, "id": "c1"}])]


def test_stream_keeps_whole_calls_that_share_index_zero() -> None:
    """Two complete calls both numbered 0 stay two calls; extra_content is kept."""
    signature = {"google": {"thought_signature": "sig"}}
    events = list(api_client.iter_events(_sse(
        _delta(tool_calls=[{"index": 0, "id": "a", "extra_content": signature,
                            "function": {"name": "first", "arguments": "{}"}}]),
        _delta(tool_calls=[{"index": 0, "id": "b",
                            "function": {"name": "second", "arguments": ""}}]))))
    calls = events[0][1]
    assert [c["name"] for c in calls] == ["first", "second"]
    assert calls[0]["extra_content"] == signature and calls[1]["arguments"] == {}


def test_stream_error_chunk_raises() -> None:
    """An error object inside the stream is reported, not swallowed."""
    with pytest.raises(RuntimeError, match="quota"):
        list(api_client.iter_events(_sse({"error": {"message": "quota exceeded"}})))


def test_missing_key_fails_before_any_request() -> None:
    """Without a key the client refuses, with a message that says where to put it."""
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        api_client.chat("m", [{"role": "user", "content": "x"}],
                        base_url="https://llm.example/v1", api_key="")


def test_env_file_fills_missing_variables_only(tmp_path: Path, monkeypatch) -> None:
    """backend/.env supplies the key; a variable already set in the shell wins."""
    env = tmp_path / ".env"
    env.write_text("# comment\nLLM_API_KEY = 'from-file'\nOTHER_SET=file\n\nnot a pair\n",
                   encoding="utf-8")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("OTHER_SET", "shell")
    settings_module.load_env_file(env)
    import os
    assert os.environ["LLM_API_KEY"] == "from-file"
    assert os.environ["OTHER_SET"] == "shell"
    settings_module.load_env_file(tmp_path / "missing.env")


def test_settings_repr_hides_the_key() -> None:
    """Printing settings (logs, tracebacks) must not reveal the key."""
    assert "secret-key" not in repr(_settings())


def test_provider_switch_picks_client_model_and_url() -> None:
    """One setting decides which client, model, URL and temperature are used."""
    api, local = _settings("api"), _settings("ollama")
    chosen = loop._provider_chat(api)
    print(f"[api] api endpoint {loop._endpoint(api)}, ollama endpoint {loop._endpoint(local)}")
    assert chosen.func is api_client.chat
    assert chosen.keywords == {"api_key": "secret-key", "reasoning_effort": "low"}
    assert loop._endpoint(api) == ("hosted-model", "https://llm.example/v1", None)
    assert loop._provider_chat(local) is ollama_client.chat
    assert loop._endpoint(local) == ("local-model", "http://127.0.0.1:11434", 0.0)


def test_loop_returns_call_id_and_signature_within_the_turn(tmp_path: Path) -> None:
    """After a tool call, the next request of the turn carries the provider's fields."""
    conn = db.connect(tmp_path / "turn.db")
    iid = db.create_inspection(conn)
    db.add_image(conn, iid, 1, f"uploads/{iid}/1.jpg", f"cams/{iid}/1.png", 3.0, 3.0, 2,
                 [0.02, 0.02, 0.96], 0.96, 0.2, "Chanos Chanos", "trung tâm", 0.3, 0.5)
    db.update_decision(conn, iid, "closed", "ANSWER", 2, [0.02, 0.02, 0.96], 0.96, 0.2,
                       "Chanos Chanos", 1, [], {})
    signature = {"google": {"thought_signature": "sig-1"}}
    seen: list[tuple[str, str, list]] = []

    def fake(model: str, messages: list, base_url: str = "", **kwargs: object) -> list:
        """First call requests the tool with provider fields; second call answers."""
        seen.append((model, base_url, [dict(m) for m in messages]))
        if len(seen) == 1:
            return [("tool_calls", [{"name": loop.TOOL_NAME, "arguments": {},
                                     "id": "call-9", "extra_content": signature}])]
        return [("text", "Xong.")]

    out = "".join(loop.run_turn(conn, _settings("api"), iid, "user", "hỏi",
                                policy=POLICY, chat_fn=fake))
    replayed = seen[1][2][-2]["tool_calls"][0]
    stored = db.get_inspection(conn, iid)["messages"]
    conn.close()
    print(f"[api] loop used {seen[0][0]} at {seen[0][1]}; replayed call {replayed}")
    assert out == "Xong."
    assert seen[0][0] == "hosted-model" and seen[0][1] == "https://llm.example/v1"
    assert replayed["id"] == "call-9" and replayed["extra_content"] == signature
    # What the API sees next is valid OpenAI shape, with the signature attached.
    wire = api_client.to_api_messages(seen[1][2])
    assert wire[-2]["tool_calls"][0]["extra_content"] == signature
    assert wire[-1]["tool_call_id"] == "call-9"
    # The database keeps only words and numbers, as before.
    assert all("sig-1" not in (row["content"] or "") for row in stored)
