"""SQLite storage for inspections, images, and agent messages (stdlib only)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    action TEXT,
    label INTEGER,
    p0 REAL,
    p1 REAL,
    p2 REAL,
    conf REAL,
    strangeness REAL,
    nearest_species TEXT,
    n_images INTEGER NOT NULL DEFAULT 0,
    reasons TEXT NOT NULL DEFAULT '[]',
    policy_snapshot TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    file_path TEXT NOT NULL,
    cam_path TEXT NOT NULL,
    logit0 REAL NOT NULL,
    logit1 REAL NOT NULL,
    label INTEGER NOT NULL,
    p0 REAL NOT NULL,
    p1 REAL NOT NULL,
    p2 REAL NOT NULL,
    conf REAL NOT NULL,
    strangeness REAL NOT NULL,
    nearest_species TEXT NOT NULL,
    cam_peak TEXT NOT NULL,
    cam_center_share REAL NOT NULL,
    cam_concentration REAL NOT NULL,
    UNIQUE (inspection_id, seq)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_name TEXT
);
"""


def _now() -> str:
    """Current UTC time as an ISO string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database file, creating the three tables when missing."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def create_inspection(conn: sqlite3.Connection) -> int:
    """Insert a new open inspection and return its id."""
    now = _now()
    cur = conn.execute(
        "INSERT INTO inspections (created_at, updated_at, status) VALUES (?, ?, 'open')",
        (now, now),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_image(conn: sqlite3.Connection, inspection_id: int, seq: int, file_path: str,
              cam_path: str, logit0: float, logit1: float, label: int,
              probs: list[float], conf: float, strangeness: float,
              nearest_species: str, cam_peak: str, cam_center_share: float,
              cam_concentration: float) -> int:
    """Insert one image row for an inspection and return its id."""
    cur = conn.execute(
        """INSERT INTO images (inspection_id, seq, created_at, file_path, cam_path,
            logit0, logit1, label, p0, p1, p2, conf, strangeness, nearest_species,
            cam_peak, cam_center_share, cam_concentration)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (inspection_id, seq, _now(), file_path, cam_path, logit0, logit1, label,
         probs[0], probs[1], probs[2], conf, strangeness, nearest_species,
         cam_peak, cam_center_share, cam_concentration),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_decision(conn: sqlite3.Connection, inspection_id: int, status: str,
                    action: str, label: int | None, probs: list[float], conf: float,
                    strangeness: float, nearest_species: str, n_images: int,
                    reasons: list[str], policy_snapshot: dict[str, Any]) -> None:
    """Write the merged decision back onto the inspection row."""
    conn.execute(
        """UPDATE inspections SET updated_at = ?, status = ?, action = ?, label = ?,
           p0 = ?, p1 = ?, p2 = ?, conf = ?, strangeness = ?, nearest_species = ?,
           n_images = ?, reasons = ?, policy_snapshot = ? WHERE id = ?""",
        (_now(), status, action, label, probs[0], probs[1], probs[2], conf,
         strangeness, nearest_species, n_images, json.dumps(reasons),
         json.dumps(policy_snapshot), inspection_id),
    )
    conn.commit()


def add_message(conn: sqlite3.Connection, inspection_id: int, role: str,
                content: str, tool_name: str | None = None) -> int:
    """Append one chat message (or tool call record) and return its id."""
    cur = conn.execute(
        "INSERT INTO messages (inspection_id, created_at, role, content, tool_name)"
        " VALUES (?, ?, ?, ?, ?)",
        (inspection_id, _now(), role, content, tool_name),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_inspection(conn: sqlite3.Connection, inspection_id: int) -> dict[str, Any] | None:
    """Full inspection detail: row plus images and messages in order."""
    row = conn.execute("SELECT * FROM inspections WHERE id = ?",
                       (inspection_id,)).fetchone()
    if row is None:
        return None
    inspection = dict(row)
    inspection["reasons"] = json.loads(inspection["reasons"])
    inspection["policy_snapshot"] = json.loads(inspection["policy_snapshot"])
    images = [dict(r) for r in conn.execute(
        "SELECT * FROM images WHERE inspection_id = ? ORDER BY seq", (inspection_id,))]
    messages = [dict(r) for r in conn.execute(
        "SELECT * FROM messages WHERE inspection_id = ? ORDER BY id", (inspection_id,))]
    return {"inspection": inspection, "images": images, "messages": messages}


def list_inspections(conn: sqlite3.Connection, limit: int = 20, offset: int = 0,
                     action: str | None = None) -> list[dict]:
    """Inspection rows, newest first, optionally filtered by decision action."""
    if action is None:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM inspections ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset))]
    return [dict(r) for r in conn.execute(
        "SELECT * FROM inspections WHERE action = ? ORDER BY id DESC LIMIT ? OFFSET ?",
        (action, limit, offset))]


def set_status(conn: sqlite3.Connection, inspection_id: int, status: str) -> None:
    """Change only the status (and timestamp) of one inspection."""
    conn.execute("UPDATE inspections SET updated_at = ?, status = ? WHERE id = ?",
                 (_now(), status, inspection_id))
    conn.commit()


def get_stats(conn: sqlite3.Connection, days: int | None = None) -> dict[str, Any]:
    """Aggregate counts for the dashboard: actions, labels, days, confidence.

    Only inspections with at least one image count. With days set, only
    inspections created in the last days days count. Days follow Vietnam
    time (UTC+7), hardcoded because the app serves Vietnam only.
    """
    conds = ["inspections.n_images > 0"]
    params: tuple = ()
    if days is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conds.append("inspections.created_at >= ?")
        params = (cutoff,)
    where = "WHERE " + " AND ".join(conds)
    total = conn.execute(f"SELECT COUNT(*) FROM inspections {where}", params).fetchone()[0]
    by_action = {r[0]: r[1] for r in conn.execute(
        f"SELECT action, COUNT(*) FROM inspections {where} GROUP BY action", params)}
    by_label = {r[0]: r[1] for r in conn.execute(
        f"SELECT label, COUNT(*) FROM inspections {where} GROUP BY label", params)}
    avg_images = conn.execute(
        "SELECT AVG(n) FROM (SELECT COUNT(images.id) AS n FROM inspections"
        f" LEFT JOIN images ON images.inspection_id = inspections.id {where}"
        " GROUP BY inspections.id)", params).fetchone()[0]
    by_day = {r[0]: r[1] for r in conn.execute(
        "SELECT substr(datetime(created_at, '+7 hours'), 1, 10) AS day, COUNT(*)"
        f" FROM inspections {where} GROUP BY day ORDER BY day", params)}
    conf_hist = [0] * 10
    query = "SELECT conf FROM inspections"
    if where:
        query += f" {where} AND conf IS NOT NULL"
    else:
        query += " WHERE conf IS NOT NULL"
    for (conf,) in conn.execute(query, params):
        conf_hist[min(9, int(float(conf) * 10))] += 1
    return {
        "total": total,
        "by_action": by_action,
        "by_label": by_label,
        "avg_images": float(avg_images or 0.0),
        "by_day": by_day,
        "conf_hist": conf_hist,
    }
