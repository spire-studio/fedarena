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


SORT_KEYS = {"avg_accuracy", "avg_accuracy_drop", "worst_case_accuracy", "avg_convergence_speed", "avg_stability"}


def _extract_scenario_results(results_json: str, scenario: str | None) -> dict | None:
    """Extract results for a specific scenario, handling both old and new formats."""
    results = json.loads(results_json)
    if "scenarios" in results:
        target = scenario or "cifar10_noniid"
        return results["scenarios"].get(target)
    if scenario is None or scenario == "cifar10_noniid":
        return results
    return None


@router.get("", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    role: str = Query(..., pattern="^(attack|defense)$"),
    sort_by: str = Query("avg_accuracy"),
    scenario: str | None = Query(None),
    show_all_versions: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Get ranked leaderboard for attacks or defenses.

    Attacks ranked by lowest avg accuracy (stronger attack = lower accuracy).
    Defenses ranked by highest avg accuracy (stronger defense = higher accuracy).
    """
    if sort_by not in SORT_KEYS:
        sort_by = "avg_accuracy"

    stmt = (
        select(Submission, EvaluationJob)
        .join(EvaluationJob, EvaluationJob.submission_id == Submission.id)
        .where(Submission.role == role, Submission.status == "completed")
        .order_by(EvaluationJob.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    seen: dict[int, tuple] = {}
    for sub, job in rows:
        if sub.id not in seen and job.results_json:
            seen[sub.id] = (sub, job)

    entries: list[dict] = []
    group_versions: dict[str, list[int]] = {}
    for sub, job in seen.values():
        group = sub.method_group or sub.method_name
        ver = sub.version or 1
        group_versions.setdefault(group, []).append(ver)

    # When deduplicating, keep only the highest version per group
    if not show_all_versions:
        best_per_group: dict[str, int] = {}
        for sub, job in seen.values():
            group = sub.method_group or sub.method_name
            ver = sub.version or 1
            if group not in best_per_group or ver > best_per_group[group]:
                best_per_group[group] = ver

    for sub, job in seen.values():
        group = sub.method_group or sub.method_name
        ver = sub.version or 1
        if not show_all_versions and best_per_group.get(group) != ver:
            continue
        results = _extract_scenario_results(job.results_json, scenario)
        if results is None:
            continue
        summary = results.get("__summary__", {})
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
                "opponent_scores": {
                    k: v.get("avg_final_accuracy") for k, v in results.items() if k != "__summary__"
                },
                "submitted_at": sub.created_at,
                "avg_accuracy_drop": summary.get("avg_accuracy_drop"),
                "worst_case_accuracy": summary.get("worst_case_accuracy"),
                "avg_convergence_speed": summary.get("avg_convergence_speed"),
                "avg_stability": summary.get("avg_stability"),
                "version": ver,
                "has_older_versions": len(group_versions.get(group, [])) > 1,
            }
        )

    if sort_by == "avg_accuracy":
        reverse = role == "defense"
    elif sort_by in ("avg_accuracy_drop",):
        reverse = role == "attack"
    elif sort_by == "avg_convergence_speed":
        reverse = False
    elif sort_by == "avg_stability":
        reverse = False
    else:
        reverse = role == "defense"

    entries.sort(key=lambda e: e.get(sort_by) or 0, reverse=reverse)

    return [LeaderboardEntry(rank=i + 1, **entry) for i, entry in enumerate(entries)]
