"""Extract 768-dim features for the development set into a reference bank."""

from __future__ import annotations

import socket
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import timm
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.settings import load_settings
from app.vision import core, inference


def main() -> int:
    """Build app_data/reference/bank_seed7.npz from release_split/development.txt."""
    settings = load_settings()
    device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    print(f"[bank] device: {device} | torch {torch.__version__} | timm {timm.__version__}")
    print(f"[bank] checkpoint: {settings.checkpoint}")
    loaded = inference.load_model(settings)

    repo_root = settings.data_dir.parent
    entries = (repo_root / "release_split" / "development.txt").read_text(encoding="utf-8").splitlines()
    assert len(entries) == 3512, f"expected 3512 development images, got {len(entries)}"

    features, species_list, labels, paths = [], [], [], []
    for i, entry in enumerate(entries):
        path = Path(settings.data_dir) / entry.strip()
        species, grade = path.parent.name.split(" - ")
        out = inference.predict_image(loaded, Image.open(path).convert("RGB"))
        features.append(out["feature"].numpy())
        species_list.append(species.strip())
        labels.append(core.LABEL_MAP[grade.strip()])
        paths.append(entry.strip())
        if (i + 1) % 500 == 0:
            print(f"[bank] {i + 1}/{len(entries)}")

    features_arr = np.stack(features).astype(np.float32)
    labels_arr = np.array(labels, dtype=np.int64)
    print(f"[bank] images: {features_arr.shape[0]}, feature dim: {features_arr.shape[1]}")
    assert features_arr.shape == (3512, 768), features_arr.shape

    for species, count in sorted(Counter(species_list).items()):
        print(f"[bank] species {species}: {count}")
    names = ["Highly Fresh", "Fresh", "Not Fresh"]
    for label, count in sorted(Counter(labels).items()):
        print(f"[bank] label {names[label]}: {count}")
    assert sum(Counter(species_list).values()) == len(entries)

    dest = settings.app_data_dir / "reference" / "bank_seed7.npz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        dest,
        features=features_arr,
        species=np.array(species_list),
        labels=labels_arr,
        paths=np.array(paths),
        hostname=np.array(socket.gethostname()),
        device=np.array(device),
        torch_version=np.array(torch.__version__),
        checkpoint=np.array(str(settings.checkpoint)),
        invoked=np.array("build_reference_bank.py"),
        timestamp=np.array(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    print(f"[bank] wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
