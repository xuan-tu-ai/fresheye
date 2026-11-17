"""Agent tests: the inspection-result tool reads exactly what the database holds."""

from __future__ import annotations

import json
from pathlib import Path

from app import db
from app.agent import loop, ollama_client, prompts, tools
from app.policy import Policy
from app.settings import Settings

POLICY = Policy(conf_threshold=0.95, strangeness_threshold=0.35, knn_k=10, max_images=3)


def _seeded_db(path: Path, action: str, label: int | None) -> int:
    """One inspection with two images, one decision, and its id."""
    conn = db.connect(path)
    try:
        iid = db.create_inspection(conn)
        for seq in (1, 2):
            db.add_image(conn, iid, seq, f"uploads/{iid}/{seq}.jpg",
                         f"cams/{iid}/{seq}.png", 3.0, 3.0, 2,
                         [0.05, 0.05, 0.9], 0.9, 0.2, "Chanos Chanos",
                         "trung tâm", 0.3, 0.5)
        db.update_decision(conn, iid, "closed", action, label,
                           [0.05, 0.05, 0.9], 0.9, 0.2, "Chanos Chanos", 2,
                           [] if action == "ANSWER" else ["LOW_CONFIDENCE"], {})
        return iid
    finally:
        conn.close()


def _tool_result(path: Path, action: str, label: int | None) -> dict:
    """Run the tool against a fresh connection on a seeded database."""
    iid = _seeded_db(path, action, label)
    conn = db.connect(path)
    try:
        return tools.get_inspection_result(conn, iid, POLICY)
    finally:
        conn.close()


def test_tool_matches_database(tmp_path: Path) -> None:
    """Every tool field equals the stored inspection row."""
    result = _tool_result(tmp_path / "tool.db", "ANSWER", 2)
    print(f"[T4.2] tool: {result}")
    assert result["decision"] == "ANSWER"
    assert result["freshness_level"] == "Not Fresh"
    assert result["freshness_level_vi"] == "Không tươi"
    assert result["probabilities"] == {"Highly Fresh": 0.05, "Fresh": 0.05,
                                       "Not Fresh": 0.9}
    assert result["confidence"] == 0.9
    assert result["confidence_threshold"] == 0.95
    assert result["unfamiliarity"] == {"score": 0.2, "threshold": 0.35,
                                       "is_unfamiliar": False,
                                       "meaning": tools.UNFAMILIAR_MEANING}
    assert result["most_similar_known_species"] == "Chanos Chanos"
    assert result["reasons"] == []
    assert result["photos_taken"] == 2
    assert result["max_photos"] == 3
    assert result["attention_map"] == {"peak_region": "trung tâm",
                                      "center_share": 0.3, "concentration": 0.5,
                                      "meaning": tools.ATTENTION_MEANING}


def test_abstain_hides_freshness_level(tmp_path: Path) -> None:
    """A non-ANSWER result names no freshness level in any form."""
    result = _tool_result(tmp_path / "abstain.db", "ABSTAIN", None)
    print(f"[T4.2] abstain: {result}")
    assert result["decision"] == "ABSTAIN"
    for key in ("freshness_level", "freshness_level_vi", "probabilities", "label"):
        assert key not in result
    text = json.dumps(result, ensure_ascii=False)
    for name in ("Highly Fresh", "Not Fresh", "Fresh", "Rất tươi", "Tươi", "Không tươi"):
        assert name not in text, name


def test_no_image_paths_or_bytes(tmp_path: Path) -> None:
    """The tool JSON never leaks image paths, filenames, or binary data."""
    result = _tool_result(tmp_path / "leak.db", "ANSWER", 2)
    text = json.dumps(result, ensure_ascii=False)
    for banned in ("uploads", "cams", ".jpg", ".png", "file_path", "cam_path"):
        assert banned not in text, banned

    def walk(value: object) -> None:
        """Fail on any bytes value in the nested result."""
        assert not isinstance(value, bytes)
        if isinstance(value, dict):
            for sub in value.values():
                walk(sub)
        elif isinstance(value, list):
            for sub in value:
                walk(sub)

    walk(result)


def _settings(think: bool | None = False, few_shot: bool = False,
              drop_notice: bool = False, think_user: bool = False) -> Settings:
    """Settings pointing at a fake LLM (never called over the network)."""
    return Settings(
        checkpoint=Path("checkpoint"), final_config=Path("final_config"),
        data_dir=Path("data"), app_data_dir=Path("app_data"), port=8200,
        ollama_url="http://127.0.0.1:11434", llm_model="fake-model",
        llm_think=think, agent_few_shot=few_shot,
        agent_drop_notice_rule=drop_notice, llm_think_user=think_user,
        temperature=0.0,
    )


