"""Tests for the strangeness score and the temporary policy threshold."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.settings import load_settings
from app.vision import inference, strangeness


def _setup() -> tuple:
    """Load settings, the reference bank, and the calibrated policy."""
    settings = load_settings()
    bank = strangeness.load_bank(settings.app_data_dir / "reference" / "bank_seed7.npz")
    policy_path = Path(__file__).resolve().parent.parent / "config" / "policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    return settings, bank, policy


def test_ood_images_exceed_threshold() -> None:
    """Random noise and a non-eye photo score above the strangeness threshold."""
    settings, bank, policy = _setup()
    device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    print(f"[T1.5] device: {device}")
    threshold = float(policy["strangeness_threshold"])
    k = int(policy["knn_k"])
    loaded = inference.load_model(settings)
    rng = np.random.default_rng(0)
    noise = Image.fromarray(rng.integers(0, 256, (224, 224, 3), dtype=np.uint8), mode="RGB")
    plain = Image.new("RGB", (224, 224), (120, 120, 120))
    for name, image in (("noise", noise), ("plain", plain)):
        out = inference.predict_image(loaded, image)
        result = strangeness.score(out["feature"].numpy(), bank, k)
        print(f"[T1.5] {name}: strangeness {result['strangeness']:.4f} vs threshold {threshold:.4f}")
        assert result["strangeness"] > threshold, name


def test_test_images_below_p99_and_species_report() -> None:
    """Typical test images stay below p99; report the nearest-species match rate."""
    settings, bank, policy = _setup()
    p99 = float(policy["percentiles"]["p99"])
    k = int(policy["knn_k"])
    loaded = inference.load_model(settings)
    repo_root = settings.data_dir.parent
    entries = (repo_root / "release_split" / "test.txt").read_text(encoding="utf-8").splitlines()
    assert len(entries) == 878

    scored = []
    for entry in entries:
        path = Path(settings.data_dir) / entry.strip()
        species, _ = path.parent.name.split(" - ")
        out = inference.predict_image(loaded, Image.open(path).convert("RGB"))
        result = strangeness.score(out["feature"].numpy(), bank, k)
        scored.append((result["strangeness"], result["nearest_species"] == species.strip()))

    median_strangeness = float(np.median([s for s, _ in scored]))
    hits = sum(1 for _, hit in scored if hit)
    rate = hits / len(scored)
    print(f"[T1.5] median test strangeness: {median_strangeness:.4f} vs p99 {p99:.4f}")
    print(f"[T1.5] nearest-species match: {hits}/{len(scored)} = {rate * 100:.2f}% (report only)")
    assert median_strangeness <= p99
