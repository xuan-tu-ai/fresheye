"""Deterministic decision rule over one inspection's images (plan 6.6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from app.vision import core


@dataclass(frozen=True)
class Policy:
    conf_threshold: float
    strangeness_threshold: float
    knn_k: int
    max_images: int


def decide(results: list[dict[str, Any]], policy: Policy) -> dict[str, Any]:
    """Average CORN logits, decode with core.predict, then apply both thresholds."""
    mean = torch.stack(
        [torch.as_tensor(item["logits"], dtype=torch.float32) for item in results]
    ).mean(dim=0, keepdim=True)
    labels, probs, conf = core.predict(mean, True)  # pinned checkpoint is a CORN head
    label = int(labels[0])
    confidence = float(conf[0])
    strang = float(sum(float(item["strangeness"]) for item in results) / len(results))
    reasons = []
    if confidence < policy.conf_threshold:
        reasons.append("LOW_CONFIDENCE")
    if strang > policy.strangeness_threshold:
        reasons.append("UNFAMILIAR")
    final_label: int | None
    if not reasons:
        action, final_label = "ANSWER", label
    elif len(results) < policy.max_images:
        action, final_label = "ASK_MORE", None
    else:
        action, final_label = "ABSTAIN", None
    return {
        "action": action,
        "label": final_label,
        "probs": [float(v) for v in probs[0]],
        "conf": confidence,
        "strangeness": strang,
        "reasons": reasons,
        "n_images": len(results),
    }
