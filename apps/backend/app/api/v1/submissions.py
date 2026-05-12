"""Submission CRUD routes."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ...config import settings
from ...db import get_session
from ...models import EvaluationJob, Submission
from ...schemas import AnalysisResponse, SubmissionCreate, SubmissionDetail, SubmissionResponse, VersionInfo
from ...services.evaluation import run_evaluation
from ...services.report import generate_markdown_report
from ...services.submission import (
    compute_versioned_name,
    remove_submission_files,
    rewrite_method_name_in_code,
    validate_code,
    write_submission_files,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]

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

    canonical_name: str = result["method_name"]
    class_name: str = result["class_name"]

    # Check for existing submissions with the same method_group
    existing = (
        (
            await session.execute(
                select(Submission)
                .where(Submission.method_group == canonical_name)
                .order_by(Submission.version.desc())
            )
        )
        .scalars()
        .all()
    )

    if existing and not body.update_existing:
        latest = existing[0]
        raise HTTPException(
            409,
            f"Method '{canonical_name}' already exists (v{latest.version or 1}, id={latest.id}). "
            "Set update_existing=true to submit as a new version.",
        )

    if existing:
        next_version = (existing[0].version or 1) + 1
        method_name = compute_versioned_name(canonical_name, next_version)
        code = rewrite_method_name_in_code(body.code, canonical_name, method_name)
    else:
        next_version = 1
        method_name = canonical_name
        code = body.code

    # Write files to submissions/
    write_submission_files(method_name, class_name, body.role, code)

    # Create DB records
    submission = Submission(
        method_name=method_name,
        role=body.role,
        display_name=body.display_name,
        author=body.author,
        description=body.description,
        code=code,
        status="evaluating",
        method_group=canonical_name,
        version=next_version,
    )
    session.add(submission)
    await session.commit()
    await session.refresh(submission)

    job = EvaluationJob(submission_id=submission.id, status="queued")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Launch background evaluation
    run_evaluation(job.id, submission.id, method_name, body.role, num_seeds=body.num_seeds)

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
        error=job.error if job else None,
    )


@router.get("/{submission_id}/report")
async def get_submission_report(
    submission_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Download a Markdown evaluation report for a submission."""
    submission = await session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")

    import json

    stmt = (
        select(EvaluationJob)
        .where(EvaluationJob.submission_id == submission_id)
        .order_by(EvaluationJob.created_at.desc())
    )
    job = (await session.execute(stmt)).scalars().first()
    results = json.loads(job.results_json) if job and job.results_json else None

    markdown = generate_markdown_report(submission.model_dump(), results)
    filename = f"report_{submission.method_name}.md"

    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{submission_id}/analysis", response_model=AnalysisResponse)
async def get_submission_analysis(
    submission_id: int,
    regenerate: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Get or generate LLM analysis for a completed submission."""
    if not settings.openai_api_key:
        raise HTTPException(503, "LLM API key not configured")

    submission = await session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")
    if submission.status != "completed":
        raise HTTPException(400, "Submission evaluation not completed yet")

    stmt = (
        select(EvaluationJob)
        .where(EvaluationJob.submission_id == submission_id)
        .order_by(EvaluationJob.created_at.desc())
    )
    job = (await session.execute(stmt)).scalars().first()
    if not job or not job.results_json:
        raise HTTPException(400, "No evaluation results available")

    if job.analysis_text and not regenerate:
        return AnalysisResponse(analysis=job.analysis_text, cached=True)

    from fl_core.research.scenarios import get_matrix_path_with_fallback

    matrix_path = get_matrix_path_with_fallback("cifar10_noniid")
    if matrix_path is None:
        raise HTTPException(404, "Benchmark matrix not found")
    matrix_data = json.loads(matrix_path.read_text(encoding="utf-8"))

    results = json.loads(job.results_json)

    from ...services.analysis import generate_analysis

    analysis_text = await generate_analysis(
        submission=submission.model_dump(),
        results=results,
        matrix_data=matrix_data,
    )

    job.analysis_text = analysis_text
    session.add(job)
    await session.commit()

    return AnalysisResponse(analysis=analysis_text, cached=False)


@router.get("/{submission_id}/versions", response_model=list[VersionInfo])
async def get_submission_versions(
    submission_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get all versions of the same method group."""
    submission = await session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")
    if not submission.method_group:
        return []

    siblings = (
        await session.execute(
            select(Submission)
            .where(Submission.method_group == submission.method_group)
            .order_by(Submission.version.desc())
        )
    ).scalars().all()

    result = []
    for sub in siblings:
        avg_acc = None
        job = (
            await session.execute(
                select(EvaluationJob)
                .where(EvaluationJob.submission_id == sub.id)
                .order_by(EvaluationJob.created_at.desc())
            )
        ).scalars().first()
        if job and job.results_json:
            data = json.loads(job.results_json)
            if "scenarios" in data:
                data = data["scenarios"].get("cifar10_noniid", data)
            accs = [v["avg_final_accuracy"] for v in data.values() if isinstance(v, dict) and v.get("avg_final_accuracy") is not None]
            if accs:
                avg_acc = sum(accs) / len(accs)
        result.append(VersionInfo(
            id=sub.id,
            version=sub.version or 1,
            method_name=sub.method_name,
            display_name=sub.display_name,
            status=sub.status,
            avg_accuracy=avg_acc,
            created_at=sub.created_at,
        ))
    return result


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
