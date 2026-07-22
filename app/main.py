"""DevLog API — a tiny personal tracker for studies, work and projects.

The app is deliberately small: the real product of this repository is the
delivery pipeline around it (Docker, CI, GitOps with Argo CD, Kubernetes,
Prometheus/Grafana). See README.md.
"""

from fastapi import FastAPI, HTTPException, Query, Request
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from app import models
from app.info import runtime_info

app = FastAPI(title="DevLog API", version="0.1.0")

# Exposes GET /metrics in Prometheus format (request count, latency, errors).
# Custom study metrics will be added in the observability phase.
Instrumentator().instrument(app).expose(app)

VALID_TYPES = {"study", "work", "project"}


class EntryIn(BaseModel):
    type: str = Field(examples=["study"])
    what: str = Field(min_length=3, examples=["Wrote my first Deployment manifest"])
    tags: list[str] = Field(default_factory=list, examples=[["kubernetes", "kind"]])
    minutes: int = Field(default=0, ge=0, le=24 * 60)


@app.post("/entries", status_code=201)
def create_entry(entry: EntryIn) -> dict:
    if entry.type not in VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"type must be one of {sorted(VALID_TYPES)}",
        )
    return models.add_entry(entry.type, entry.what, entry.tags, entry.minutes)


@app.get("/entries")
def list_entries(
    tag: str | None = Query(default=None, description="filter by tag"),
    days: int | None = Query(default=None, ge=1, description="only the last N days"),
) -> list[dict]:
    return models.list_entries(tag=tag, days=days)


@app.get("/stats")
def stats() -> dict:
    return models.stats()


@app.get("/weekly")
def weekly() -> dict:
    return models.weekly()


@app.get("/info")
def info(request: Request) -> dict:
    return runtime_info(request)


@app.get("/health")
def health() -> dict:
    """Liveness/readiness probe target for Kubernetes (used from Phase 2 on)."""
    return {"status": "ok"}
