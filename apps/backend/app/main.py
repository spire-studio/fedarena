"""FedArena API — FastAPI application entry point.

Start with:
    PYTHONPATH=libs:apps/backend/runners uv run uvicorn apps.backend.app.main:app \\
        --host 0.0.0.0 --port 8000 \\
        --reload --reload-dir apps/backend/app

The --reload-dir flag prevents uvicorn from restarting when the evaluation
worker writes new submission files under libs/.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import select

from .api.v1.router import api_router
from .db import get_session, init_db
from .models import BenchJob, EvaluationJob, Submission
from .services.task_queue import init_queue, shutdown_queue

logger = logging.getLogger("fedarena.startup")


async def _recover_stale_jobs() -> None:
    """Mark orphaned running/evaluating jobs as failed on startup."""
    async for session in get_session():
        stale_jobs = (
            (await session.execute(select(EvaluationJob).where(EvaluationJob.status.in_(["running", "queued"]))))
            .scalars()
            .all()
        )
        for job in stale_jobs:
            job.status = "failed"
            job.error = "Server restarted while job was running"
            session.add(job)
            sub = await session.get(Submission, job.submission_id)
            if sub and sub.status in ("evaluating", "pending"):
                sub.status = "failed"
                session.add(sub)
        stale_bench = (
            (await session.execute(select(BenchJob).where(BenchJob.status.in_(["running", "queued"])))).scalars().all()
        )
        for job in stale_bench:
            job.status = "failed"
            job.error = "Server restarted while job was running"
            session.add(job)

        total_stale = len(stale_jobs) + len(stale_bench)
        if total_stale:
            await session.commit()
            logger.info("Recovered %d stale jobs on startup", total_stale)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    init_queue(max_workers=1)
    await _recover_stale_jobs()
    yield
    shutdown_queue()


app = FastAPI(
    title="FedArena API",
    version="0.2.0",
    description="Attack/Defense evaluation arena for Federated Learning",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
