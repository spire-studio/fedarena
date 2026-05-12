"""Scenarios route — lists available FL evaluation scenarios."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas import ScenarioInfo

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioInfo])
async def get_scenarios():
    from fl_core.research.scenarios import has_matrix, list_scenarios

    return [
        ScenarioInfo(
            id=s.id,
            name=s.name,
            description=s.description,
            has_matrix=has_matrix(s.id),
            is_default=s.is_default,
        )
        for s in list_scenarios()
    ]
