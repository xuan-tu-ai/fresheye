#!/usr/bin/env python3
"""Model, losses, data split, and prediction rule for fish-eye freshness grading.

Primitives shared by the selection, training, and evaluation scripts. The data
split is drawn once from a fixed SPLIT_SEED and is independent of the training
seed, so the held-out test set is identical for every run.
"""

from __future__ import annotations

import os
import random

import numpy as np
import timm
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from sklearn.model_selection import StratifiedKFold, train_test_split
from torch.utils.data import Dataset
from torchvision import transforms

# ── Fixed configuration ─────────────────────────────────────────────────────
MODEL_NAME = "swin_tiny_patch4_window7_224"
NUM_CLASSES = 3
IMG_SIZE = 224
NUM_WORKERS = 2
DATA_ROOT = "data"
SPLIT_SEED = 42          # governs the 80/20 split AND the 5 dev folds; never varies
TEST_FRACTION = 0.20
N_FOLDS = 5
LABEL_MAP = {"Highly Fresh": 0, "Fresh": 1, "Not Fresh": 2}
CLASS_NAMES = ["Highly Fresh", "Fresh", "Not Fresh"]
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

DEFAULT_HP = {
    "lr": 1e-4,
    "weight_decay": 1e-2,
    "drop_path": 0.1,
    "gamma": 2.0,
    "pct_start": 0.1,
    "batch_size": 32,
    "aff_degrees": 20,
    "aff_translate": 0.05,
    "rerase_p": 0.4,
}

# Architecture x loss configurations compared during selection.
CONFIGS = {
    "ce_gap":              {"dual_pool": False, "head": "ce",   "loss": "ce"},
    "ce_gapgmp":           {"dual_pool": True,  "head": "ce",   "loss": "ce"},
    "corn_gap_std":        {"dual_pool": False, "head": "corn", "loss": "corn_std"},
    "corn_gap_ours":       {"dual_pool": False, "head": "corn", "loss": "corn_ours"},
    "corn_gapgmp_std":     {"dual_pool": True,  "head": "corn", "loss": "corn_std"},
    "focalcorn_gap_std":   {"dual_pool": False, "head": "corn", "loss": "focalcorn_std"},
    "focalcorn_gap_ours":  {"dual_pool": False, "head": "corn", "loss": "focalcorn_ours"},
    "focalcorn_gapgmp_std":{"dual_pool": True,  "head": "corn", "loss": "focalcorn_std"},
    # Diagnostic ablation: focal weighting without the ordinal head.
    "focalce_gap":         {"dual_pool": False, "head": "ce",   "loss": "focal_ce"},
}


# ── Model ───────────────────────────────────────────────────────────────────
class FreshnessModel(nn.Module):
    """Swin backbone + pooling + (ordinal or nominal) linear head.

    ``timm``'s ``forward_features`` already applies the trailing LayerNorm, so no
    further normalisation is applied here.
    """

    def __init__(self, model_name: str = MODEL_NAME, num_classes: int = NUM_CLASSES,
                 pretrained: bool = True, drop_path_rate: float = 0.0,
                 dual_pool: bool = False, ordinal: bool = True):
        super().__init__()
        self.dual_pool = dual_pool
        self.ordinal = ordinal
        self.backbone = timm.create_model(
            model_name, pretrained=pretrained, num_classes=0,
            drop_path_rate=drop_path_rate,
        )
        nf = self.backbone.num_features
        out_dim = (num_classes - 1) if ordinal else num_classes
        self.fc = nn.Linear(nf * 2 if dual_pool else nf, out_dim)

    def _pool(self, x: torch.Tensor) -> torch.Tensor:
        x = self.backbone.forward_features(x)
        if x.dim() == 4:                      # B, H, W, C
            gap, gmp = x.mean(dim=[1, 2]), x.amax(dim=[1, 2])
        elif x.dim() == 3:                    # B, N, C
            gap, gmp = x.mean(dim=1), x.amax(dim=1)
        else:
            gap, gmp = x.mean(dim=[-2, -1]), x.amax(dim=[-2, -1])
        return torch.cat([gap, gmp], dim=1) if self.dual_pool else gap

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self._pool(x))


# ── Losses ──────────────────────────────────────────────────────────────────
def ce_loss(logits, labels, num_classes=NUM_CLASSES, gamma=0.0):
    return F.cross_entropy(logits, labels)


def focal_ce_loss(logits, labels, num_classes=NUM_CLASSES, gamma=2.0):
    """Focal-weighted cross-entropy on the nominal head (Lin et al., 2017).

    The same modulating factor used inside the CORN losses, applied to the
    three-class softmax instead. Isolates the focal weighting from the
    ordinal parameterisation; at gamma = 0 it reduces to ``ce_loss``.
    """
    ce = F.cross_entropy(logits, labels, reduction="none")
    p = torch.exp(-ce)
    return ((1.0 - p) ** gamma * ce).mean()


def _corn_terms(logits, labels, num_classes, gamma, focal):
    """Per-(example, task) losses over the conditional subsets.

    Returns the concatenated element-wise losses and the per-task means.
    """
    flat, task_means = [], []
    for k in range(num_classes - 1):
        mask = (labels >= k).nonzero(as_tuple=False).squeeze(1)
        if mask.numel() == 0:
            continue
        target = (labels[mask] > k).float()
        bce = F.binary_cross_entropy_with_logits(
            logits[mask, k], target, reduction="none")
        if focal:
            p = torch.exp(-bce)
            bce = (1.0 - p) ** gamma * bce
        flat.append(bce)
        task_means.append(bce.mean())
    return flat, task_means


