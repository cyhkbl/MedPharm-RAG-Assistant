from __future__ import annotations

import importlib
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.models.database import ensure_data_dirs

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    app = FastAPI(
        title="MedPharm RAG Assistant API",
        description="医学教材知识整合、知识图谱与 RAG 问答后端",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有来源（部署到 Vercel/Railway 需要）
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _include_available_routers(app)

    @app.on_event("startup")
    async def on_startup() -> None:
        await ensure_data_dirs()

    @app.get("/")
    async def root() -> dict[str, str | list[str]]:
        return {
            "name": "MedPharm RAG Assistant API",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
            "features": ["textbook parsing", "knowledge graph", "integration", "rag", "dialogue"],
        }

    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


def _include_available_routers(app: FastAPI) -> None:
    """Mount routers from api modules when those modules exist."""

    router_modules = ("upload", "knowledge_graph", "integration", "rag", "dialogue", "report")
    for module_name in router_modules:
        try:
            module = importlib.import_module(f"backend.api.{module_name}")
        except ModuleNotFoundError as error:
            if error.name == f"backend.api.{module_name}":
                continue
            raise

        router = getattr(module, "router", None)
        if router is None:
            logger.warning("backend.api.%s has no router; skipped", module_name)
            continue
        app.include_router(router)


app = create_app()
