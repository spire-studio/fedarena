"""Tests for the submissions CRUD API."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from apps.backend.app.services.report import generate_markdown_report

from .conftest import VALID_ATTACK_CODE, VALID_DEFENSE_CODE


@pytest.mark.asyncio
class TestCreateSubmission:
    async def test_create_attack(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            resp = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "Test Attack",
                    "author": "tester",
                    "description": "A test attack",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["method_name"] == "arena_attack_test_atk"
        assert data["role"] == "attack"
        assert data["display_name"] == "Test Attack"
        assert data["status"] == "evaluating"
        assert data["job_id"] is not None

    async def test_create_defense(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            resp = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_DEFENSE_CODE,
                    "role": "defense",
                    "display_name": "Test Defense",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["method_name"] == "arena_defense_test_def"
        assert data["role"] == "defense"

    async def test_invalid_role(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "code": VALID_ATTACK_CODE,
                "role": "invalid",
                "display_name": "Bad",
            },
        )
        assert resp.status_code == 400

    async def test_syntax_error(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "code": "def broken(:",
                "role": "attack",
                "display_name": "Bad",
            },
        )
        assert resp.status_code == 422

    async def test_missing_base_class(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "code": "class Foo:\n    pass\n",
                "role": "attack",
                "display_name": "Bad",
            },
        )
        assert resp.status_code == 422

    async def test_missing_method_name(self, client: AsyncClient):
        code = """\
from fl_core.research.base_attack import ResearchAttackStrategy

class NoName(ResearchAttackStrategy):
    def attack(self, local_model_params, global_model_params, round_num=0, client_id=0):
        return local_model_params
"""
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "code": code,
                "role": "attack",
                "display_name": "Bad",
            },
        )
        assert resp.status_code == 422

    async def test_wrong_prefix(self, client: AsyncClient):
        code = """\
from fl_core.research.base_attack import ResearchAttackStrategy

class WrongPrefix(ResearchAttackStrategy):
    method_name = "bad_prefix_test"
    def attack(self, local_model_params, global_model_params, round_num=0, client_id=0):
        return local_model_params
"""
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "code": code,
                "role": "attack",
                "display_name": "Bad",
            },
        )
        assert resp.status_code == 422

    async def test_missing_required_method(self, client: AsyncClient):
        code = """\
from fl_core.research.base_attack import ResearchAttackStrategy

class NoAttackMethod(ResearchAttackStrategy):
    method_name = "arena_attack_no_method"
    def setup(self, config=None):
        pass
