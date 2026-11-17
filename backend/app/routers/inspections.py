"""Inspection endpoints: create, upload eye photos, read back (flow 7.2)."""

from __future__ import annotations

import io
import sqlite3
from collections import Counter
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from PIL import Image, UnidentifiedImageError

from app import db
from app.policy import decide
from app.schemas import DecisionOut, ImageOut, ImageUploadOut, InspectionOut, MessageOut
from app.vision import core, eigencam, inference, strangeness

router = APIRouter(prefix="/api/inspections", tags=["inspections"])


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """Open a per-request SQLite connection, closed after the request."""
    conn = db.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def _image_out(row: dict[str, Any]) -> ImageOut:
    """Shape one stored image row for the API."""
    return ImageOut(
        seq=row["seq"],
        label=row["label"],
        probs=[row["p0"], row["p1"], row["p2"]],
        conf=row["conf"],
        strangeness=row["strangeness"],
        nearest_species=row["nearest_species"],
        cam_peak=row["cam_peak"],
        cam_center_share=row["cam_center_share"],
        cam_concentration=row["cam_concentration"],
        image_url=f"/media/{row['file_path']}",
        cam_url=f"/media/{row['cam_path']}",
    )


def _decision_out(inspection: dict[str, Any]) -> DecisionOut | None:
    """Shape the merged decision, or None before the first upload."""
    if inspection["action"] is None:
        return None
    return DecisionOut(
        action=inspection["action"],
        label=inspection["label"],
        probs=[inspection["p0"], inspection["p1"], inspection["p2"]],
        conf=inspection["conf"],
        strangeness=inspection["strangeness"],
        nearest_species=inspection["nearest_species"],
        n_images=inspection["n_images"],
        reasons=inspection["reasons"],
    )


def _inspection_out(detail: dict[str, Any]) -> InspectionOut:
    """Shape a full inspection detail row for the API."""
    inspection = detail["inspection"]
    return InspectionOut(
        id=inspection["id"],
        status=inspection["status"],
        created_at=inspection["created_at"],
        updated_at=inspection["updated_at"],
        decision=_decision_out(inspection),
        images=[_image_out(row) for row in detail["images"]],
        messages=[MessageOut(**row) for row in detail["messages"]],
    )


@router.post("", response_model=InspectionOut)
def create_inspection(request: Request,
                      conn: sqlite3.Connection = Depends(get_conn)) -> InspectionOut:
    """Open a new inspection."""
    detail = db.get_inspection(conn, db.create_inspection(conn))
    assert detail is not None
    return _inspection_out(detail)


@router.post("/{inspection_id}/images", response_model=ImageUploadOut)
async def upload_image(inspection_id: int, file: UploadFile, request: Request,
                       conn: sqlite3.Connection = Depends(get_conn)) -> ImageUploadOut:
    """Score one cropped eye photo and merge it into the inspection decision."""
    detail = db.get_inspection(conn, inspection_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    inspection = detail["inspection"]
    policy = request.app.state.policy
    if inspection["status"] != "open" or inspection["n_images"] >= policy.max_images:
        raise HTTPException(status_code=409, detail="Inspection is closed.")
    try:
        pil = Image.open(io.BytesIO(await file.read())).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="File is not a decodable image.") from exc

    settings = request.app.state.settings
    loaded = request.app.state.loaded
    bank = request.app.state.bank
    seq = inspection["n_images"] + 1
    rel_img = f"uploads/{inspection_id}/{seq}.jpg"
    rel_cam = f"cams/{inspection_id}/{seq}.png"
    abs_img = settings.app_data_dir / rel_img
    abs_img.parent.mkdir(parents=True, exist_ok=True)
    pil.save(abs_img, format="JPEG")

    out = inference.predict_image(loaded, pil)
    scored = strangeness.score(out["feature"].numpy(), bank, policy.knn_k)
    tensor = loaded.transform(pil).unsqueeze(0).to(core.DEVICE)
    saliency = eigencam.eigencam(loaded.model, tensor)
    summary = eigencam.describe(saliency)
    abs_cam = settings.app_data_dir / rel_cam
    abs_cam.parent.mkdir(parents=True, exist_ok=True)
    abs_cam.write_bytes(eigencam.overlay_png(saliency))

    db.add_image(
        conn, inspection_id, seq, rel_img, rel_cam,
        float(out["logits"][0]), float(out["logits"][1]), out["label"],
        [float(v) for v in out["probs"]], out["conf"], scored["strangeness"],
        scored["nearest_species"], summary["peak"], summary["center_share"],
        summary["concentration"],
    )

    fresh = db.get_inspection(conn, inspection_id)
    assert fresh is not None
    rows = fresh["images"]
    merged = decide(
        [{"logits": [r["logit0"], r["logit1"]], "strangeness": r["strangeness"]}
         for r in rows],
        policy,
    )
    status = "closed" if merged["action"] in ("ANSWER", "ABSTAIN") else "open"
    db.update_decision(
        conn, inspection_id, status, merged["action"], merged["label"],
        merged["probs"], merged["conf"], merged["strangeness"],
        Counter(r["nearest_species"] for r in rows).most_common(1)[0][0],
        merged["n_images"], merged["reasons"],
        {"conf_threshold": policy.conf_threshold,
         "strangeness_threshold": policy.strangeness_threshold,
         "knn_k": policy.knn_k, "max_images": policy.max_images},
    )

    final = db.get_inspection(conn, inspection_id)
    assert final is not None
    decision = _decision_out(final["inspection"])
    assert decision is not None
    return ImageUploadOut(
        inspection_id=inspection_id,
        status=status,
        image=_image_out(final["images"][-1]),
        decision=decision,
    )


@router.get("", response_model=list[InspectionOut])
def list_all(request: Request, limit: int = Query(default=20, ge=1, le=100),
             offset: int = Query(default=0, ge=0),
             action: str | None = Query(default=None),
             conn: sqlite3.Connection = Depends(get_conn)) -> list[InspectionOut]:
    """List inspections, newest first, optionally filtered by decision action."""
    if action is not None and action not in ("ANSWER", "ASK_MORE", "ABSTAIN"):
        raise HTTPException(status_code=422, detail="Unknown action filter.")
    out = []
    for row in db.list_inspections(conn, limit, offset, action):
        detail = db.get_inspection(conn, row["id"])
        assert detail is not None
        out.append(_inspection_out(detail))
    return out


@router.get("/{inspection_id}", response_model=InspectionOut)
def read_inspection(inspection_id: int, request: Request,
                    conn: sqlite3.Connection = Depends(get_conn)) -> InspectionOut:
    """One inspection with every image and message."""
    detail = db.get_inspection(conn, inspection_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    return _inspection_out(detail)


@router.post("/{inspection_id}/close", response_model=InspectionOut)
def close_inspection(inspection_id: int, request: Request,
                     conn: sqlite3.Connection = Depends(get_conn)) -> InspectionOut:
    """Close an open inspection, keeping its current decision."""
    detail = db.get_inspection(conn, inspection_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Inspection not found.")
    if detail["inspection"]["status"] != "open":
        raise HTTPException(status_code=409, detail="Inspection is already closed.")
    db.set_status(conn, inspection_id, "closed")
    closed = db.get_inspection(conn, inspection_id)
    assert closed is not None
    return _inspection_out(closed)
