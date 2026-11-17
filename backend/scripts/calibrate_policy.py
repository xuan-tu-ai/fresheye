"""Score the 878 test images and write the temporary policy thresholds.

WARNING: do not rerun this script now; it would overwrite policy.json with the
95th percentile and discard the LOSO-chosen threshold (0.35).
"""

from __future__ import annotations

import csv
import json
import socket
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.settings import load_settings
from app.vision import inference, strangeness

CONF_THRESHOLD = 0.95
KNN_K = 10
MAX_IMAGES = 3


def main() -> int:
    """Compute test-image strangeness, save per-image CSV, write policy.json."""
    settings = load_settings()
    device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    print(f"[calibrate] device: {device} | torch {torch.__version__}")
    print(f"[calibrate] bank: {settings.app_data_dir / 'reference' / 'bank_seed7.npz'}")
    loaded = inference.load_model(settings)
    bank = strangeness.load_bank(settings.app_data_dir / "reference" / "bank_seed7.npz")

    repo_root = settings.data_dir.parent
    entries = (repo_root / "release_split" / "test.txt").read_text(encoding="utf-8").splitlines()
    assert len(entries) == 878, f"expected 878 test images, got {len(entries)}"

    rows = []
    for i, entry in enumerate(entries):
        path = Path(settings.data_dir) / entry.strip()
        species, _ = path.parent.name.split(" - ")
        out = inference.predict_image(loaded, Image.open(path).convert("RGB"))
        result = strangeness.score(out["feature"].numpy(), bank, KNN_K)
        rows.append({"path": entry.strip(), "species_true": species.strip(), **result})
        if (i + 1) % 200 == 0:
            print(f"[calibrate] {i + 1}/{len(entries)}")

    values = np.array([row["strangeness"] for row in rows])
    percentiles = {f"p{q}": float(np.percentile(values, q)) for q in (50, 90, 95, 99)}
    for name, value in percentiles.items():
        print(f"[calibrate] {name}: {value:.4f}")

    today = date.today().isoformat()
    policy = {
        "conf_threshold": CONF_THRESHOLD,
        "strangeness_threshold": percentiles["p95"],
        "knn_k": KNN_K,
        "max_images": MAX_IMAGES,
        "provisional": True,
        "conf_threshold_source": "paper (temporary, replaced after LOSO)",
        "strangeness_threshold_source": (
            "95th percentile of test-image strangeness versus bank_seed7 "
            f"(temporary, replaced after LOSO, calibrated {today})"
        ),
        "knn_k_source": "plan P7 default",
        "max_images_source": "plan P9 temporary value",
        "bank": "bank_seed7.npz",
        "percentiles": percentiles,
        "hostname": socket.gethostname(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    policy_path = Path(__file__).resolve().parent.parent / "config" / "policy.json"
    policy_path.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[calibrate] wrote {policy_path}")

    results_dir = settings.app_data_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "strangeness_test_seed7.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "species_true", "strangeness", "nearest_species"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[calibrate] wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
