"""Database tests on a temporary file with hand-counted expectations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import db


def _image(seq: int, label: int = 2, conf: float = 0.97) -> dict:
    """One fake image row with fixed EigenCAM summary values."""
    return {
        "seq": seq, "file_path": f"uploads/1/{seq}.jpg", "cam_path": f"cams/1/{seq}.png",
        "logit0": 3.0, "logit1": 3.0, "label": label, "probs": [0.05, 0.05, 0.9],
        "conf": conf, "strangeness": 0.2, "nearest_species": "Chanos Chanos",
        "cam_peak": "trung tâm", "cam_center_share": 0.3, "cam_concentration": 0.5,
    }


def test_crud_round_trip_in_order(tmp_path: Path) -> None:
    """Create, images, decision, and messages read back fully and in order."""
    conn = db.connect(tmp_path / "test.db")
    iid = db.create_inspection(conn)
    img1 = _image(1)
    img2 = _image(2)
    db.add_image(conn, iid, **img1)
    db.add_image(conn, iid, **img2)
    db.update_decision(conn, iid, status="closed", action="ANSWER", label=2,
                       probs=[0.05, 0.05, 0.9], conf=0.97, strangeness=0.2,
                       nearest_species="Chanos Chanos", n_images=2,
                       reasons=[], policy_snapshot={"conf_threshold": 0.95})
    db.add_message(conn, iid, role="user", content="hello")
    db.add_message(conn, iid, role="assistant", content="world")

    detail = db.get_inspection(conn, iid)
    assert detail is not None
    assert detail["inspection"]["status"] == "closed"
    assert detail["inspection"]["action"] == "ANSWER"
    assert detail["inspection"]["label"] == 2
    assert detail["inspection"]["reasons"] == []
    assert detail["inspection"]["policy_snapshot"] == {"conf_threshold": 0.95}
    assert [im["seq"] for im in detail["images"]] == [1, 2]
    assert detail["images"][0]["cam_peak"] == "trung tâm"
    assert [m["content"] for m in detail["messages"]] == ["hello", "world"]
    assert db.get_inspection(conn, 999999) is None
    conn.close()


def test_stats_match_hand_counts(tmp_path: Path) -> None:
    """Dashboard aggregates equal counts computed by hand."""
    conn = db.connect(tmp_path / "stats.db")
    first = db.create_inspection(conn)
    db.add_image(conn, first, **_image(1))
    db.add_image(conn, first, **_image(2))
    db.update_decision(conn, first, status="closed", action="ANSWER", label=2,
                       probs=[0.05, 0.05, 0.9], conf=0.97, strangeness=0.2,
                       nearest_species="Chanos Chanos", n_images=2,
                       reasons=[], policy_snapshot={})
    second = db.create_inspection(conn)
    db.add_image(conn, second, **_image(1, label=1, conf=0.5))
    db.update_decision(conn, second, status="open", action="ASK_MORE", label=None,
                       probs=[0.5, 0.25, 0.25], conf=0.5, strangeness=0.9,
                       nearest_species="Nibea Albiflora", n_images=1,
                       reasons=["LOW_CONFIDENCE"], policy_snapshot={})
    third = db.create_inspection(conn)
    for seq in (1, 2, 3):
        db.add_image(conn, third, **_image(seq, conf=0.4))
    db.update_decision(conn, third, status="closed", action="ABSTAIN", label=None,
                       probs=[0.5, 0.25, 0.25], conf=0.4, strangeness=0.9,
                       nearest_species="Nibea Albiflora", n_images=3,
                       reasons=["LOW_CONFIDENCE", "UNFAMILIAR"], policy_snapshot={})

    listed = db.list_inspections(conn)
    assert [r["id"] for r in listed] == [third, second, first]
    stats = db.get_stats(conn)
    print(f"[T3.1] stats: {stats}")
    assert stats["total"] == 3
    assert stats["by_action"] == {"ANSWER": 1, "ASK_MORE": 1, "ABSTAIN": 1}
    assert stats["by_label"] == {2: 1, None: 2}
    assert stats["avg_images"] == 2.0
    assert sum(stats["by_day"].values()) == 3
    assert sum(stats["conf_hist"]) == 3
    assert stats["conf_hist"][9] == 1
    conn.close()


def test_stats_days_window(tmp_path: Path) -> None:
    """days=7 counts only the last week of hand-made 10-day data."""
    conn = db.connect(tmp_path / "days.db")
    now = datetime.now(timezone.utc)
    for day in range(10):
        stamp = (now - timedelta(days=day)).isoformat()
        conn.execute("INSERT INTO inspections (created_at, updated_at, status, action,"
                     " n_images) VALUES (?, ?, 'closed', 'ANSWER', 1)", (stamp, stamp))
    conn.commit()
    full = db.get_stats(conn)
    week = db.get_stats(conn, days=7)
    print(f"[B3] total {full['total']}, last-7-days {week['total']}")
    assert full["total"] == 10
    assert week["total"] == 7
    assert sum(week["by_day"].values()) == 7
    assert week["by_action"] == {"ANSWER": 7}
    conn.close()


def test_stats_skip_empty_inspections_and_vietnam_day(tmp_path: Path) -> None:
    """Empty inspections count nowhere; days follow Vietnam time (UTC+7)."""
    conn = db.connect(tmp_path / "empty.db")
    ghost = db.create_inspection(conn)
    assert ghost > 0
    first = conn.execute("INSERT INTO inspections (created_at, updated_at, status,"
                         " action, label, n_images) VALUES ('2026-10-03T18:00:00+00:00',"
                         " '2026-10-03T18:00:00+00:00', 'closed', 'ANSWER', 1, 2)"
                         ).lastrowid
    for seq in (1, 2):
        db.add_image(conn, first, seq, f"u/{seq}.jpg", f"c/{seq}.png", 0.0, 0.0, 1,
                     [0.0, 1.0, 0.0], 1.0, 0.1, "Chanos Chanos", "trung tâm",
                     0.3, 0.5)
    conn.execute("INSERT INTO inspections (created_at, updated_at, status, action,"
                 " label, n_images) VALUES ('2026-10-03T10:00:00+00:00',"
                 " '2026-10-03T10:00:00+00:00', 'open', 'ASK_MORE', NULL, 0)")
    conn.commit()
    stats = db.get_stats(conn)
    print(f"[VIEC2] stats: {stats}")
    assert stats["total"] == 1
    assert stats["avg_images"] == 2.0
    assert stats["by_action"] == {"ANSWER": 1}
    assert None not in stats["by_action"]
    assert stats["by_label"] == {1: 1}
    assert stats["by_day"] == {"2026-10-04": 1}
    conn.close()
