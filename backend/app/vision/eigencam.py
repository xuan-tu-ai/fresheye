"""EigenCAM saliency plus PNG overlay and numeric summary.

`eigencam` and `upscale` are verbatim copies from the paper release script
`release/focalcorn-swin-ffe/src/make_eigencam.py`. `overlay_png` and
`describe` are new helpers for the web app.
"""

from __future__ import annotations

import io
from typing import Any

import numpy as np
import torch
from matplotlib import cm
from PIL import Image

from app.vision import core

_PEAK_NAMES = (
    ("trên-trái", "phía trên", "trên-phải"),
    ("bên trái", "trung tâm", "bên phải"),
    ("dưới-trái", "phía dưới", "dưới-phải"),
)


def eigencam(model: core.FreshnessModel, x: torch.Tensor) -> np.ndarray:
    """First-principal-component saliency of the final-stage activations."""
    with torch.no_grad():
        feat = model.backbone.forward_features(x)      # B, H, W, C
    if feat.dim() == 3:                                 # B, N, C -> B, H, W, C
        n = feat.shape[1]
        s = int(round(n ** 0.5))
        feat = feat.reshape(feat.shape[0], s, s, feat.shape[2])
    a = feat[0].detach().cpu().numpy()                  # H, W, C
    h, w, c = a.shape
    flat = a.reshape(h * w, c)
    flat = flat - flat.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(flat, full_matrices=False)
    sal = (flat @ vt[0]).reshape(h, w)
    if sal.sum() < 0:                                   # sign of a PC is arbitrary
        sal = -sal
    sal = np.maximum(sal, 0)
    return sal / (sal.max() + 1e-12)


def upscale(sal: np.ndarray, size: int) -> np.ndarray:
    """Nearest-then-smooth resize, so no extra dependency is needed."""
    r = np.kron(sal, np.ones((size // sal.shape[0] + 1, size // sal.shape[1] + 1)))[:size, :size]
    k = 9
    pad = np.pad(r, k // 2, mode="edge")
    out = np.zeros_like(r)
    for i in range(k):
        for j in range(k):
            out += pad[i:i + r.shape[0], j:j + r.shape[1]]
    return out / (k * k)


def overlay_png(sal: np.ndarray) -> bytes:
    """Render saliency with the jet colormap as 224x224 RGBA PNG bytes.

    Opacity follows attention: low-saliency areas stay nearly transparent so
    the eye photo shows through, high-saliency areas are opaque.
    """
    big = upscale(np.asarray(sal, dtype=np.float64), 224)
    rgb = (cm.jet(big)[..., :3] * 255).astype(np.uint8)
    alpha = (np.clip(big, 0.0, 1.0) * 255).astype(np.uint8)
    rgba = np.dstack([rgb, alpha])
    image = Image.fromarray(rgba, mode="RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def describe(sal: np.ndarray) -> dict[str, Any]:
    """Summarize a 7x7 saliency map: peak cell name, center share, concentration."""
    values = np.asarray(sal, dtype=np.float64)
    peak_i, peak_j = (int(v) for v in np.unravel_index(np.argmax(values), values.shape))
    total = float(values.sum())
    center = float(values[2:5, 2:5].sum())
    top10 = float(np.sort(values.ravel())[-10:].sum())
    return {
        "peak": _PEAK_NAMES[min(2, peak_i * 3 // 7)][min(2, peak_j * 3 // 7)],
        "center_share": center / total if total > 0 else 0.0,
        "concentration": top10 / total if total > 0 else 0.0,
    }
