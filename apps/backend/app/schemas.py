"""Pydantic request/response schemas."""

from datetime import datetime

from pydantic import BaseModel

# ── Submissions ──────────────────────────────────────────────


class SubmissionCreate(BaseModel):
    code: str
    role: str  # "attack" | "defense"
    display_name: str
    author: str | None = None
    description: str | None = None


class SubmissionResponse(BaseModel):
    id: int
    method_name: str
    role: str
    display_name: str
    author: str | None
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionDetail(SubmissionResponse):
    code: str
    job_id: int | None = None
    results: dict | None = None


# ── Jobs ─────────────────────────────────────────────────────


class JobProgress(BaseModel):
    id: int
    submission_id: int
    status: str
    progress: str | None
    total_opponents: int
    completed_opponents: int
    current_opponent: str | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


# ── Leaderboard ──────────────────────────────────────────────


class LeaderboardEntry(BaseModel):
    rank: int
    submission_id: int
    method_name: str
    display_name: str
    author: str | None
    role: str
    avg_accuracy: float
    opponent_scores: dict  # {opponent_name: accuracy}
    submitted_at: datetime


# ── Matrix ───────────────────────────────────────────────────


class MatrixResponse(BaseModel):
    attacks: list[str]
    defenses: list[str]
    matrix: dict  # {attack_key: {defense_key: {avg_final_accuracy, ...}}}
    config: str | None = None
    seeds: list[int] | None = None
