"""Agent routes — LLM-powered prompt-to-submission pipeline."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import PROJECT_ROOT, settings
from ...db import get_session
from ...models import EvaluationJob, Submission
from ...schemas import SubmissionDetail
from ...services.agent.codegen import generate_submission
from ...services.evaluation import run_evaluation
from ...services.submission import validate_code, write_submission_files

router = APIRouter(prefix="/agent", tags=["agent"])


class PromptRequest(BaseModel):
    prompt: str


class PromptResponse(BaseModel):
    submission: SubmissionDetail
    generated_code: str


class AgentConfigResponse(BaseModel):
    has_api_key: bool
    model: str
    api_base: str


class UpdateConfigRequest(BaseModel):
    api_key: str | None = None
    api_base: str | None = None
    model: str | None = None


@router.get("/config", response_model=AgentConfigResponse)
async def get_agent_config():
    """Check if the agent is configured (API key set)."""
    return AgentConfigResponse(
        has_api_key=bool(settings.openai_api_key),
        model=settings.default_llm_model,
        api_base=settings.openai_api_base,
    )


@router.put("/config", response_model=AgentConfigResponse)
async def update_agent_config(body: UpdateConfigRequest):
    """Update LLM API configuration (persisted to .env)."""
    if body.api_key is not None:
        settings.openai_api_key = body.api_key
    if body.api_base is not None:
        settings.openai_api_base = body.api_base
    if body.model is not None:
        settings.default_llm_model = body.model

    _persist_env(
        PROJECT_ROOT / ".env",
        {
            "OPENAI_API_KEY": settings.openai_api_key,
            "OPENAI_API_BASE": settings.openai_api_base,
            "DEFAULT_LLM_MODEL": settings.default_llm_model,
        },
    )

    return AgentConfigResponse(
        has_api_key=bool(settings.openai_api_key),
        model=settings.default_llm_model,
        api_base=settings.openai_api_base,
    )


def _persist_env(env_path: Path, updates: dict[str, str]) -> None:
    """Update specific keys in a .env file, preserving other lines."""
    lines: list[str] = []
    seen: set[str] = set()
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
            if key and key in updates:
                lines.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                lines.append(line)
    for key, val in updates.items():
        if key not in seen:
            lines.append(f"{key}={val}")
    env_path.write_text("\n".join(lines) + "\n")


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    code: str
    role: str
    method_name: str
    class_name: str
    display_name: str
    description: str


@router.post("/generate", response_model=GenerateResponse)
async def generate_code(body: GenerateRequest):
    """Generate code from a prompt without submitting. Returns code for review."""
    if not settings.openai_api_key:
        raise HTTPException(503, "LLM API key not configured. Set OPENAI_API_KEY in .env")

    try:
        generated = await generate_submission(body.prompt)
    except ValueError as e:
        raise HTTPException(422, f"Code generation failed: {e}")
    except Exception as e:
        raise HTTPException(502, f"LLM API error: {e}")

    return GenerateResponse(
        code=generated["code"],
        role=generated["role"],
        method_name=generated["method_name"],
        class_name=generated["class_name"],
        display_name=generated.get("display_name", generated["method_name"]),
        description=generated.get("description", ""),
    )


@router.post("/prompt", response_model=PromptResponse, status_code=201)
async def submit_prompt(
    body: PromptRequest,
    session: AsyncSession = Depends(get_session),
):
    """Generate code from a natural language prompt, validate, submit, and start evaluation."""
    if not settings.openai_api_key:
        raise HTTPException(
            503,
            "LLM API key not configured. Set OPENAI_API_KEY in .env",
        )

    # 1. Generate code via LLM
    try:
        generated = await generate_submission(body.prompt)
    except ValueError as e:
        raise HTTPException(422, f"Code generation failed: {e}")
    except Exception as e:
        raise HTTPException(502, f"LLM API error: {e}")

    code = generated["code"]
    role = generated["role"]
    method_name = generated["method_name"]
    class_name = generated["class_name"]
    display_name = generated.get("display_name", method_name)
    description = generated.get("description", "")

    # 2. Validate generated code
    validation = validate_code(code, role)
    if not validation["ok"]:
        raise HTTPException(
            422,
            f"Generated code failed validation: {validation['error']}\n\nGenerated code:\n{code}",
        )

    # Use the method_name from validation (canonical)
    method_name = validation["method_name"]
    class_name = validation["class_name"]

    # 3. Check for duplicates
    from sqlmodel import select

    existing = (
        (await session.execute(select(Submission).where(Submission.method_name == method_name))).scalars().first()
    )
    if existing:
        raise HTTPException(409, f"Method '{method_name}' already exists (id={existing.id})")

    # 4. Write files + create DB records
    write_submission_files(method_name, class_name, role, code)

    submission = Submission(
        method_name=method_name,
        role=role,
        display_name=display_name,
        author="agent",
        description=description,
        code=code,
        status="evaluating",
    )
    session.add(submission)
    await session.commit()
    await session.refresh(submission)

    job = EvaluationJob(submission_id=submission.id, status="queued")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # 5. Launch background evaluation
    run_evaluation(job.id, submission.id, method_name, role)

    return PromptResponse(
        submission=SubmissionDetail(
            **submission.model_dump(),
            job_id=job.id,
            results=None,
        ),
        generated_code=code,
    )
