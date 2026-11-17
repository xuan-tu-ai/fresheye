"""API tests for the inspection flow (7.2) with the real model and database."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db
from app.main import app
from app.settings import load_settings


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    """One app instance; writes go to a scratch dir, reads stay real."""
    scratch = tmp_path_factory.mktemp("app_data")
    with TestClient(app) as test_client:
        real_settings = app.state.settings
        app.state.settings = replace(real_settings, app_data_dir=scratch)
        app.state.db_path = scratch / "app.db"
        try:
            yield test_client
        finally:
            app.state.settings = real_settings
            app.state.db_path = real_settings.app_data_dir / "app.db"


def _test_db():
    """Connection to the scratch database the app under test writes to."""
    return db.connect(app.state.settings.app_data_dir / "app.db")


def _answer_case() -> dict:
    """First test-set row passing both live thresholds, with its expected label."""
    settings = load_settings()
    csv_path = settings.app_data_dir / "results" / "replay_policy_seed7.csv"
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if (row["action_both"] == "ANSWER" and float(row["conf"]) >= 0.95
                    and float(row["strangeness"]) <= 0.35):
                return {"path": row["path"], "label": int(row["label_both"])}
    raise AssertionError("no row passes both thresholds in the replay CSV")


def test_upload_high_confidence_image_answers_and_closes(client: TestClient) -> None:
    """A confident test image returns its seed7 label and closes the inspection."""
    case = _answer_case()
    settings = load_settings()
    created = client.post("/api/inspections")
    assert created.status_code == 200
    iid = created.json()["id"]
    assert created.json()["status"] == "open"
    with (settings.data_dir / case["path"]).open("rb") as f:
        resp = client.post(
            f"/api/inspections/{iid}/images",
            files={"file": (case["path"].rsplit("/", 1)[-1], f, "image/jpeg")},
        )
    assert resp.status_code == 200
    body = resp.json()
    print(f"[T3.2] upload: action {body['decision']['action']}, "
          f"label {body['decision']['label']}")
    assert body["decision"]["action"] == "ANSWER"
    assert body["decision"]["label"] == case["label"]
    assert body["status"] == "closed"
    assert body["image"]["seq"] == 1
    scratch = app.state.settings.app_data_dir
    assert (scratch / f"uploads/{iid}/1.jpg").is_file()
    assert (scratch / f"cams/{iid}/1.png").is_file()
    detail = client.get(f"/api/inspections/{iid}")
    assert detail.status_code == 200
    assert len(detail.json()["images"]) == 1


def test_noise_images_ask_more_then_abstain_and_close(client: TestClient) -> None:
    """Three noise uploads ask twice then abstain; the fourth is rejected."""
    iid = client.post("/api/inspections").json()["id"]
    rng = np.random.default_rng(7)
    buffer = io.BytesIO()
    Image.fromarray(rng.integers(0, 256, (300, 300, 3), dtype=np.uint8)).save(
        buffer, format="JPEG")
    payload = buffer.getvalue()
    actions = []
    for _ in range(3):
        resp = client.post(f"/api/inspections/{iid}/images",
                           files={"file": ("noise.jpg", payload, "image/jpeg")})
        assert resp.status_code == 200
        actions.append(resp.json()["decision"]["action"])
    print(f"[T3.2] noise actions: {actions}")
    assert actions == ["ASK_MORE", "ASK_MORE", "ABSTAIN"]
    fourth = client.post(f"/api/inspections/{iid}/images",
                         files={"file": ("noise.jpg", payload, "image/jpeg")})
    assert fourth.status_code == 409


def test_bad_uploads_rejected(client: TestClient) -> None:
    """Text uploads fail with 422; unknown inspections fail with 404."""
    iid = client.post("/api/inspections").json()["id"]
    bad = client.post(f"/api/inspections/{iid}/images",
                      files={"file": ("note.txt", b"not an image", "text/plain")})
    assert bad.status_code == 422
    assert client.get("/api/inspections/999999999").status_code == 404
    missing = client.post("/api/inspections/999999999/images",
                          files={"file": ("x.jpg", b"zzz", "image/jpeg")})
    assert missing.status_code == 404


def test_list_inspections_newest_first(client: TestClient) -> None:
    """The list matches the database row count, newest first."""
    conn = _test_db()
    try:
        expected = [row["id"] for row in db.list_inspections(conn, limit=100)]
    finally:
        conn.close()
    resp = client.get("/api/inspections?limit=100")
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()]
    print(f"[T3.3] inspections: {len(ids)} rows")
    assert ids == expected


def test_stats_match_direct_counts(client: TestClient) -> None:
    """GET /api/stats equals the aggregates read straight from the database."""
    conn = _test_db()
    try:
        expected = db.get_stats(conn)
    finally:
        conn.close()
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    print(f"[T3.3] stats: total {body['total']}, avg {body['avg_images']}")
    assert body["total"] == expected["total"]
    assert body["avg_images"] == expected["avg_images"]
    assert body["conf_hist"] == expected["conf_hist"]
    assert body["by_day"] == expected["by_day"]
    for key in ("by_action", "by_label"):
        assert body[key] == {str(k) if k is not None else "none": v
                             for k, v in expected[key].items()}


def test_media_serves_uploaded_file(client: TestClient) -> None:
    """An uploaded eye photo and its EigenCAM are retrievable under /media."""
    case = _answer_case()
    settings = load_settings()
    iid = client.post("/api/inspections").json()["id"]
    with (settings.data_dir / case["path"]).open("rb") as f:
        body = client.post(
            f"/api/inspections/{iid}/images",
            files={"file": (case["path"].rsplit("/", 1)[-1], f, "image/jpeg")},
        ).json()
    for url in (body["image"]["image_url"], body["image"]["cam_url"]):
        resp = client.get(url)
        print(f"[T3.3] media {url}: {resp.status_code}, {resp.headers['content-type']}")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/")
        assert len(resp.content) > 0


def test_health_reports_bank_policy_ollama(client: TestClient) -> None:
    """Health exposes bank state, active thresholds, and Ollama reachability."""
    body = client.get("/api/health").json()
    print(f"[T3.3] health: bank {body['bank_images']}x{body['bank_dim']}, "
          f"ollama {body['ollama_reachable']}")
    assert body["checkpoint_exists"] is True
    assert body["bank_loaded"] is True
    assert body["bank_images"] == 3512
    assert body["bank_dim"] == 768
    assert body["policy"]["conf_threshold"] == 0.95
    assert isinstance(body["ollama_reachable"], bool)


def test_chat_errors(client: TestClient) -> None:
    """Unknown inspections give 404; bad kinds and missing messages give 422."""
    assert client.post("/api/inspections/999999999/chat",
                       json={"kind": "explain"}).status_code == 404
    iid = client.post("/api/inspections").json()["id"]
    assert client.post(f"/api/inspections/{iid}/chat",
                       json={"kind": "shout"}).status_code == 422
    assert client.post(f"/api/inspections/{iid}/chat",
                       json={"kind": "user"}).status_code == 422
    assert client.post(f"/api/inspections/{iid}/chat",
                       json={"kind": "user", "message": "  "}).status_code == 422


def test_chat_streams_with_fake_llm(client: TestClient, monkeypatch) -> None:
    """Fake turn streams two chunks and a done marker as server-sent events."""
    from app.agent import loop as loop_module

    def fake(conn, settings, inspection_id, kind, message=None, **kwargs):
        """Yield two chunks without touching the database."""
        assert kind == "explain"
        yield "hello "
        yield "world"

    monkeypatch.setattr(loop_module, "run_turn", fake)
    iid = client.post("/api/inspections").json()["id"]
    resp = client.post(f"/api/inspections/{iid}/chat", json={"kind": "explain"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    texts = [json.loads(line[6:])["text"] for line in resp.text.splitlines()
             if line.startswith("data: ") and "text" in line]
    assert texts == ["hello ", "world"]
    assert '{"done": true}' in resp.text


def test_close_inspection(client: TestClient) -> None:
    """Closing an ASK_MORE inspection keeps its decision and blocks uploads."""
    iid = client.post("/api/inspections").json()["id"]
    rng = np.random.default_rng(11)
    buffer = io.BytesIO()
    Image.fromarray(rng.integers(0, 256, (300, 300, 3), dtype=np.uint8)).save(
        buffer, format="JPEG")
    payload = buffer.getvalue()
    first = client.post(f"/api/inspections/{iid}/images",
                        files={"file": ("noise.jpg", payload, "image/jpeg")})
    assert first.status_code == 200
    assert first.json()["decision"]["action"] == "ASK_MORE"
    closed = client.post(f"/api/inspections/{iid}/close")
    assert closed.status_code == 200
    body = closed.json()
    print(f"[B1] closed: {body['status']}, {body['decision']['action']}")
    assert body["status"] == "closed"
    assert body["decision"]["action"] == "ASK_MORE"
    assert body["decision"]["label"] is None
    extra = client.post(f"/api/inspections/{iid}/images",
                        files={"file": ("noise.jpg", payload, "image/jpeg")})
    assert extra.status_code == 409
    assert client.post(f"/api/inspections/{iid}/close").status_code == 409
    assert client.post("/api/inspections/999999999/close").status_code == 404


def test_list_filter_by_action(client: TestClient) -> None:
    """Each action filter matches the direct database counts."""
    conn = _test_db()
    try:
        expected = {a: len(db.list_inspections(conn, limit=100, action=a))
                    for a in ("ANSWER", "ASK_MORE", "ABSTAIN")}
    finally:
        conn.close()
    for action, count in expected.items():
        resp = client.get(f"/api/inspections?action={action}&limit=100")
        assert resp.status_code == 200
        items = resp.json()
        print(f"[B2] action {action}: {len(items)} rows")
        assert len(items) == count
        assert all(it["decision"]["action"] == action for it in items)
    assert client.get("/api/inspections?action=MAYBE").status_code == 422


def test_stats_days_param(client: TestClient) -> None:
    """days restricts stats; invalid values are rejected."""
    conn = _test_db()
    try:
        expected = db.get_stats(conn, days=7)
    finally:
        conn.close()
    resp = client.get("/api/stats?days=7")
    assert resp.status_code == 200
    print(f"[B3] days=7 total: {resp.json()['total']}")
    assert resp.json()["total"] == expected["total"]
    assert client.get("/api/stats?days=0").status_code == 422
    assert client.get("/api/stats?days=nope").status_code == 422
