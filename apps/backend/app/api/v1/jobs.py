"""Job progress polling and control routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...models import EvaluationJob
from ...schemas import JobProgress
from ...services.task_queue import get_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


class QueueStatusResponse(BaseModel):
    total: int
    running: int
    pending: int
    tasks: list[dict]


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
