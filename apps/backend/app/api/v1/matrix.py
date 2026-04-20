"""Benchmark matrix route — serves the pre-computed baseline matrix."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...schemas import MatrixResponse

router = APIRouter(prefix="/matrix", tags=["matrix"])

MATRIX_PATH = Path(__file__).resolve().parents[5] / "results" / "arena" / "benchmark_matrix.json"


@router.get("", response_model=MatrixResponse)
async def get_matrix():
    """Return the benchmark matrix."""
    if not MATRIX_PATH.exists():
        raise HTTPException(
            404,
            "Benchmark matrix not found. Run 'arena generate' first.",
        )
    data = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    return MatrixResponse(
        attacks=data.get("attacks", []),
        defenses=data.get("defenses", []),
        matrix=data.get("matrix", {}),
        config=data.get("config"),
        seeds=data.get("seeds"),
    )
