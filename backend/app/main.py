"""
FastAPI Main Application Entrypoint for Agent Evaluation & Reliability Platform.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.services.supabase_store import supabase_store

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if supabase_store._sb:
        logger.info("✅ Supabase connected — persistent storage active.")
    else:
        logger.warning(
            "⚠️  Supabase not configured — running in-memory fallback mode. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in backend/.env to enable persistence."
        )
    yield
    # Shutdown (nothing to close for Supabase REST client)

app = FastAPI(
    title="AI Agent Evaluation and Reliability Engine",
    description="Continuous integration, red-teaming, sandboxed execution & reliability scoring for autonomous agents.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "AI Agent Evaluation & Reliability Platform",
        "version": "2.0.0",
        "docs_url": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
