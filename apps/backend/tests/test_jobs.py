"""Tests for the jobs progress API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from apps.backend.app.models import EvaluationJob, Submission

from .conftest import test_session


@pytest.mark.asyncio
class TestJobProgress:
    async def test_get_progress(self, client: AsyncClient):
        async with test_session() as session:
            sub = Submission(
                method_name="arena_attack_job_test",
                role="attack",
                display_name="Job Test",
                code="# test",
                status="evaluating",
            )
            session.add(sub)
            await session.commit()
            await session.refresh(sub)

            job = EvaluationJob(
                submission_id=sub.id,
                status="running",
                total_opponents=5,
                completed_opponents=2,
                current_opponent="krum",
                progress="2/5 opponents done",
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_id = job.id

        resp = await client.get(f"/api/v1/jobs/{job_id}/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["total_opponents"] == 5
        assert data["completed_opponents"] == 2
        assert data["current_opponent"] == "krum"

    async def test_job_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/jobs/999/progress")
        assert resp.status_code == 404
