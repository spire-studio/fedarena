"""Leaderboard route — ranks completed submissions."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ...db import get_session
from ...models import EvaluationJob, Submission
from ...schemas import LeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    role: str = Query(..., pattern="^(attack|defense)$"),
    session: AsyncSession = Depends(get_session),
):
    """Get ranked leaderboard for attacks or defenses.

    Attacks ranked by lowest avg accuracy (stronger attack = lower accuracy).
    Defenses ranked by highest avg accuracy (stronger defense = higher accuracy).
    """
    stmt = (
        select(Submission, EvaluationJob)
        .join(EvaluationJob, EvaluationJob.submission_id == Submission.id)
        .where(Submission.role == role, Submission.status == "completed")
        .order_by(EvaluationJob.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    # Deduplicate: keep latest job per submission
    seen: dict[int, tuple] = {}
    for sub, job in rows:
        if sub.id not in seen and job.results_json:
            seen[sub.id] = (sub, job)

    # Parse results and compute avg accuracy
    entries: list[dict] = []
    for sub, job in seen.values():
        results = json.loads(job.results_json)
        accs = [v["avg_final_accuracy"] for v in results.values() if v.get("avg_final_accuracy") is not None]
        if not accs:
            continue
        avg = sum(accs) / len(accs)
        entries.append(
            {
                "submission_id": sub.id,
                "method_name": sub.method_name,
                "display_name": sub.display_name,
                "author": sub.author,
                "role": sub.role,
                "avg_accuracy": avg,
                "opponent_scores": {k: v.get("avg_final_accuracy") for k, v in results.items()},
                "submitted_at": sub.created_at,
            }
        )

    # Sort: attacks ascending (lower = stronger), defenses descending
    reverse = role == "defense"
    entries.sort(key=lambda e: e["avg_accuracy"], reverse=reverse)

    # Assign ranks
    return [LeaderboardEntry(rank=i + 1, **entry) for i, entry in enumerate(entries)]
