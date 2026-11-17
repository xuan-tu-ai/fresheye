"""GET /api/stats: dashboard aggregates."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, Request

from app import db
from app.routers.inspections import get_conn
from app.schemas import StatsOut

router = APIRouter(prefix="/api", tags=["stats"])


def _str_keys(counts: dict) -> dict[str, int]:
    """JSON-safe keys, marking missing values as none."""
    return {str(k) if k is not None else "none": v for k, v in counts.items()}


@router.get("/stats", response_model=StatsOut)
def read_stats(request: Request, days: int | None = Query(default=None, ge=1),
               conn: sqlite3.Connection = Depends(get_conn)) -> StatsOut:
    """Dashboard counts, optionally restricted to the last days days."""
    raw = db.get_stats(conn, days)
    return StatsOut(
        total=raw["total"],
        by_action=_str_keys(raw["by_action"]),
        by_label=_str_keys(raw["by_label"]),
        avg_images=raw["avg_images"],
        by_day=raw["by_day"],
        conf_hist=raw["conf_hist"],
    )
