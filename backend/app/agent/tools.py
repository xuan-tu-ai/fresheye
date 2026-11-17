"""The single agent tool: read an inspection result as compact JSON.

The tool never exposes image paths or image bytes; the LLM only sees words
and numbers. Level names, probabilities, and Vietnamese labels appear only
for ANSWER decisions.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any

from app import db
from app.policy import Policy
from app.vision import core

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_inspection_result",
        "description": ("Read the result of the currently open inspection. "
                        "Takes no parameters."),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

FRESHNESS_VI = ["Rất tươi", "Tươi", "Không tươi"]
UNFAMILIAR_MEANING = (
    "This score measures how different the photo is from the photos "
    "the model learned on; it is not a smell and not a defect of the fish."
)
ATTENTION_MEANING = (
    "This is the region the model pays attention to; it is not "
    "evidence that the fish is fresh or spoiled."
)


def get_inspection_result(conn: sqlite3.Connection, inspection_id: int,
                          policy: Policy) -> dict[str, Any]:
    """Self-explanatory inspection JSON: decision words, numbers, meanings."""
    detail = db.get_inspection(conn, inspection_id)
    if detail is None:
        return {"error": "Inspection not found."}
    inspection = detail["inspection"]
    images = detail["images"]
    result: dict[str, Any] = {"decision": inspection["action"]}
    if inspection["action"] == "ANSWER":
        label = inspection["label"]
        result["freshness_level"] = core.CLASS_NAMES[label]
        result["freshness_level_vi"] = FRESHNESS_VI[label]
        result["probabilities"] = {
            "Highly Fresh": inspection["p0"],
            "Fresh": inspection["p1"],
            "Not Fresh": inspection["p2"],
        }
    result["confidence"] = inspection["conf"]
    result["confidence_threshold"] = policy.conf_threshold
    result["unfamiliarity"] = {
        "score": inspection["strangeness"],
        "threshold": policy.strangeness_threshold,
        "is_unfamiliar": inspection["strangeness"] > policy.strangeness_threshold,
        "meaning": UNFAMILIAR_MEANING,
    }
    result["most_similar_known_species"] = inspection["nearest_species"]
    result["reasons"] = inspection["reasons"]
    result["photos_taken"] = inspection["n_images"]
    result["max_photos"] = policy.max_images
    result["attention_map"] = {
        "peak_region": Counter(im["cam_peak"] for im in images).most_common(1)[0][0],
        "center_share": sum(im["cam_center_share"] for im in images) / len(images),
        "concentration": sum(im["cam_concentration"] for im in images) / len(images),
        "meaning": ATTENTION_MEANING,
    }
    return result
