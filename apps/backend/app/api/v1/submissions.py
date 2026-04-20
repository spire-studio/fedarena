"""Submission CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ...db import get_session
from ...models import EvaluationJob, Submission
from ...schemas import SubmissionCreate, SubmissionDetail, SubmissionResponse
from ...services.evaluation import run_evaluation
from ...services.submission import (
    remove_submission_files,
    validate_code,
    write_submission_files,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionDetail, status_code=201)
async def create_submission(
    body: SubmissionCreate,
    session: AsyncSession = Depends(get_session),
):
    """Submit a new attack or defense for evaluation."""
    if body.role not in ("attack", "defense"):
        raise HTTPException(400, "role must be 'attack' or 'defense'")

    # Validate code
    result = validate_code(body.code, body.role)
    if not result["ok"]:
        raise HTTPException(422, result["error"])

    method_name: str = result["method_name"]
    class_name: str = result["class_name"]

    # Check for duplicate method_name
    existing = (
        (await session.execute(select(Submission).where(Submission.method_name == method_name))).scalars().first()
    )
    if existing:
        raise HTTPException(409, f"Method '{method_name}' already exists (id={existing.id})")

    # Write files to submissions/
    write_submission_files(method_name, class_name, body.role, body.code)

    # Create DB records
    submission = Submission(
        method_name=method_name,
        role=body.role,
        display_name=body.display_name,
        author=body.author,
        description=body.description,
        code=body.code,
        status="evaluating",
    )
    session.add(submission)
    await session.commit()
    await session.refresh(submission)

    job = EvaluationJob(submission_id=submission.id, status="queued")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Launch background evaluation
    run_evaluation(job.id, submission.id, method_name, body.role)

    return SubmissionDetail(
        **submission.model_dump(),
        job_id=job.id,
        results=None,
    )


@router.get("", response_model=list[SubmissionResponse])
async def list_submissions(
    role: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List all submissions, optionally filtered by role."""
    stmt = select(Submission).order_by(Submission.created_at.desc())
    if role:
        stmt = stmt.where(Submission.role == role)
    results = await session.execute(stmt)
    return results.scalars().all()


@router.get("/{submission_id}", response_model=SubmissionDetail)
async def get_submission(
    submission_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get submission detail including code and results."""
    submission = await session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")

    # Get latest job
    stmt = (
        select(EvaluationJob)
        .where(EvaluationJob.submission_id == submission_id)
        .order_by(EvaluationJob.created_at.desc())
    )
    job = (await session.execute(stmt)).scalars().first()

    import json

    results = None
    job_id = None
    if job:
        job_id = job.id
        if job.results_json:
            results = json.loads(job.results_json)

    return SubmissionDetail(
        **submission.model_dump(),
        job_id=job_id,
        results=results,
    )


@router.delete("/{submission_id}", status_code=204)
async def delete_submission(
    submission_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a submission and its files."""
    submission = await session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")

    # Remove files
    remove_submission_files(submission.method_name, submission.role)

    # Delete related jobs
    jobs = (
        (await session.execute(select(EvaluationJob).where(EvaluationJob.submission_id == submission_id)))
        .scalars()
        .all()
    )
    for job in jobs:
        await session.delete(job)

    await session.delete(submission)
    await session.commit()
