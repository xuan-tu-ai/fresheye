"""Check the core.py copy matches the paper original's SHA-256."""

from __future__ import annotations

import hashlib
from pathlib import Path

EXPECTED_SHA256 = "114616fcdc91847717ba17d86b452d30a45e6f7a436154d7a442c5e141bb9713"


def test_core_copy_matches_original() -> None:
    """The copy must be byte-identical to the paper original (no edits)."""
    copied = Path(__file__).resolve().parent.parent / "app" / "vision" / "core.py"
    digest = hashlib.sha256(copied.read_bytes()).hexdigest()
    print(f"[T1.1] SHA-256 of the copy: {digest}")
    assert digest == EXPECTED_SHA256, "core.py differs from the paper original"
