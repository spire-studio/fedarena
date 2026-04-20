"""Bench routes — natural language experiment execution."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ...config import settings
from ...db import get_session
from ...models import BenchJob
from ...services.agent.bench_planner import plan_experiments
from ...services.bench_worker import run_bench

router = APIRouter(prefix="/bench", tags=["bench"])


class BenchRequest(BaseModel):
    prompt: str


class BenchExperiment(BaseModel):
    name: str
    attack_method: str | None = None
    defense_method: str | None = None


class BenchJobResponse(BaseModel):
    id: int
    prompt: str
    plan_summary: str | None
    status: str
    experiments: list[BenchExperiment]
    results: list[dict] | None = None
    total_experiments: int
    completed_experiments: int
    current_experiment: str | None
    error: str | None
    started_at: str | None
    completed_at: str | None


def _build_response(job: BenchJob) -> BenchJobResponse:
    experiments = []
    if job.experiments_json:
        experiments = [BenchExperiment(**e) for e in json.loads(job.experiments_json)]
    results = None
    if job.results_json:
        results = json.loads(job.results_json)
    return BenchJobResponse(
        id=job.id,
        prompt=job.prompt,
        plan_summary=job.plan_summary,
        status=job.status,
        experiments=experiments,
        results=results,
        total_experiments=job.total_experiments,
        completed_experiments=job.completed_experiments,
        current_experiment=job.current_experiment,
        error=job.error,
        started_at=str(job.started_at) if job.started_at else None,
        completed_at=str(job.completed_at) if job.completed_at else None,
    )


@router.post("", response_model=BenchJobResponse, status_code=201)
async def create_bench_job(
    body: BenchRequest,
    session: AsyncSession = Depends(get_session),
):
    """Parse a natural language prompt into experiments and start execution."""
    if not settings.openai_api_key:
        raise HTTPException(503, "LLM API key not configured. Set OPENAI_API_KEY in .env")

    # 1. LLM plans experiments
    try:
        plan = await plan_experiments(body.prompt)
    except ValueError as e:
        raise HTTPException(422, f"Planning failed: {e}")
    except Exception as e:
        raise HTTPException(502, f"LLM API error: {e}")

    experiments = plan["experiments"]

    # 2. Create DB record
    job = BenchJob(
        prompt=body.prompt,
        plan_summary=plan.get("plan_summary"),
        status="queued",
        experiments_json=json.dumps(experiments, ensure_ascii=False),
        total_experiments=len(experiments),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # 3. Launch background execution
    run_bench(job.id, experiments)

    return _build_response(job)


@router.get("/{job_id}", response_model=BenchJobResponse)
async def get_bench_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get bench job status and results."""
    job = await session.get(BenchJob, job_id)
    if not job:
        raise HTTPException(404, "Bench job not found")
    return _build_response(job)


@router.get("", response_model=list[BenchJobResponse])
async def list_bench_jobs(
    session: AsyncSession = Depends(get_session),
):
    """List recent bench jobs."""
    stmt = select(BenchJob).order_by(BenchJob.id.desc()).limit(20)
    jobs = (await session.execute(stmt)).scalars().all()
    return [_build_response(j) for j in jobs]
