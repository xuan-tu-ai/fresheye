"""Load the vision checkpoint and run single-image CORN inference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import torch
from PIL import Image
from torchvision import transforms

from app.settings import Settings
from app.vision import core


@dataclass(frozen=True)
class LoadedModel:
    """Eval-mode model plus its transform and CORN ordinal flag."""

    model: core.FreshnessModel
    transform: transforms.Compose
    ordinal: bool


def load_model(settings: Settings) -> LoadedModel:
    """Build the model from final_config.json and load the seed7 checkpoint."""
    raw = json.loads(settings.final_config.read_text(encoding="utf-8"))
    cfg, hp = raw["cfg"], raw["hp"]
    model = core.build_model(cfg, hp, pretrained=False)
    state = torch.load(settings.checkpoint, map_location=core.DEVICE)
    model.load_state_dict(state)
    model.eval()
    _, eval_tf = core.build_transforms(hp)
    return LoadedModel(model=model, transform=eval_tf, ordinal=(cfg["head"] == "corn"))


def predict_image(loaded: LoadedModel, image: Image.Image) -> dict[str, Any]:
    """Run one cropped eye photo through the model without gradients."""
    x = loaded.transform(image).unsqueeze(0).to(core.DEVICE)
    with torch.no_grad():
        feature = loaded.model._pool(x)
        logits = loaded.model.fc(feature)
        spatial = loaded.model.backbone.forward_features(x)
        labels, probs, conf = core.predict(logits, loaded.ordinal)
    return {
        "logits": logits[0].cpu(),
        "label": int(labels[0]),
        "probs": probs[0].cpu(),
        "conf": float(conf[0]),
        "feature": feature[0].cpu(),
        "spatial": spatial[0].cpu(),
    }