def _assert_no_images_key(value: object) -> None:
    """Fail on an exact images key (n_images and max_images counts are fine)."""
    if isinstance(value, dict):
        assert "images" not in value
        for sub in value.values():
            _assert_no_images_key(sub)
    elif isinstance(value, list):
        for sub in value:
            _assert_no_images_key(sub)


def test_loop_runs_tool_and_finishes(tmp_path: Path) -> None:
    """Fake asks for the tool once, then answers; all messages are stored."""
    db_path = tmp_path / "loop.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    seen: list = []

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """First call requests the tool, second call answers."""
        seen.append(messages)
        if len(seen) == 1:
            return [("tool_calls", [{"name": "get_inspection_result",
                                     "arguments": {"inspection_id": iid}}])]
        return [("text", "hello world")]

    conn = db.connect(db_path)
    try:
        out = list(loop.run_turn(conn, _settings(), iid, "user", "hello",
                                 policy=POLICY, chat_fn=fake))
    finally:
        conn.close()
    assert out == ["hello world"]
    conn = db.connect(db_path)
    try:
        detail = db.get_inspection(conn, iid)
    finally:
        conn.close()
    assert detail is not None
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant",
                                                      "tool", "assistant"]
    assert detail["messages"][1]["tool_name"] == "get_inspection_result"
    assert json.loads(detail["messages"][2]["content"])["decision"] == "ANSWER"
    assert detail["messages"][3]["content"] == "hello world"
    for messages in seen:
        _assert_no_images_key(messages)


def test_loop_stops_after_four_tool_rounds(tmp_path: Path) -> None:
    """Always-tool fake: 5 chats (last without tools), 4 tool runs, text kept."""
    db_path = tmp_path / "loop4.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    seen: list = []

    def fake(model: str, messages: list, tools: list | None = None,
             **kwargs: object) -> list:
        """Request the tool while offered; answer once tools are taken away."""
        seen.append((tools, messages))
        if tools is None:
            return [("text", "final answer")]
        return [("tool_calls", [{"name": "get_inspection_result",
                                 "arguments": {"inspection_id": iid}}])]

    conn = db.connect(db_path)
    try:
        out = list(loop.run_turn(conn, _settings(), iid, "explain",
                                 policy=POLICY, chat_fn=fake))
    finally:
        conn.close()
    assert len(seen) == 5
    assert seen[-1][0] is None
    assert out[-1] == "final answer"
    conn = db.connect(db_path)
    try:
        detail = db.get_inspection(conn, iid)
    finally:
        conn.close()
    assert detail is not None
    assert [m["role"] for m in detail["messages"]].count("tool") == 4
    assert detail["messages"][-1]["content"] == "final answer"
    for _, messages in seen:
        _assert_no_images_key(messages)


def _run_turn(db_path: Path, iid: int, kind: str, message: str | None,
              fake: object, policy: Policy = POLICY,
              settings: Settings | None = None) -> list:
    """Run one turn on a fresh connection and return the yielded chunks."""
    conn = db.connect(db_path)
    try:
        return list(loop.run_turn(conn, settings or _settings(), iid, kind, message,
                                  policy=policy, chat_fn=fake))
    finally:
        conn.close()


def _assistant_rows(db_path: Path, iid: int) -> list:
    """Assistant rows of one inspection in stored order."""
    conn = db.connect(db_path)
    try:
        detail = db.get_inspection(conn, iid)
    finally:
        conn.close()
    assert detail is not None
    return [m for m in detail["messages"] if m["role"] == "assistant"]


def test_loop_falls_back_on_empty_final_answer(tmp_path: Path) -> None:
    """Blank text after the last round yields and stores the fallback."""
    db_path = tmp_path / "fallback.db"
    iid = _seeded_db(db_path, "ANSWER", 2)

    def fake(model: str, messages: list, tools: list | None = None,
             **kwargs: object) -> list:
        """Always request the tool; answer blank once tools are taken away."""
        if tools is None:
            return [("text", "")]
        return [("tool_calls", [{"name": "get_inspection_result",
                                 "arguments": {"inspection_id": iid}}])]

    out = _run_turn(db_path, iid, "explain", None, fake)
    assert out == [prompts.FALLBACK_ANSWER]
    assert _assistant_rows(db_path, iid)[-1]["content"] == prompts.FALLBACK_ANSWER


