"""Tests for the leaderboard API."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from apps.backend.app.models import EvaluationJob, Submission

from .conftest import test_session


async def _seed_completed_submission(
    role: str,
    method_name: str,
    display_name: str,
    results: dict,
) -> int:
    """Insert a completed submission + job with results directly into DB."""
    async with test_session() as session:
        sub = Submission(
            method_name=method_name,
            role=role,
            display_name=display_name,
            author="tester",
            code="# placeholder",
            status="completed",
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)

        job = EvaluationJob(
            submission_id=sub.id,
            status="completed",
            results_json=json.dumps(results),
            total_opponents=len(results),
            completed_opponents=len(results),
        )
        session.add(job)
        await session.commit()
        return sub.id


@pytest.mark.asyncio
class TestLeaderboard:
    async def test_empty_leaderboard(self, client: AsyncClient):
        resp = await client.get("/api/v1/leaderboard?role=defense")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_requires_role(self, client: AsyncClient):
        resp = await client.get("/api/v1/leaderboard")
        assert resp.status_code == 422

    async def test_invalid_role(self, client: AsyncClient):
        resp = await client.get("/api/v1/leaderboard?role=bad")
        assert resp.status_code == 422

    async def test_defense_leaderboard_ranked(self, client: AsyncClient):
        await _seed_completed_submission(
            "defense",
            "arena_defense_a",
            "Defense A",
            {"alie": {"avg_final_accuracy": 0.8}, "ipm": {"avg_final_accuracy": 0.7}},
        )
        await _seed_completed_submission(
            "defense",
            "arena_defense_b",
            "Defense B",
            {"alie": {"avg_final_accuracy": 0.9}, "ipm": {"avg_final_accuracy": 0.85}},
        )

        resp = await client.get("/api/v1/leaderboard?role=defense")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["rank"] == 1
        assert data[0]["display_name"] == "Defense B"
        assert data[1]["rank"] == 2
        assert data[1]["display_name"] == "Defense A"

    async def test_attack_leaderboard_ranked(self, client: AsyncClient):
        await _seed_completed_submission(
            "attack",
            "arena_attack_a",
            "Attack A",
            {"krum": {"avg_final_accuracy": 0.3}},
        )
        await _seed_completed_submission(
            "attack",
            "arena_attack_b",
            "Attack B",
            {"krum": {"avg_final_accuracy": 0.5}},
        )

        resp = await client.get("/api/v1/leaderboard?role=attack")
        data = resp.json()
        assert data[0]["display_name"] == "Attack A"
        assert data[1]["display_name"] == "Attack B"

    async def test_excludes_non_completed(self, client: AsyncClient):
        async with test_session() as session:
            sub = Submission(
                method_name="arena_defense_pending",
                role="defense",
                display_name="Pending",
                code="# placeholder",
                status="evaluating",
            )
            session.add(sub)
            await session.commit()

        resp = await client.get("/api/v1/leaderboard?role=defense")
        assert resp.json() == []
