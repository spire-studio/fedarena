"""Job progress polling and control routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ...db import get_session
from ...models import BenchJob, EvaluationJob, Submission
from ...schemas import JobProgress
from ...services.task_queue import get_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


class QueueStatusResponse(BaseModel):
    total: int
    running: int
    pending: int
    tasks: list[dict]


class JobListItem(BaseModel):
    id: int
    job_type: str  # "evaluation" | "bench"
    status: str
    label: str
    submission_id: int | None = None
    progress: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str


@router.get("", response_model=list[JobListItem])
async def list_jobs(session: AsyncSession = Depends(get_session)):
    eval_stmt = (
        select(EvaluationJob, Submission.display_name)
        .join(Submission, Submission.id == EvaluationJob.submission_id, isouter=True)
        .order_by(EvaluationJob.created_at.desc())
        .limit(50)
    )
    eval_rows = (await session.execute(eval_stmt)).all()

    bench_stmt = select(BenchJob).order_by(BenchJob.bench_created_at.desc()).limit(50)
    bench_rows = (await session.execute(bench_stmt)).scalars().all()

    items: list[JobListItem] = []
    for job, display_name in eval_rows:
        items.append(
            JobListItem(
                id=job.id,
                job_type="evaluation",
                status=job.status,
                label=display_name or f"Submission #{job.submission_id}",
                submission_id=job.submission_id,
                progress=job.progress,
                error=job.error,
                started_at=str(job.started_at) if job.started_at else None,
                completed_at=str(job.completed_at) if job.completed_at else None,
                created_at=str(job.created_at),
            )
        )
    for job in bench_rows:
        items.append(
            JobListItem(
                id=job.id,
                job_type="bench",
                status=job.status,
                label=job.prompt[:80] if job.prompt else f"Bench #{job.id}",
                error=job.error,
                started_at=str(job.started_at) if job.started_at else None,
                completed_at=str(job.completed_at) if job.completed_at else None,
                created_at=str(job.bench_created_at),
            )
        )

    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:50]


@router.get("/queue/status", response_model=QueueStatusResponse)
async def queue_status():
    """Get current task queue status."""
    return get_queue().status()


@router.get("/{job_id}/progress", response_model=JobProgress)
async def get_job_progress(
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Poll evaluation job progress."""
    job = await session.get(EvaluationJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobProgress.model_validate(job)


@router.post("/{job_id}/cancel")
async def cancel_eval_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Cancel a queued or running evaluation job."""
    job = await session.get(EvaluationJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in ("queued", "running"):
        raise HTTPException(400, f"Cannot cancel job with status '{job.status}'")
    get_queue().cancel(f"eval:{job_id}")
    return {"ok": True}