def test_loop_falls_back_on_empty_first_answer(tmp_path: Path) -> None:
    """Blank text with no tool call yields and stores the fallback."""
    db_path = tmp_path / "fallback1.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    calls: list = []

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """Answer blank at once."""
        calls.append(messages)
        return [("text", "   ")]

    out = _run_turn(db_path, iid, "user", "hello", fake)
    assert out == [prompts.FALLBACK_ANSWER]
    assert len(calls) == 1
    assert _assistant_rows(db_path, iid)[-1]["content"] == prompts.FALLBACK_ANSWER


def test_loop_reports_unknown_tool_name(tmp_path: Path) -> None:
    """A wrong tool name gets an error reply; the real tool still runs once."""
    db_path = tmp_path / "wrongtool.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    seen: list = []
    script = [
        [("tool_calls", [{"name": "nope", "arguments": {}}])],
        [("tool_calls", [{"name": "get_inspection_result",
                           "arguments": {"inspection_id": iid}}])],
        [("text", "done")],
    ]

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """Wrong name, then right name, then an answer."""
        seen.append(messages)
        return script[len(seen) - 1]

    out = _run_turn(db_path, iid, "user", "hello", fake)
    assert out == ["done"]
    assert "Unknown tool" in json.dumps(seen[1], ensure_ascii=False)
    assistants = _assistant_rows(db_path, iid)
    assert [m["tool_name"] for m in assistants
            if m["tool_name"]] == ["nope", "get_inspection_result"]
    assert assistants[-1]["content"] == "done"


def test_loop_ignores_llm_inspection_id(tmp_path: Path) -> None:
    """The tool always reads the current inspection, not the LLM-filled id."""
    db_path = tmp_path / "pinned.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    other = _seeded_db(db_path, "ABSTAIN", None)

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """Ask for the other inspection, then answer."""
        if len(messages) < 4:
            return [("tool_calls", [{"name": "get_inspection_result",
                                     "arguments": {"inspection_id": other}}])]
        return [("text", "done")]

    _run_turn(db_path, iid, "user", "hello", fake)
    conn = db.connect(db_path)
    try:
        detail = db.get_inspection(conn, iid)
    finally:
        conn.close()
    assert detail is not None
    tool_rows = [m for m in detail["messages"] if m["role"] == "tool"]
    assert len(tool_rows) == 1
    assert json.loads(tool_rows[0]["content"])["decision"] == "ANSWER"


def test_no_blank_assistant_message_without_tool(tmp_path: Path) -> None:
    """Stored assistant rows are never blank text without a tool call."""
    db_path = tmp_path / "noblank.db"
    iid = _seeded_db(db_path, "ANSWER", 2)

    def fake_text(model: str, messages: list, **kwargs: object) -> list:
        """Answer normally."""
        return [("text", "all good")]

    def fake_blank(model: str, messages: list, **kwargs: object) -> list:
        """Answer blank."""
        return [("text", "")]

    _run_turn(db_path, iid, "user", "hello", fake_text)
    _run_turn(db_path, iid, "user", "hello again", fake_blank)
    for row in _assistant_rows(db_path, iid):
        assert row["content"].strip() != "" or row["tool_name"] is not None


def test_loop_preserves_whitespace_chunks(tmp_path: Path) -> None:
    """Every chunk is yielded verbatim, including whitespace-only ones."""
    db_path = tmp_path / "spaces.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    chunks = ["dưới", " ", "4°C", "\n", "- ", "Đóng", " ", "đá"]

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """Answer in many small chunks."""
        return [("text", chunk) for chunk in chunks]

    out = _run_turn(db_path, iid, "user", "hello", fake)
    assert "".join(out) == "".join(chunks)
    assert _assistant_rows(db_path, iid)[-1]["content"] == "".join(chunks)


def test_loop_flushes_leading_whitespace(tmp_path: Path) -> None:
    """Leading blank chunks are held, then flushed at the first word."""
    db_path = tmp_path / "leading.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    chunks = ["  ", "\n", "Xin", " ", "chào"]

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """Answer with leading blank chunks."""
        return [("text", chunk) for chunk in chunks]

    out = _run_turn(db_path, iid, "user", "hello", fake)
    assert "".join(out) == "  \nXin chào"
    assert _assistant_rows(db_path, iid)[-1]["content"] == "  \nXin chào"


