"""Tests for the dashboard aggregation endpoint."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from .conftest import VALID_ATTACK_CODE, VALID_DEFENSE_CODE, test_session


@pytest.mark.asyncio
async def test_dashboard_empty(client: AsyncClient):
    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_submissions"] == 0
    assert data["completed_evaluations"] == 0
    assert data["failed_evaluations"] == 0
    assert data["active_jobs"] == 0
    assert data["top_attack"] is None
    assert data["top_defense"] is None
    assert data["recent_submissions"] == []


@pytest.mark.asyncio
async def test_dashboard_counts_submissions(client: AsyncClient):
    await client.post(
        "/api/v1/submissions",
        json={"code": VALID_ATTACK_CODE, "role": "attack", "display_name": "Atk1"},
    )
    await client.post(
        "/api/v1/submissions",
        json={"code": VALID_DEFENSE_CODE, "role": "defense", "display_name": "Def1"},
    )
    resp = await client.get("/api/v1/dashboard")
    data = resp.json()
    assert data["total_submissions"] == 2
    assert len(data["recent_submissions"]) == 2


@pytest.mark.asyncio
async def test_dashboard_recent_order(client: AsyncClient):
    await client.post(
        "/api/v1/submissions",
        json={"code": VALID_ATTACK_CODE, "role": "attack", "display_name": "Atk"},
    )
    await client.post(
        "/api/v1/submissions",
        json={"code": VALID_DEFENSE_CODE, "role": "defense", "display_name": "Def"},
    )
    resp = await client.get("/api/v1/dashboard")
    data = resp.json()
    names = [s["display_name"] for s in data["recent_submissions"]]
    assert names == ["Def", "Atk"]


@pytest.mark.asyncio
async def test_dashboard_top_methods(client: AsyncClient):
    from apps.backend.app.models import EvaluationJob, Submission

    async with test_session() as session:
        sub = Submission(
            method_name="arena_attack_test",
            role="attack",
            display_name="Good Attack",
            code=VALID_ATTACK_CODE,
            status="completed",
        )
        session.add(sub)
        await session.flush()

        job = EvaluationJob(
            submission_id=sub.id,
            status="completed",
            results_json=json.dumps({"opp1": {"avg_final_accuracy": 0.15}}),
        )
        session.add(job)
        await session.commit()

    resp = await client.get("/api/v1/dashboard")
    data = resp.json()
    assert data["completed_evaluations"] == 1
    assert data["top_attack"] is not None
    assert data["top_attack"]["display_name"] == "Good Attack"
    assert data["top_attack"]["avg_accuracy"] == pytest.approx(0.15)
