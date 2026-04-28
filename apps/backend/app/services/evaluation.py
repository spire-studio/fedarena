"""Background evaluation worker.

Runs arena evaluation via the centralized task queue so only one
GPU-bound job executes at a time.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, create_engine

from ..models import EvaluationJob, Submission

logger = logging.getLogger("fedarena.evaluation")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DB_PATH = PROJECT_ROOT / "db" / "fedarena.db"

_sync_engine = None
_sync_engine_lock = threading.Lock()


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        with _sync_engine_lock:
            if _sync_engine is None:
                _sync_engine = create_engine(f"sqlite:///{DB_PATH}")
    return _sync_engine


def _update_job(job_id: int, **fields) -> None:
    engine = _get_sync_engine()
    with Session(engine) as session:
        job = session.get(EvaluationJob, job_id)
        if job:
            for k, v in fields.items():
                setattr(job, k, v)
            session.add(job)
            session.commit()


def _update_submission(submission_id: int, **fields) -> None:
    engine = _get_sync_engine()
    with Session(engine) as session:
        sub = session.get(Submission, submission_id)
        if sub:
            for k, v in fields.items():
                setattr(sub, k, v)
            session.add(sub)
            session.commit()


def run_evaluation(job_id: int, submission_id: int, method_name: str, role: str) -> None:
    """Submit evaluation to the GPU task queue."""
    from .task_queue import get_queue

    key = f"eval:{job_id}"

    def on_cancel() -> None:
        now = datetime.now(UTC)
        _update_job(job_id, status="cancelled", completed_at=now)
        _update_submission(submission_id, status="failed", updated_at=now)

    get_queue().submit(
        key,
        "evaluation",
        _evaluation_worker,
        job_id,
        submission_id,
        method_name,
        role,
        on_cancel=on_cancel,
    )


def _evaluation_worker(
    job_id: int,
    submission_id: int,
    method_name: str,
    role: str,
    cancel_event: threading.Event,
) -> None:
    def now() -> datetime:
        return datetime.now(UTC)

    if cancel_event.is_set():
        _update_job(job_id, status="cancelled", completed_at=now())
        _update_submission(submission_id, status="failed", updated_at=now())
        return

    libs_path = str(PROJECT_ROOT / "libs")
    runners_path = str(PROJECT_ROOT / "apps" / "backend" / "runners")
    for p in (libs_path, runners_path):
        if p not in sys.path:
            sys.path.insert(0, p)

    _update_job(job_id, status="running", started_at=now())
    _update_submission(submission_id, status="evaluating", updated_at=now())

    try:
        import fl_core.research.registry as reg

        reg._discovered = False
        reg._ensure_discovered()

        if role == "attack":
            reg.get_attack(method_name)
        else:
            reg.get_defense(method_name)

        matrix_path = PROJECT_ROOT / "results" / "arena" / "benchmark_matrix.json"
        if not matrix_path.exists():
            raise FileNotFoundError("Benchmark matrix not found. Run 'arena generate' first.")

        matrix_data = json.loads(matrix_path.read_text(encoding="utf-8"))

        if role == "attack":
            opponents = matrix_data["defenses"]
        else:
            opponents = matrix_data["attacks"]

        total = len(opponents)
        _update_job(job_id, total_opponents=total)

        config_path = PROJECT_ROOT / "configs" / "research" / "bench_baseline.yaml"
        config = _load_config(config_path)
        output_dir = PROJECT_ROOT / "results" / "arena"
        seeds = matrix_data.get("seeds", [0])

        results: dict[str, Any] = {}
        NO_ATTACK = "__none__"
        NO_DEFENSE = "__none__"

        for i, opp in enumerate(opponents):
            if cancel_event.is_set():
                _update_job(job_id, status="cancelled", completed_at=now())
                _update_submission(submission_id, status="failed", updated_at=now())
                logger.info("Evaluation cancelled: %s", method_name)
                return

            _update_job(
                job_id,
                completed_opponents=i,
                current_opponent=opp,
                progress=f"{i}/{total} opponents done",
            )

            if role == "attack":
                atk = method_name
                dfn = opp if opp != NO_DEFENSE else None
            else:
                atk = opp if opp != NO_ATTACK else None
                dfn = method_name

            seed_results = []
            for seed in seeds:
                try:
                    from fl_core.research.runner import _run_single_seed

                    metrics = _run_single_seed(
                        config=config,
                        experiment_name=f"{atk or NO_ATTACK}_vs_{dfn or NO_DEFENSE}",
                        seed=seed,
                        results_dir=output_dir / "runs",
                        attack_method=atk,
                        defense_method=dfn,
                    )
                    acc = metrics.get("final_accuracy")
                    global_res = metrics.get("global_results", {})
                    seed_results.append(
                        {
                            "seed": seed,
                            "final_accuracy": acc,
                            "rounds": global_res.get("rounds", []),
                            "accuracy_trajectory": global_res.get("global_accuracy", []),
                            "loss_trajectory": global_res.get("global_loss", []),
                        }
                    )
                except Exception as e:
                    logger.error("Seed %d failed: %s", seed, e)
                    seed_results.append({"seed": seed, "final_accuracy": None, "error": str(e)})

            valid = [r["final_accuracy"] for r in seed_results if r["final_accuracy"] is not None]
            results[opp] = {
                "avg_final_accuracy": sum(valid) / len(valid) if valid else None,
                "per_seed": seed_results,
            }

            _update_job(
                job_id,
                completed_opponents=i + 1,
                progress=f"{i + 1}/{total} opponents done",
                results_json=json.dumps(results, ensure_ascii=False),
            )

        _update_job(
            job_id,
            status="completed",
            completed_opponents=total,
            current_opponent=None,
            progress=f"{total}/{total} opponents done",
            results_json=json.dumps(results, ensure_ascii=False),
            completed_at=now(),
        )
        _update_submission(submission_id, status="completed", updated_at=now())

        eval_path = output_dir / f"eval_{method_name}.json"
        eval_path.parent.mkdir(parents=True, exist_ok=True)
        eval_path.write_text(
            json.dumps({"method": method_name, "role": role, "results": results}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("Evaluation completed: %s", method_name)

    except Exception as e:
        logger.exception("Evaluation failed for %s", method_name)
        _update_job(job_id, status="failed", error=str(e), completed_at=now())
        _update_submission(submission_id, status="failed", updated_at=now())


def _load_config(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