"""
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "code": code,
                "role": "attack",
                "display_name": "Bad",
            },
        )
        assert resp.status_code == 422

    async def test_duplicate_method_name(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            resp1 = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "First",
                },
            )
            assert resp1.status_code == 201

            resp2 = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "Duplicate",
                },
            )
        assert resp2.status_code == 409


@pytest.mark.asyncio
class TestListSubmissions:
    async def _create(self, client: AsyncClient, code: str, role: str, name: str):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            return await client.post(
                "/api/v1/submissions",
                json={
                    "code": code,
                    "role": role,
                    "display_name": name,
                },
            )

    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/v1/submissions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_all(self, client: AsyncClient):
        await self._create(client, VALID_ATTACK_CODE, "attack", "Atk")
        await self._create(client, VALID_DEFENSE_CODE, "defense", "Def")
        resp = await client.get("/api/v1/submissions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_filter_by_role(self, client: AsyncClient):
        await self._create(client, VALID_ATTACK_CODE, "attack", "Atk")
        await self._create(client, VALID_DEFENSE_CODE, "defense", "Def")

        resp = await client.get("/api/v1/submissions?role=attack")
        assert len(resp.json()) == 1
        assert resp.json()[0]["role"] == "attack"

        resp = await client.get("/api/v1/submissions?role=defense")
        assert len(resp.json()) == 1
        assert resp.json()[0]["role"] == "defense"


@pytest.mark.asyncio
class TestGetSubmission:
    async def test_get_existing(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            create_resp = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "Get Test",
                },
            )
        sid = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/submissions/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sid
        assert data["code"] == VALID_ATTACK_CODE
        assert data["display_name"] == "Get Test"

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/submissions/999")
        assert resp.status_code == 404

    async def test_get_includes_error(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            create_resp = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "Error Test",
                },
            )
        data = create_resp.json()
        sid = data["id"]
        job_id = data["job_id"]

        from apps.backend.app.models import EvaluationJob

        from .conftest import test_session

        async with test_session() as session:
            job = await session.get(EvaluationJob, job_id)
            job.status = "failed"
            job.error = "CUDA out of memory"
            session.add(job)
            await session.commit()

        resp = await client.get(f"/api/v1/submissions/{sid}")
        assert resp.status_code == 200
        assert resp.json()["error"] == "CUDA out of memory"

    async def test_get_no_error_when_success(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            resp = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "OK Test",
                },
            )
        sid = resp.json()["id"]
        detail = await client.get(f"/api/v1/submissions/{sid}")
        assert detail.json()["error"] is None


@pytest.mark.asyncio
class TestDeleteSubmission:
    async def test_delete_existing(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            create_resp = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "Del Test",
                },
            )
        sid = create_resp.json()["id"]

        with patch("apps.backend.app.api.v1.submissions.remove_submission_files"):
            resp = await client.delete(f"/api/v1/submissions/{sid}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/v1/submissions/{sid}")
        assert resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient):
        resp = await client.delete("/api/v1/submissions/999")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestSubmissionReport:
    async def _create_with_results(self, client: AsyncClient) -> int:
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            resp = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "Report Test",
                    "author": "tester",
                    "description": "An attack for testing reports",
                },
            )
        data = resp.json()
        sid = data["id"]
        job_id = data["job_id"]

        from apps.backend.app.models import EvaluationJob

        from .conftest import test_session

        results = {
            "baseline_fedavg": {
                "avg_final_accuracy": 0.85,
                "per_seed": [
                    {
                        "seed": 0,
                        "final_accuracy": 0.85,
                        "rounds": [1, 2, 3],
                        "accuracy_trajectory": [0.3, 0.6, 0.85],
                        "loss_trajectory": [2.1, 1.2, 0.5],
                    }
                ],
            },
            "__none__": {
                "avg_final_accuracy": 0.92,
                "per_seed": [{"seed": 0, "final_accuracy": 0.92}],
            },
        }
        async with test_session() as session:
            job = await session.get(EvaluationJob, job_id)
            job.status = "completed"
            job.results_json = json.dumps(results)
            session.add(job)
            await session.commit()

        return sid

    async def test_report_download(self, client: AsyncClient):
        sid = await self._create_with_results(client)
        resp = await client.get(f"/api/v1/submissions/{sid}/report")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        body = resp.text
        assert "# Evaluation Report: Report Test" in body
        assert "arena_attack_test_atk" in body
        assert "0.8500" in body
        assert "fedavg" in body

    async def test_report_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/submissions/999/report")
        assert resp.status_code == 404

    async def test_report_no_results(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.submissions.write_submission_files"),
            patch("apps.backend.app.api.v1.submissions.run_evaluation"),
        ):
            resp = await client.post(
                "/api/v1/submissions",
                json={
                    "code": VALID_ATTACK_CODE,
                    "role": "attack",
                    "display_name": "No Results",
                },
            )
        sid = resp.json()["id"]
        resp = await client.get(f"/api/v1/submissions/{sid}/report")
        assert resp.status_code == 200
        body = resp.text
        assert "# Evaluation Report: No Results" in body
        assert "## Summary" not in body


class TestReportGeneration:
    def test_basic_report(self):
        sub = {
            "display_name": "My Attack",
            "method_name": "arena_attack_my",
            "role": "attack",
            "author": "alice",
            "status": "completed",
            "created_at": "2026-01-15T10:00:00",
            "description": "A smart attack",
            "code": "class Foo:\n    pass\n",
        }
        results = {
            "fedavg": {
                "avg_final_accuracy": 0.75,
                "per_seed": [{"seed": 0, "final_accuracy": 0.75}],
            },
        }
        md = generate_markdown_report(sub, results)
        assert "# Evaluation Report: My Attack" in md
        assert "alice" in md
        assert "0.7500" in md
        assert "lower = stronger attack" in md
        assert "```python" in md

    def test_report_without_results(self):
        sub = {
            "display_name": "Pending",
            "method_name": "arena_defense_pending",
            "role": "defense",
            "author": None,
            "status": "pending",
            "created_at": "2026-01-15T10:00:00",
            "description": None,
            "code": "class Foo:\n    pass\n",
        }
        md = generate_markdown_report(sub, None)
        assert "# Evaluation Report: Pending" in md
        assert "## Summary" not in md
        assert "## Code" in md

    def test_multi_seed_report(self):
        sub = {
            "display_name": "Multi",
            "method_name": "arena_attack_multi",
            "role": "attack",
            "author": None,
            "status": "completed",
            "created_at": "2026-01-15T10:00:00",
            "description": None,
            "code": "pass",
        }
        results = {
            "opp": {
                "avg_final_accuracy": 0.80,
                "per_seed": [
                    {"seed": 0, "final_accuracy": 0.78},
                    {"seed": 1, "final_accuracy": 0.82},
                ],
            },
        }
        md = generate_markdown_report(sub, results)
        assert "Per Seed" in md
        assert "0.7800" in md
        assert "0.8200" in md

    def test_trajectory_table(self):
        sub = {
            "display_name": "Traj",
            "method_name": "arena_attack_traj",
            "role": "attack",
            "author": None,
            "status": "completed",
            "created_at": "2026-01-15T10:00:00",
            "description": None,
            "code": "pass",
        }
        results = {
            "opp": {
                "avg_final_accuracy": 0.9,
                "per_seed": [
                    {
                        "seed": 0,
                        "final_accuracy": 0.9,
                        "rounds": [1, 2],
                        "accuracy_trajectory": [0.5, 0.9],
                        "loss_trajectory": [1.5, 0.3],
                    }
                ],
            },
        }
        md = generate_markdown_report(sub, results)
        assert "## Training Trajectories" in md
        assert "vs opp" in md
        assert "0.5000" in md
