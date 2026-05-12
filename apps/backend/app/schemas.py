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
    num_seeds: int | None = None  # None = use matrix default; 1 = quick; 3 = full
    update_existing: bool = False


class SubmissionResponse(BaseModel):
    id: int
    method_name: str
    role: str
    display_name: str
    author: str | None
    description: str | None
    status: str
    method_group: str | None = None
    version: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionDetail(SubmissionResponse):
    code: str
    job_id: int | None = None
    results: dict | None = None
    error: str | None = None


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
    avg_accuracy_drop: float | None = None
    worst_case_accuracy: float | None = None
    avg_convergence_speed: float | None = None
    avg_stability: float | None = None
    version: int | None = None
    has_older_versions: bool = False


class VersionInfo(BaseModel):
    id: int
    version: int
    method_name: str
    display_name: str
    status: str
    avg_accuracy: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Matrix ───────────────────────────────────────────────────


class AnalysisResponse(BaseModel):
    analysis: str
    cached: bool


class MatrixResponse(BaseModel):
    attacks: list[str]
    defenses: list[str]
    matrix: dict  # {attack_key: {defense_key: {avg_final_accuracy, ...}}}
    config: str | None = None
    seeds: list[int] | None = None
    scenario_id: str | None = None


# ── Scenarios ────────────────────────────────────────────────


class ScenarioInfo(BaseModel):
    id: str
    name: str
    description: str
    has_matrix: bool
    is_default: bool = False
