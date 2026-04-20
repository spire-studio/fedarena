"""Job progress polling route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...models import EvaluationJob
from ...schemas import JobProgress

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
