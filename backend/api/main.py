"""
CausalCast live backend -- FastAPI app.

This is the "live demo" track (see docs/architecture.md once written):
full network access, meant to run alongside the React frontend for
judges. It shares zero code with the "scored pipeline" track's I/O
layer (src/, run.sh) -- but both tracks call the exact same core/
functions, so their numbers can never diverge on the same input.

Run locally:
    pip install -r backend/requirements-backend.txt
    uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load backend/.env (see backend/.env.example) before anything else so
# ANTHROPIC_API_KEY is available to backend/llm/summarizer.py without
# requiring the operator to export it manually. Safe no-op if the file
# doesn't exist -- backend/llm/summarizer.py already falls back to
# template narration when the key is unset.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .routes import forecast, insights, simulate_budget, upload

app = FastAPI(
    title="CausalCast API",
    description=(
        "Live backend for the CausalCast demo. Every number in every "
        "response is computed by core/ -- the same network-free library "
        "src/predict.py uses for the scored batch pipeline. This layer "
        "only handles HTTP, validation, and JSON shaping."
    ),
    version="0.1.0",
)

# Dev-friendly default: allow the Vite dev server (and any origin) to hit
# the API locally. Tighten allow_origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(forecast.router, prefix="/api", tags=["forecast"])
app.include_router(simulate_budget.router, prefix="/api", tags=["budget"])
app.include_router(insights.router, prefix="/api", tags=["insights"])


@app.get("/health")
async def health():
    return {"status": "ok"}
