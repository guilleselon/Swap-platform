"""FastAPI application factory.

Run in dev:
    uvicorn app.main:app --reload

The routers for /api/chains, /api/quotes and /api/swap/prepare are
already scaffolded in app/api/routes/ but not yet wired here — see the
commented block near the bottom of ``create_app``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import register_exception_handlers

APP_TITLE = "Swap Aggregator"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = (
    "Multi-chain, multi-DEX swap aggregator. "
    "Backend-only: never holds private keys, never custodies funds."
)

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app() -> FastAPI:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # --- Health check -------------------------------------------------------
    @app.get("/health", tags=["meta"])
    async def health() -> JSONResponse:
        return JSONResponse(
            {"status": "ok", "version": APP_VERSION}
        )

    # --- Routers------------------
    from app.api.routes import chains, quotes, swap
    app.include_router(chains.router, prefix="/api", tags=["chains"])
    app.include_router(quotes.router, prefix="/api", tags=["quotes"])
    app.include_router(swap.router,   prefix="/api", tags=["swap"])

    # --- Frontend (SPA) — mounted last so /api/* takes priority -------------
    if (FRONTEND_DIR / "index.html").exists():
        app.mount(
            "/",
            StaticFiles(directory=str(FRONTEND_DIR), html=True),
            name="frontend",
        )

    return app


app = create_app()


def run() -> None:
    """Console-script entry point (``swap-aggregator``)."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "dev") == "dev",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
