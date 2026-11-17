"""POST /api/inspections/{id}/chat: streamed agent answers (SSE)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app import db
from app.agent import loop
from app.routers.inspections import get_conn
from app.schemas import ChatRequest

router = APIRouter(prefix="/api/inspections", tags=["chat"])


@router.post("/{inspection_id}/chat")
def chat(inspection_id: int, body: ChatRequest, request: Request,
         conn: sqlite3.Connection = Depends(get_conn)) -> StreamingResponse:
    """Stream one agent turn as server-sent events."""
    if db.get_inspection(conn, inspection_id) is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    if body.kind not in ("explain", "user"):
        raise HTTPException(status_code=422, detail="Kind must be explain or user.")
    if body.kind == "user" and not (body.message or "").strip():
        raise HTTPException(status_code=422, detail="Message is required for kind user.")
    settings = request.app.state.settings

    def events() -> Iterator[str]:
        """Yield one SSE data line per text chunk, then a done marker."""
        for chunk in loop.run_turn(conn, settings, inspection_id,
                                   body.kind, body.message):
            yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
        yield "data: {\"done\": true}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
