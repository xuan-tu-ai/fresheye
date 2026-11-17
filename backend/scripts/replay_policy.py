"""Replay the one-image rule over the 878 test images, twice.

Variant A uses only the confidence threshold, variant B uses both thresholds.
The confidence-only numbers must exactly match the values computed directly
from seed7.npz; the script asserts that and exits nonzero otherwise.
"""

from __future__ import annotations

import csv
import socket
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.policy import Policy, decide
from app.settings import load_policy, load_settings
from app.vision import inference, strangeness


def main() -> int:
    """Run both variants, print metrics, save the per-image CSV, self-check."""
    settings = load_settings()
    device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    stamp = {
        "hostname": socket.gethostname(),
        "device": device,
        "torch_version": torch.__version__,
        "checkpoint": str(settings.checkpoint),
        "invoked": "replay_policy.py",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(f"[replay] {stamp}")
    policy = load_policy()
    conf_only = Policy(
        conf_threshold=policy.conf_threshold,
        strangeness_threshold=float("inf"),
        knn_k=policy.knn_k,
        max_images=policy.max_images,
    )

    loaded = inference.load_model(settings)
    bank = strangeness.load_bank(settings.app_data_dir / "reference" / "bank_seed7.npz")
    repo_root = settings.data_dir.parent
    entries = (repo_root / "release_split" / "test.txt").read_text(encoding="utf-8").splitlines()
    ref = np.load(repo_root / "outputs" / "clean" / "test" / "seed7.npz")
    y_true, y_pred, ref_conf = ref["y_true"], ref["y_pred"], ref["conf"]
    assert len(entries) == 878 == len(y_true)

    rows = []
    for i, entry in enumerate(entries):
        path = Path(settings.data_dir) / entry.strip()
        out = inference.predict_image(loaded, Image.open(path).convert("RGB"))
        result = strangeness.score(out["feature"].numpy(), bank, policy.knn_k)
        single = {"logits": out["logits"], "strangeness": result["strangeness"]}
        answer_a = decide([single], conf_only)
        answer_b = decide([single], policy)
        rows.append(
            {
                "path": entry.strip(),
                "y_true": int(y_true[i]),
                "conf": out["conf"],
                "strangeness": result["strangeness"],
                "action_conf": answer_a["action"],
                "label_conf": answer_a["label"] if answer_a["label"] is not None else "",
                "action_both": answer_b["action"],
                "label_both": answer_b["label"] if answer_b["label"] is not None else "",
            }
        )
        if (i + 1) % 200 == 0:
            print(f"[replay] {i + 1}/{len(entries)}")

    for name, action_key, label_key in (("conf-only", "action_conf", "label_conf"),
                                        ("both", "action_both", "label_both")):
        answered = [r for r in rows if r[action_key] == "ANSWER"]
        labels = np.array([int(r[label_key]) for r in answered])
        truth = np.array([r["y_true"] for r in answered])
        coverage = len(answered) / len(rows)
        accuracy = float((labels == truth).mean()) if answered else 0.0
        danger = int(((truth == 2) & (labels == 0)).sum())
        print(f"[replay] {name}: coverage {coverage * 100:.2f}% "
              f"({len(answered)}/{len(rows)}), accuracy {accuracy * 100:.2f}%, "
              f"NotFresh->HighlyFresh {danger}")

    mask = ref_conf >= policy.conf_threshold
    conf_rows = [r for r in rows if r["action_conf"] == "ANSWER"]
    assert len(conf_rows) == int(mask.sum()), "coverage differs from seed7.npz"
    assert sum(1 for r in conf_rows if int(r["label_conf"]) == r["y_true"]) == int(
        (y_pred[mask] == y_true[mask]).sum()
    ), "accuracy differs from seed7.npz"
    print("[replay] self-check against seed7.npz: exact match")

    results_dir = settings.app_data_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "replay_policy_seed7.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["path", "y_true", "conf", "strangeness", "action_conf",
                        "label_conf", "action_both", "label_both",
                        "hostname", "timestamp", "torch_version"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "hostname": stamp["hostname"],
                             "timestamp": stamp["timestamp"],
                             "torch_version": stamp["torch_version"]})
    print(f"[replay] wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
