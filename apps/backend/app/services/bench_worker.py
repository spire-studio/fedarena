"""Background bench experiment worker.

Runs a list of planned experiments sequentially via the centralized task queue.
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

from ..models import BenchJob

logger = logging.getLogger("fedarena.bench_worker")

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


def _update_bench_job(job_id: int, **fields) -> None:
    engine = _get_sync_engine()
    with Session(engine) as session:
        job = session.get(BenchJob, job_id)
        if job:
            for k, v in fields.items():
                setattr(job, k, v)
            session.add(job)
            session.commit()


def run_bench(job_id: int, experiments: list[dict[str, Any]]) -> None:
    """Submit bench job to the GPU task queue."""
    from .task_queue import get_queue

    key = f"bench:{job_id}"

    def on_cancel() -> None:
        _update_bench_job(
            job_id,
            status="cancelled",
            completed_at=datetime.now(UTC),
        )

    get_queue().submit(
        key,
        "bench",
        _bench_worker,
        job_id,
        experiments,
        on_cancel=on_cancel,
    )


def _bench_worker(
    job_id: int,
    experiments: list[dict[str, Any]],
    cancel_event: threading.Event,
) -> None:
    def now() -> datetime:
        return datetime.now(UTC)

    if cancel_event.is_set():
        _update_bench_job(job_id, status="cancelled", completed_at=now())
        return

    libs_path = str(PROJECT_ROOT / "libs")
    runners_path = str(PROJECT_ROOT / "apps" / "backend" / "runners")
    for p in (libs_path, runners_path):
        if p not in sys.path:
            sys.path.insert(0, p)

    _update_bench_job(
        job_id,
        status="running",
        started_at=now(),
        total_experiments=len(experiments),
    )

    try:
        import yaml
        from fl_core.research.registry import _ensure_discovered

        _ensure_discovered()

        config_path = PROJECT_ROOT / "configs" / "research" / "bench_baseline.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        results_dir = PROJECT_ROOT / "results" / "bench"

        all_results: list[dict[str, Any]] = []

        for i, exp in enumerate(experiments):
            if cancel_event.is_set():
                _update_bench_job(job_id, status="cancelled", completed_at=now())
                logger.info("Bench job %d cancelled", job_id)
                return

            exp_name = exp.get("name", f"exp_{i}")
            atk = exp.get("attack_method")
            dfn = exp.get("defense_method")

            _update_bench_job(
                job_id,
                completed_experiments=i,
                current_experiment=exp_name,
            )

            try:
                from fl_core.research.runner import _run_single_seed

                metrics = _run_single_seed(
                    config=config,
                    experiment_name=exp_name,
                    seed=0,
                    results_dir=results_dir,
                    attack_method=atk,
                    defense_method=dfn,
                )
                acc = metrics.get("final_accuracy")
                loss = metrics.get("final_loss")
                global_res = metrics.get("global_results", {})
                all_results.append(
                    {
                        "name": exp_name,
                        "attack_method": atk,
                        "defense_method": dfn,
                        "final_accuracy": acc,
                        "final_loss": loss,
                        "rounds": global_res.get("rounds", []),
                        "accuracy_trajectory": global_res.get("global_accuracy", []),
                        "loss_trajectory": global_res.get("global_loss", []),
                        "error": None,
                    }
                )
                logger.info("[%d/%d] %s: acc=%.4f", i + 1, len(experiments), exp_name, acc or 0)
            except Exception as e:
                logger.error("[%d/%d] %s: FAILED %s", i + 1, len(experiments), exp_name, e)
                all_results.append(
                    {
                        "name": exp_name,
                        "attack_method": atk,
                        "defense_method": dfn,
                        "final_accuracy": None,
                        "final_loss": None,
                        "error": str(e),
                    }
                )

        _update_bench_job(
            job_id,
            status="completed",
            completed_experiments=len(experiments),
            current_experiment=None,
            results_json=json.dumps(all_results, ensure_ascii=False),
            completed_at=now(),
        )
        logger.info("Bench job %d completed: %d experiments", job_id, len(experiments))

    except Exception as e:
        logger.exception("Bench job %d failed", job_id)
        _update_bench_job(
            job_id,
            status="failed",
            error=str(e),
            completed_at=now(),
        )
