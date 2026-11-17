"""Pydantic request/response shapes for the inspection API."""

from __future__ import annotations

from pydantic import BaseModel


class ImageOut(BaseModel):
    seq: int
    label: int
    probs: list[float]
    conf: float
    strangeness: float
    nearest_species: str
    cam_peak: str
    cam_center_share: float
    cam_concentration: float
    image_url: str
    cam_url: str


class DecisionOut(BaseModel):
    action: str
    label: int | None
    probs: list[float]
    conf: float
    strangeness: float
    nearest_species: str
    n_images: int
    reasons: list[str]


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    tool_name: str | None
    created_at: str


class InspectionOut(BaseModel):
    id: int
    status: str
    created_at: str
    updated_at: str
    decision: DecisionOut | None
    images: list[ImageOut]
    messages: list[MessageOut]


class ImageUploadOut(BaseModel):
    inspection_id: int
    status: str
    image: ImageOut
    decision: DecisionOut


class ChatRequest(BaseModel):
    kind: str
    message: str | None = None


class StatsOut(BaseModel):
    total: int
    by_action: dict[str, int]
    by_label: dict[str, int]
    avg_images: float
    by_day: dict[str, int]
    conf_hist: list[int]