def corn_std(logits, labels, num_classes=NUM_CLASSES, gamma=0.0):
    """Standard CORN loss (Shi et al., 2023): example-weighted across thresholds."""
    flat, _ = _corn_terms(logits, labels, num_classes, gamma, focal=False)
    allterms = torch.cat(flat)
    return allterms.sum() / allterms.numel()


def corn_ours(logits, labels, num_classes=NUM_CLASSES, gamma=0.0):
    """Threshold-averaged CORN variant: unweighted mean of per-threshold means."""
    _, means = _corn_terms(logits, labels, num_classes, gamma, focal=False)
    return torch.stack(means).mean()


def focalcorn_std(logits, labels, num_classes=NUM_CLASSES, gamma=2.0):
    """Focal-weighted CORN, example-weighted across thresholds."""
    flat, _ = _corn_terms(logits, labels, num_classes, gamma, focal=True)
    allterms = torch.cat(flat)
    return allterms.sum() / allterms.numel()


def focalcorn_ours(logits, labels, num_classes=NUM_CLASSES, gamma=2.0):
    """Focal-weighted CORN, unweighted mean of per-threshold means."""
    _, means = _corn_terms(logits, labels, num_classes, gamma, focal=True)
    return torch.stack(means).mean()


LOSSES = {
    "ce": ce_loss,
    "focal_ce": focal_ce_loss,
    "corn_std": corn_std,
    "corn_ours": corn_ours,
    "focalcorn_std": focalcorn_std,
    "focalcorn_ours": focalcorn_ours,
}


# ── Prediction rule (single, shared by every metric) ─────────────────────────
def predict(logits: torch.Tensor, ordinal: bool):
    """Return (labels, probs, confidence) under one consistent rule.

    Ordinal: label by CORN cumulative-product decoding; probabilities by the same
    cumulative products; confidence is the probability of the decoded label.
    Nominal: softmax argmax with its own probability.
    """
    if ordinal:
        f = torch.sigmoid(logits)
        labels = (torch.cumprod(f, dim=1) > 0.5).sum(dim=1).long()
        f0, f1 = f[:, 0], f[:, 1]
        probs = torch.stack([1 - f0, f0 * (1 - f1), f0 * f1], dim=1)
        probs = probs.clamp(min=1e-12)
        probs = probs / probs.sum(dim=1, keepdim=True)
    else:
        probs = torch.softmax(logits, dim=1)
        labels = probs.argmax(dim=1).long()
    conf = probs.gather(1, labels.view(-1, 1)).squeeze(1)
    return labels, probs, conf


# ── Data ────────────────────────────────────────────────────────────────────
def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_index(data_root: str = DATA_ROOT):
    """Sorted directory listing for a reproducible ordering."""
    paths, labels, strata = [], [], []
    for cls_name in sorted(os.listdir(data_root)):
        folder = os.path.join(data_root, cls_name)
        if not os.path.isdir(folder):
            continue
        parts = cls_name.split(" - ")
        if len(parts) != 2:
            continue
        label = LABEL_MAP.get(parts[1].strip())
        if label is None:
            continue
        for fn in sorted(os.listdir(folder)):
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                paths.append(os.path.join(folder, fn))
                labels.append(label)
                strata.append(cls_name)          # species x class -> 24 strata
    return np.array(paths), np.array(labels), np.array(strata)


def make_split(data_root: str = DATA_ROOT):
    """The single, fixed 80/20 species-stratified split. Independent of training seed."""
    paths, labels, strata = load_index(data_root)
    idx = np.arange(len(paths))
    dev_idx, test_idx = train_test_split(
        idx, test_size=TEST_FRACTION, stratify=strata, random_state=SPLIT_SEED)
    return np.sort(dev_idx), np.sort(test_idx), paths, labels, strata


def make_folds(dev_idx: np.ndarray, strata: np.ndarray, n_folds: int = N_FOLDS):
    """Species-stratified 5-fold partition of the development set."""
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=SPLIT_SEED)
    return [(dev_idx[tr], dev_idx[va]) for tr, va in skf.split(dev_idx, strata[dev_idx])]


class FishDataset(Dataset):
    def __init__(self, paths, labels, transform):
        self.paths, self.labels, self.transform = list(paths), list(labels), transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        return self.transform(Image.open(self.paths[i]).convert("RGB")), self.labels[i]


def build_transforms(hp: dict):
    train_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.5),
        transforms.RandomAffine(degrees=hp["aff_degrees"],
                                translate=(hp["aff_translate"], hp["aff_translate"])),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
        transforms.RandomErasing(p=hp["rerase_p"], scale=(0.02, 0.1), ratio=(0.3, 3.3)),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    return train_tf, eval_tf


def build_model(cfg: dict, hp: dict, pretrained: bool = True) -> FreshnessModel:
    return FreshnessModel(
        MODEL_NAME, NUM_CLASSES, pretrained=pretrained,
        drop_path_rate=hp["drop_path"], dual_pool=cfg["dual_pool"],
        ordinal=(cfg["head"] == "corn"),
    ).to(DEVICE)
