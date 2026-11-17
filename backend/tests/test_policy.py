"""Table-driven tests for every branch of policy.decide (plan 6.6)."""

from __future__ import annotations

from typing import Any

import torch

from app.policy import Policy, decide
from app.settings import load_policy
from app.vision import core

POLICY = Policy(conf_threshold=0.9, strangeness_threshold=0.5, knn_k=10, max_images=3)


def _result(logit0: float, logit1: float, strang: float) -> dict[str, Any]:
    """One fake image result with given CORN logits and strangeness."""
    return {"logits": torch.tensor([logit0, logit1]), "strangeness": strang}


def test_answer_when_both_thresholds_pass() -> None:
    """One confident familiar image closes the inspection with a label."""
    out = decide([_result(3.0, 3.0, 0.1)], POLICY)
    print(f"[T2.1] answer: {out}")
    assert out["action"] == "ANSWER"
    assert out["label"] == 2
    assert out["reasons"] == []
    assert out["n_images"] == 1


def test_ask_more_on_low_confidence() -> None:
    """Low confidence alone asks for another photo with LOW_CONFIDENCE."""
    out = decide([_result(0.0, 0.0, 0.1)], POLICY)
    print(f"[T2.1] low conf: {out}")
    assert out["action"] == "ASK_MORE"
    assert out["label"] is None
    assert out["reasons"] == ["LOW_CONFIDENCE"]


def test_ask_more_on_strange_image() -> None:
    """High strangeness alone asks for another photo with UNFAMILIAR."""
    out = decide([_result(3.0, 3.0, 0.9)], POLICY)
    print(f"[T2.1] strange: {out}")
    assert out["action"] == "ASK_MORE"
    assert out["reasons"] == ["UNFAMILIAR"]


def test_both_reasons_when_both_fail() -> None:
    """An unsure strange image reports both reason codes."""
    out = decide([_result(0.0, 0.0, 0.9)], POLICY)
    print(f"[T2.1] both bad: {out}")
    assert out["action"] == "ASK_MORE"
    assert out["reasons"] == ["LOW_CONFIDENCE", "UNFAMILIAR"]


def test_abstain_at_max_images() -> None:
    """Three unsure images abstain and carry no freshness label."""
    out = decide([_result(0.0, 0.0, 0.9)] * 3, POLICY)
    print(f"[T2.1] abstain: {out}")
    assert out["action"] == "ABSTAIN"
    assert out["label"] is None
    assert out["n_images"] == 3


def test_second_image_pulls_mean_over_threshold() -> None:
    """Averaged logits cross the confidence threshold on the second photo."""
    first = decide([_result(0.0, 0.0, 0.1)], POLICY)
    assert first["action"] == "ASK_MORE"
    out = decide([_result(0.0, 0.0, 0.1), _result(6.0, 6.0, 0.1)], POLICY)
    print(f"[T2.1] merged: {out}")
    assert out["action"] == "ANSWER"
    assert out["n_images"] == 2


def test_exact_threshold_counts_as_pass() -> None:
    """Values exactly on the thresholds count as passing (>=, <=)."""
    _, _, conf = core.predict(torch.tensor([[3.0, 3.0]]), True)
    exact = Policy(
        conf_threshold=float(conf[0]), strangeness_threshold=0.42, knn_k=10, max_images=3
    )
    out = decide([_result(3.0, 3.0, 0.42)], exact)
    print(f"[T2.1] boundary: {out}")
    assert out["action"] == "ANSWER"


def test_merged_label_matches_core_predict() -> None:
    """The merged label/probs/conf always equal core.predict of mean logits."""
    results = [_result(0.0, 0.0, 0.1), _result(6.0, 6.0, 0.3)]
    out = decide(results, POLICY)
    labels, probs, conf = core.predict(torch.tensor([[3.0, 3.0]]), True)
    assert out["action"] == "ANSWER"
    assert out["label"] == int(labels[0])
    assert out["probs"] == [float(v) for v in probs[0]]
    assert out["conf"] == float(conf[0])
    assert out["strangeness"] == 0.2


def test_load_policy_reads_config() -> None:
    """settings.load_policy exposes the calibrated thresholds with right types."""
    policy = load_policy()
    print(f"[T2.1] policy: {policy}")
    assert policy.conf_threshold == 0.95
    assert 0.0 < policy.strangeness_threshold < 1.0
    assert policy.knn_k == 10
    assert policy.max_images == 3
