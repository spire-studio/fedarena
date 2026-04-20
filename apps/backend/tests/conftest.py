"""Shared fixtures for backend API tests.

Uses an in-memory SQLite database so tests are isolated and fast.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from apps.backend.app.db import get_session
from apps.backend.app.main import app

TEST_DB_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DB_URL, echo=False)
test_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_session() -> AsyncGenerator[AsyncSession]:
    async with test_session() as session:
        yield session


app.dependency_overrides[get_session] = _override_get_session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


VALID_ATTACK_CODE = """\
from typing import Any, Dict, List, Optional
import torch
from fl_core.research.base_attack import ResearchAttackStrategy


class TestAttack(ResearchAttackStrategy):
    method_name = "arena_attack_test_atk"

    def setup(self, config=None):
        pass

    def attack(self, local_model_params, global_model_params, round_num=0, client_id=0):
        return local_model_params
"""

VALID_DEFENSE_CODE = """\
from typing import Any, Dict, List, Optional
import torch
from fl_core.research.base_defense import ResearchDefenseStrategy


class TestDefense(ResearchDefenseStrategy):
    method_name = "arena_defense_test_def"

    def setup(self, config=None):
        pass

    def aggregate(self, client_models, client_weights=None, **kwargs):
        if not client_models:
            raise ValueError("empty")
        out = {}
        for k in client_models[0]:
            out[k] = torch.stack([m[k] for m in client_models]).mean(dim=0)
        return out
"""
