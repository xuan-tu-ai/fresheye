"""Strangeness of an eye photo versus the development reference bank."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Bank:
    """L2-normalized reference features with species labels."""

    features: np.ndarray
    species: np.ndarray
    labels: np.ndarray
    paths: np.ndarray


def load_bank(path: str | Path) -> Bank:
    """Load a reference bank saved by build_reference_bank.py."""
    raw = np.load(path)
    features = np.asarray(raw["features"], dtype=np.float64)
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    return Bank(
        features=(features / np.maximum(norms, 1e-12)).astype(np.float32),
        species=np.asarray(raw["species"]),
        labels=np.asarray(raw["labels"]),
        paths=np.asarray(raw["paths"]),
    )


def score(feature: np.ndarray, bank: Bank, k: int) -> dict[str, Any]:
    """Mean cosine distance to the k nearest bank rows and majority species."""
    vec = np.asarray(feature, dtype=np.float64).ravel()
    vec = vec / max(float(np.linalg.norm(vec)), 1e-12)
    sims = bank.features.astype(np.float64) @ vec
    top = np.argpartition(sims, -k)[-k:]
    return {
        "strangeness": float(np.mean(1.0 - sims[top])),
        "nearest_species": str(Counter(bank.species[top].tolist()).most_common(1)[0][0]),
    }