def test_loop_blank_only_answer_falls_back(tmp_path: Path) -> None:
    """An all-blank answer yields and stores only the fallback."""
    db_path = tmp_path / "blankonly.db"
    iid = _seeded_db(db_path, "ANSWER", 2)

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """Answer with blank chunks only."""
        return [("text", "  "), ("text", "\n")]

    out = _run_turn(db_path, iid, "user", "hello", fake)
    assert out == [prompts.FALLBACK_ANSWER]
    assert _assistant_rows(db_path, iid)[-1]["content"] == prompts.FALLBACK_ANSWER


def test_loop_passes_think_false_every_call(tmp_path: Path) -> None:
    """think=False reaches all 5 calls, including the last tool-free one."""
    db_path = tmp_path / "think.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    seen: list = []

    def fake(model: str, messages: list, tools: list | None = None,
             think: bool | None = None, **kwargs: object) -> list:
        """Record think; ask while tools are offered, then answer."""
        seen.append(think)
        if tools is None:
            return [("text", "done")]
        return [("tool_calls", [{"name": "get_inspection_result",
                                 "arguments": {}}])]

    out = _run_turn(db_path, iid, "explain", None, fake)
    assert out == ["done"]
    assert seen == [False] * 5


def test_chat_body_think_key() -> None:
    """The think key is sent only when think is not None."""
    messages = [{"role": "user", "content": "hi"}]
    assert ollama_client.build_body("m", messages, None, False, 0.0, None,
                                     False)["think"] is False
    assert "think" not in ollama_client.build_body("m", messages, None, False,
                                                   0.0, None, None)


def test_few_shot_examples_in_context_not_in_db(tmp_path: Path) -> None:
    """Examples reach the LLM but are never stored in the database."""
    db_path = tmp_path / "fewshot.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    seen: list = []

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """Capture the context, then answer."""
        seen.append(messages)
        return [("text", "ok")]

    _run_turn(db_path, iid, "explain", None, fake,
              settings=_settings(few_shot=True))
    context = json.dumps(seen[0], ensure_ascii=False)
    assert "Cá này để tủ lạnh được mấy ngày?" in context
    assert "Bạn đoán giúp tôi cá có tươi không?" in context
    assert "Mai trời có mưa không?" in context
    conn = db.connect(db_path)
    try:
        stored = json.dumps(db.get_inspection(conn, iid)["messages"], ensure_ascii=False)
    finally:
        conn.close()
    for snippet in ("Cá này để tủ lạnh được mấy ngày?",
                    "Bạn đoán giúp tôi cá có tươi không?",
                    "Mai trời có mưa không?"):
        assert snippet not in stored


def test_drop_notice_removes_rule(tmp_path: Path) -> None:
    """Dropping the notice removes rule 6 and the rule 7 reminder."""
    db_path = tmp_path / "drop.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    seen: list = []

    def fake(model: str, messages: list, **kwargs: object) -> list:
        """Capture the context, then answer."""
        seen.append(messages)
        return [("text", "ok")]

    _run_turn(db_path, iid, "explain", None, fake,
              settings=_settings(drop_notice=True))
    system = seen[0][0]["content"]
    assert "Luôn nhắc rằng đây là công cụ hỗ trợ" not in system
    assert "câu nhắc công cụ hỗ trợ" not in system
    _run_turn(db_path, iid, "explain", None, fake, settings=_settings())
    assert "Luôn nhắc rằng đây là công cụ hỗ trợ" in seen[1][0]["content"]


def test_think_user_kind_only(tmp_path: Path) -> None:
    """think=true only on user turns when llm_think_user is on."""
    db_path = tmp_path / "thinkuser.db"
    iid = _seeded_db(db_path, "ANSWER", 2)
    seen_user: list = []
    seen_explain: list = []

    def fake_user(model: str, messages: list, think: bool | None = None,
                  **kwargs: object) -> list:
        """Record think on a user turn."""
        seen_user.append(think)
        return [("text", "ok")]

    def fake_explain(model: str, messages: list, think: bool | None = None,
                     **kwargs: object) -> list:
        """Record think on an explain turn."""
        seen_explain.append(think)
        return [("text", "ok")]

    settings = _settings(think=False, think_user=True)
    _run_turn(db_path, iid, "user", "hello", fake_user, settings=settings)
    _run_turn(db_path, iid, "explain", None, fake_explain, settings=settings)
    assert seen_user == [True]
    assert seen_explain == [False]
