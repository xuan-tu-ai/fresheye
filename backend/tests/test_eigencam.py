"""Tests for the EigenCAM saliency map, PNG overlay, and numeric summary."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.settings import load_settings
from app.vision import core, eigencam, inference


def _first_test_image() -> Image.Image:
    """Open the first image listed in release_split/test.txt."""
    settings = load_settings()
    repo_root = settings.data_dir.parent
    first = (repo_root / "release_split" / "test.txt").read_text(encoding="utf-8").splitlines()[0]
    return Image.open(Path(settings.data_dir) / first.strip()).convert("RGB")


def test_saliency_shape_and_range() -> None:
    """Saliency is 7x7, inside [0, 1], with max exactly 1."""
    loaded = inference.load_model(load_settings())
    x = loaded.transform(_first_test_image()).unsqueeze(0).to(core.DEVICE)
    sal = eigencam.eigencam(loaded.model, x)
    print(f"[T1.3] saliency shape: {sal.shape}, min: {sal.min():.4f}, max: {sal.max():.6f}")
    assert sal.shape == (7, 7), sal.shape
    assert float(sal.min()) >= 0.0
    assert abs(float(sal.max()) - 1.0) < 1e-6


def test_overlay_png_size() -> None:
    """The overlay PNG opens and is 224x224 RGBA."""
    loaded = inference.load_model(load_settings())
    x = loaded.transform(_first_test_image()).unsqueeze(0).to(core.DEVICE)
    sal = eigencam.eigencam(loaded.model, x)
    image = Image.open(io.BytesIO(eigencam.overlay_png(sal)))
    print(f"[T1.3] overlay size: {image.size}, mode: {image.mode}")
    assert image.size == (224, 224)
    assert image.mode == "RGBA"


def test_overlay_alpha_follows_attention() -> None:
    """Alpha is lower at the least-attended pixel than at the peak."""
    peak = np.zeros((7, 7))
    peak[3, 3] = 1.0
    pixels = np.asarray(Image.open(io.BytesIO(eigencam.overlay_png(peak))))
    assert pixels.shape == (224, 224, 4)
    assert int(pixels[0, 0, 3]) < int(pixels[115, 115, 3])


def test_describe_values_pinned() -> None:
    """describe() numbers stay fixed for a centered synthetic peak."""
    peak = np.zeros((7, 7))
    peak[3, 3] = 1.0
    summary = eigencam.describe(peak)
    print(f"[VIEC3] summary: {summary}")
    assert summary["peak"] == "trung tâm"
    assert summary["center_share"] == 1.0
    assert summary["concentration"] == 1.0


def test_describe_ratios_and_center_peak() -> None:
    """Both ratios lie in [0, 1]; a synthetic center peak is named correctly."""
    loaded = inference.load_model(load_settings())
    x = loaded.transform(_first_test_image()).unsqueeze(0).to(core.DEVICE)
    summary = eigencam.describe(eigencam.eigencam(loaded.model, x))
    print(f"[T1.3] summary: {summary}")
    assert 0.0 <= summary["center_share"] <= 1.0
    assert 0.0 <= summary["concentration"] <= 1.0

    synthetic = np.zeros((7, 7))
    synthetic[3, 3] = 1.0
    assert eigencam.describe(synthetic)["peak"] == "trung tâm"
