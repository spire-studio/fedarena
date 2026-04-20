"""Tests for the submissions CRUD API."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

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
