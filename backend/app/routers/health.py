"""GET /api/health: versions, device, files, bank, policy, and the LLM provider."""

from __future__ import annotations

import httpx
import torch
import timm
from fastapi import APIRouter, Request

from app.settings import Settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def get_health(request: Request) -> dict:
    """Report backend health: build info, files, bank, policy, LLM provider."""
    settings: Settings = request.app.state.settings
    cuda = torch.cuda.is_available()
    bank = request.app.state.bank
    policy = request.app.state.policy
    ollama = False
    if settings.llm_provider == "ollama":
        try:
            ollama = httpx.get(f"{settings.ollama_url}/", timeout=2.0).status_code == 200
        except httpx.HTTPError:
            ollama = False
    # A hosted provider counts as ready once a key is configured; the key is never reported.
    llm_ready = bool(settings.api_key) if settings.llm_provider == "api" else ollama
    return {
        "status": "ok",
        "torch_version": torch.__version__,
        "timm_version": timm.__version__,
        "device": "cuda" if cuda else "cpu",
        "device_name": torch.cuda.get_device_name(0) if cuda else "",
        "checkpoint": str(settings.checkpoint),
        "checkpoint_exists": settings.checkpoint.is_file(),
        "final_config": str(settings.final_config),
        "final_config_exists": settings.final_config.is_file(),
        "bank_loaded": True,
        "bank_images": int(bank.features.shape[0]),
        "bank_dim": int(bank.features.shape[1]),
        "policy": {
            "conf_threshold": policy.conf_threshold,
            "strangeness_threshold": policy.strangeness_threshold,
            "knn_k": policy.knn_k,
            "max_images": policy.max_images,
        },
        "ollama_reachable": ollama,
        "llm_provider": settings.llm_provider,
        "llm_model": (settings.api_model if settings.llm_provider == "api"
                      else settings.llm_model),
        "llm_ready": llm_ready,
    }
