"""Aggregate all v1 routers."""

from fastapi import APIRouter

from .agent import router as agent_router
from .bench import router as bench_router
from .jobs import router as jobs_router
from .leaderboard import router as leaderboard_router
from .matrix import router as matrix_router
from .submissions import router as submissions_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(submissions_router)
api_router.include_router(leaderboard_router)
api_router.include_router(matrix_router)
api_router.include_router(jobs_router)
api_router.include_router(agent_router)
api_router.include_router(bench_router)
