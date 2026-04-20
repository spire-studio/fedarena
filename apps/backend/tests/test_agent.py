"""Tests for the agent API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAgentConfig:
    async def test_get_config_no_key(self, client: AsyncClient):
        with patch("apps.backend.app.api.v1.agent.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            mock_settings.default_llm_model = "gpt-4o"
            mock_settings.openai_api_base = "https://api.openai.com/v1"
            resp = await client.get("/api/v1/agent/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_api_key"] is False
        assert data["model"] == "gpt-4o"

    async def test_get_config_with_key(self, client: AsyncClient):
        with patch("apps.backend.app.api.v1.agent.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.default_llm_model = "gpt-4o"
            mock_settings.openai_api_base = "https://api.openai.com/v1"
            resp = await client.get("/api/v1/agent/config")
        assert resp.status_code == 200
        assert resp.json()["has_api_key"] is True


@pytest.mark.asyncio
class TestGenerate:
    async def test_generate_no_api_key(self, client: AsyncClient):
        with patch("apps.backend.app.api.v1.agent.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            resp = await client.post("/api/v1/agent/generate", json={"prompt": "test"})
        assert resp.status_code == 503

    async def test_generate_success(self, client: AsyncClient):
        mock_result = {
            "code": "class Foo: pass",
            "role": "attack",
            "method_name": "arena_attack_foo",
            "class_name": "Foo",
            "display_name": "Foo Attack",
            "description": "A foo attack",
        }
        with (
            patch("apps.backend.app.api.v1.agent.settings") as mock_settings,
            patch(
                "apps.backend.app.api.v1.agent.generate_submission", new_callable=AsyncMock, return_value=mock_result
            ),
        ):
            mock_settings.openai_api_key = "sk-test"
            resp = await client.post("/api/v1/agent/generate", json={"prompt": "make an attack"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "class Foo: pass"
        assert data["role"] == "attack"
        assert data["display_name"] == "Foo Attack"

    async def test_generate_llm_value_error(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.agent.settings") as mock_settings,
            patch(
                "apps.backend.app.api.v1.agent.generate_submission",
                new_callable=AsyncMock,
                side_effect=ValueError("parse failed"),
            ),
        ):
            mock_settings.openai_api_key = "sk-test"
            resp = await client.post("/api/v1/agent/generate", json={"prompt": "bad"})
        assert resp.status_code == 422

    async def test_generate_llm_api_error(self, client: AsyncClient):
        with (
            patch("apps.backend.app.api.v1.agent.settings") as mock_settings,
            patch(
                "apps.backend.app.api.v1.agent.generate_submission",
                new_callable=AsyncMock,
                side_effect=RuntimeError("timeout"),
            ),
        ):
            mock_settings.openai_api_key = "sk-test"
            resp = await client.post("/api/v1/agent/generate", json={"prompt": "bad"})
        assert resp.status_code == 502
