"""Benchmark matrix route — serves the pre-computed baseline matrix."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from ...schemas import MatrixResponse

router = APIRouter(prefix="/matrix", tags=["matrix"])


@router.get("", response_model=MatrixResponse)
async def get_matrix(scenario: str = Query("cifar10_noniid")):
    """Return the benchmark matrix for a given scenario."""
    from fl_core.research.scenarios import get_matrix_path_with_fallback

    matrix_path = get_matrix_path_with_fallback(scenario)
    if matrix_path is None:
        raise HTTPException(
            404,
            f"Benchmark matrix not found for scenario '{scenario}'. Run 'arena generate --scenario {scenario}' first.",
        )
    data = json.loads(matrix_path.read_text(encoding="utf-8"))
    return MatrixResponse(
        attacks=data.get("attacks", []),
        defenses=data.get("defenses", []),
        matrix=data.get("matrix", {}),
        config=data.get("config"),
        seeds=data.get("seeds"),
        scenario_id=scenario,
    )
