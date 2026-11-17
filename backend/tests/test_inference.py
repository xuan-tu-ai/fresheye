"""Regression test: inference over the 878 test images must match seed7.npz."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.settings import load_settings
from app.vision import inference


def test_matches_seed7_predictions() -> None:
    """Predicted labels 878/878, max prob diff below 1e-4, accuracy 90.66%."""
    settings = load_settings()
    device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    print(f"[T1.2] device: {device} | torch {torch.__version__}")
    print(f"[T1.2] checkpoint: {settings.checkpoint}")
    loaded = inference.load_model(settings)

    repo_root = settings.data_dir.parent
    entries = (repo_root / "release_split" / "test.txt").read_text(encoding="utf-8").splitlines()
    ref = np.load(repo_root / "outputs" / "clean" / "test" / "seed7.npz")
    y_true, y_pred, probs = ref["y_true"], ref["y_pred"], ref["probs"]
    assert len(entries) == 878 == len(y_true) == len(y_pred) == len(probs)

    match = 0
    max_diff = 0.0
    for i, entry in enumerate(entries):
        image = Image.open(Path(settings.data_dir) / entry.strip()).convert("RGB")
        out = inference.predict_image(loaded, image)
        if i == 0:
            assert out["feature"].shape == (768,), out["feature"].shape
            assert out["spatial"].shape[-1] == 768, out["spatial"].shape
        if out["label"] == int(y_pred[i]):
            match += 1
        diff = float(np.abs(out["probs"].numpy() - probs[i]).max())
        max_diff = max(max_diff, diff)

    accuracy = float((y_pred == y_true).mean())
    print(f"[T1.2] label match: {match}/878")
    print(f"[T1.2] max prob diff: {max_diff:.6f}")
    print(f"[T1.2] accuracy: {accuracy * 100:.2f}%")
    assert match == 878, f"only {match}/878 labels match"
    assert max_diff < 1e-4, f"max prob diff {max_diff}"
    assert round(accuracy * 100, 2) == 90.66, f"accuracy {accuracy * 100:.4f}%"
