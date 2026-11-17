"""Build the FastAPI app; vision model and bank load once at startup."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import chat, health, inspections, stats
from app.settings import load_policy, load_settings
from app.vision import inference, strangeness


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load settings, model, bank, and policy once; serve files; nothing to shut down."""
    settings = load_settings()
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    app.state.settings = settings
    app.state.loaded = inference.load_model(settings)
    app.state.bank = strangeness.load_bank(
        settings.app_data_dir / "reference" / "bank_seed7.npz")
    app.state.policy = load_policy()
    app.state.db_path = settings.app_data_dir / "app.db"
    app.mount("/media", StaticFiles(directory=settings.app_data_dir), name="media")
    dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend_dist"
    if dist.is_dir():
        @app.get("/{full_path:path}", include_in_schema=False)
        async def frontend(full_path: str) -> FileResponse:
            """Serve the built frontend file, or index.html for client routes."""
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    yield


def create_app() -> FastAPI:
    """Create the FastAPI app with config from settings.json."""
    app = FastAPI(title="Fish freshness", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(inspections.router)
    app.include_router(chat.router)
    app.include_router(stats.router)
    return app


app = create_app()
