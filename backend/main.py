from __future__ import annotations

import importlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.logging_config import generate_trace_id, setup_logging, trace_id_ctx
from backend.middleware import APIKeyMiddleware
from backend.models.database import ensure_data_dirs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    setup_logging(
        structured=os.environ.get("LOG_FORMAT", "").lower() == "json",
    )
    await ensure_data_dirs()
    logger.info("Application started, data directories ensured.")
    yield
    logger.info("Application shutting down.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()

    app = FastAPI(
        title="MedDistill API",
        description="医学教材知识蒸馏、知识图谱与 RAG 问答后端",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS: use configured FRONTEND_URL instead of wildcard.
    # allow_credentials requires explicit origins (not "*").
    allowed_origins = [origin.strip() for origin in settings.FRONTEND_URL.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API key authentication (skipped if API_KEY is empty)
    if settings.API_KEY:
        app.add_middleware(APIKeyMiddleware)

    @app.middleware("http")
    async def add_trace_id(request: Request, call_next):
        """Assign a trace ID to every request for log correlation."""
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
        trace_id_ctx.set(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response

    _include_available_routers(app)

    @app.get("/")
    async def root() -> dict[str, str | list[str]]:
        return {
            "name": "MedDistill API",
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

    router_modules = ("upload", "knowledge_graph", "integration", "rag", "dialogue", "report", "stats", "learning", "teaching")
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
