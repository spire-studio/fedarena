"""Dashboard aggregation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from ...db import get_session
from ...models import BenchJob, EvaluationJob, Submission
from ...services.task_queue import get_queue

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class TopMethod(BaseModel):
    submission_id: int
    display_name: str
    method_name: str
    author: str | None
    avg_accuracy: float


class RecentSubmission(BaseModel):
    id: int
    display_name: str
    method_name: str
    role: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    total_submissions: int
    completed_evaluations: int
    failed_evaluations: int
    active_jobs: int
    queue_pending: int
    top_attack: TopMethod | None
    top_defense: TopMethod | None
    recent_submissions: list[RecentSubmission]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(session: AsyncSession = Depends(get_session)):
    total_submissions = (await session.execute(select(func.count(Submission.id)))).scalar() or 0

    completed_evaluations = (
        await session.execute(select(func.count(EvaluationJob.id)).where(EvaluationJob.status == "completed"))
    ).scalar() or 0

    failed_evaluations = (
        await session.execute(select(func.count(EvaluationJob.id)).where(EvaluationJob.status == "failed"))
    ).scalar() or 0

    active_eval = (
        await session.execute(
            select(func.count(EvaluationJob.id)).where(EvaluationJob.status.in_(["running", "queued"]))
        )
    ).scalar() or 0

    active_bench = (
        await session.execute(select(func.count(BenchJob.id)).where(BenchJob.status.in_(["running", "queued"])))
    ).scalar() or 0

    queue_pending = get_queue().pending_count()

    top_attack = await _top_method(session, "attack")
    top_defense = await _top_method(session, "defense")

    recent_stmt = select(Submission).order_by(Submission.created_at.desc(), Submission.id.desc()).limit(8)
    recent_rows = (await session.execute(recent_stmt)).scalars().all()
    recent_submissions = [
        RecentSubmission(
            id=s.id,
            display_name=s.display_name,
            method_name=s.method_name,
            role=s.role,
            status=s.status,
            created_at=str(s.created_at),
        )
        for s in recent_rows
    ]

    return DashboardResponse(
        total_submissions=total_submissions,
        completed_evaluations=completed_evaluations,
        failed_evaluations=failed_evaluations,
        active_jobs=active_eval + active_bench,
        queue_pending=queue_pending,
        top_attack=top_attack,
        top_defense=top_defense,
        recent_submissions=recent_submissions,
    )


async def _top_method(session: AsyncSession, role: str) -> TopMethod | None:
    import json

    stmt = (
        select(Submission, EvaluationJob)
        .join(EvaluationJob, EvaluationJob.submission_id == Submission.id)
        .where(Submission.role == role, Submission.status == "completed", EvaluationJob.status == "completed")
        .order_by(EvaluationJob.completed_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    best: TopMethod | None = None
    best_score: float | None = None

    for sub, job in rows:
        if not job.results_json:
            continue
        results = json.loads(job.results_json)
        accs = [r["avg_final_accuracy"] for r in results.values() if r.get("avg_final_accuracy") is not None]
        if not accs:
            continue
        avg = sum(accs) / len(accs)
        is_better = (
            best_score is None or (role == "attack" and avg < best_score) or (role == "defense" and avg > best_score)
        )
        if is_better:
            best_score = avg
            best = TopMethod(
                submission_id=sub.id,
                display_name=sub.display_name,
                method_name=sub.method_name,
                author=sub.author,
                avg_accuracy=avg,
            )

    return best
