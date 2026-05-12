"""SQLModel table definitions."""

from datetime import UTC, datetime

from sqlmodel import Column, Field, SQLModel, Text


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Submission(SQLModel, table=True):
    __tablename__ = "submissions"

    id: int | None = Field(default=None, primary_key=True)
    method_name: str = Field(index=True, unique=True)
    role: str = Field(index=True)  # "attack" | "defense"
    display_name: str
    author: str | None = None
    description: str | None = None
    code: str = Field(sa_column=Column(Text))
    status: str = Field(default="pending")  # pending | evaluating | completed | failed
    method_group: str | None = Field(default=None, index=True)
    version: int | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class EvaluationJob(SQLModel, table=True):
    __tablename__ = "evaluation_jobs"

    id: int | None = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submissions.id", index=True)
    status: str = Field(default="queued")  # queued | running | completed | failed
    progress: str | None = None  # e.g. "3/7 opponents done"
    total_opponents: int = 0
    completed_opponents: int = 0
    current_opponent: str | None = None
    total_scenarios: int = 0
    completed_scenarios: int = 0
    current_scenario: str | None = None
    results_json: str | None = None  # JSON string of full eval results
    analysis_text: str | None = Field(default=None, sa_column=Column(Text))
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class BenchJob(SQLModel, table=True):
    __tablename__ = "bench_jobs"

    id: int | None = Field(default=None, primary_key=True)
    prompt: str = Field(sa_column=Column(Text))
    plan_summary: str | None = None
    status: str = Field(default="queued")  # queued | planning | running | completed | failed
    experiments_json: str | None = None  # JSON: list of planned experiments
    results_json: str | None = None  # JSON: list of {name, attack, defense, metrics}
    total_experiments: int = 0
    completed_experiments: int = 0
    current_experiment: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    bench_created_at: datetime = Field(default_factory=_utcnow)
