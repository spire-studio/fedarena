"""Background evaluation worker.

Runs arena evaluation via the centralized task queue so only one
GPU-bound job executes at a time.
"""

from __future__ import annotations

import json
import logging
import statistics
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


def run_evaluation(
    job_id: int,
    submission_id: int,
    method_name: str,
    role: str,
    num_seeds: int | None = None,
) -> None:
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
        num_seeds,
        on_cancel=on_cancel,
    )


def _evaluation_worker(
    job_id: int,
    submission_id: int,
    method_name: str,
    role: str,
    num_seeds: int | None,
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

        from fl_core.research.scenarios import get_config_path, get_matrix_path_with_fallback, list_scenarios

        scenarios_with_matrix = []
        for s in list_scenarios():
            mp = get_matrix_path_with_fallback(s.id)
            if mp is not None:
                scenarios_with_matrix.append((s.id, mp, get_config_path(s.id)))

        if not scenarios_with_matrix:
            raise FileNotFoundError("No benchmark matrices found. Run 'arena generate' first.")

        total_scenarios = len(scenarios_with_matrix)
        _update_job(job_id, total_scenarios=total_scenarios)

        all_scenario_results: dict[str, dict[str, Any]] = {}

        for sc_idx, (scenario_id, matrix_path, config_path) in enumerate(scenarios_with_matrix):
            if cancel_event.is_set():
                _update_job(job_id, status="cancelled", completed_at=now())
                _update_submission(submission_id, status="failed", updated_at=now())
                logger.info("Evaluation cancelled: %s", method_name)
                return

            _update_job(job_id, current_scenario=scenario_id, completed_scenarios=sc_idx)

            scenario_results = _run_scenario_opponents(
                job_id=job_id,
                method_name=method_name,
                role=role,
                matrix_path=matrix_path,
                config_path=config_path,
                scenario_id=scenario_id,
                scenario_idx=sc_idx,
                total_scenarios=total_scenarios,
                num_seeds=num_seeds,
                cancel_event=cancel_event,
                now=now,
            )

            if scenario_results is None:
                _update_submission(submission_id, status="failed", updated_at=now())
                return

            all_scenario_results[scenario_id] = scenario_results

        if len(all_scenario_results) == 1 and "cifar10_noniid" in all_scenario_results:
            final_results = all_scenario_results["cifar10_noniid"]
        else:
            final_results = {"scenarios": all_scenario_results}
            global_summary = _compute_global_summary(all_scenario_results)
            if global_summary:
                final_results["__global_summary__"] = global_summary

        output_dir = PROJECT_ROOT / "results" / "arena"
        _update_job(
            job_id,
            status="completed",
            current_opponent=None,
            current_scenario=None,
            completed_scenarios=total_scenarios,
            progress="completed",
            results_json=json.dumps(final_results, ensure_ascii=False),
            completed_at=now(),
        )
        _update_submission(submission_id, status="completed", updated_at=now())

        eval_path = output_dir / f"eval_{method_name}.json"
        eval_path.parent.mkdir(parents=True, exist_ok=True)
        eval_path.write_text(
            json.dumps({"method": method_name, "role": role, "results": final_results}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("Evaluation completed: %s (%d scenarios)", method_name, total_scenarios)

    except Exception as e:
        logger.exception("Evaluation failed for %s", method_name)
        _update_job(job_id, status="failed", error=str(e), completed_at=now())
        _update_submission(submission_id, status="failed", updated_at=now())


def _run_scenario_opponents(
    *,
    job_id: int,
    method_name: str,
    role: str,
    matrix_path: Path,
    config_path: Path,
    scenario_id: str,
    scenario_idx: int,
    total_scenarios: int,
    num_seeds: int | None = None,
    cancel_event: threading.Event,
    now,
) -> dict[str, Any] | None:
    """Run all opponent matches for one scenario. Returns results dict or None if cancelled."""
    NO_ATTACK = "__none__"
    NO_DEFENSE = "__none__"

    matrix_data = json.loads(matrix_path.read_text(encoding="utf-8"))
    config = _load_config(config_path)
    output_dir = PROJECT_ROOT / "results" / "arena"
    seeds = matrix_data.get("seeds", [0])
    if num_seeds is not None and num_seeds > 0:
        seeds = list(range(num_seeds))
    matrix = matrix_data.get("matrix", {})

    opponents = matrix_data["defenses"] if role == "attack" else matrix_data["attacks"]
    total = len(opponents)
    _update_job(job_id, total_opponents=total, completed_opponents=0)

    sc_label = f"{scenario_id} ({scenario_idx + 1}/{total_scenarios})" if total_scenarios > 1 else ""

    results: dict[str, Any] = {}

    for i, opp in enumerate(opponents):
        if cancel_event.is_set():
            _update_job(job_id, status="cancelled", completed_at=now())
            logger.info("Evaluation cancelled: %s", method_name)
            return None

        progress = f"{sc_label} {i}/{total} opponents" if sc_label else f"{i}/{total} opponents done"
        _update_job(job_id, completed_opponents=i, current_opponent=opp, progress=progress)

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
                        "initial_accuracy": metrics.get("initial_accuracy"),
                        "max_accuracy": metrics.get("max_accuracy"),
                        "convergence_speed": metrics.get("convergence_speed"),
                        "stability": metrics.get("stability"),
                        "runtime_seconds": metrics.get("runtime_seconds"),
                        "rounds": global_res.get("rounds", []),
                        "accuracy_trajectory": global_res.get("global_accuracy", []),
                        "loss_trajectory": global_res.get("global_loss", []),
                    }
                )
            except Exception as e:
                logger.error("Seed %d failed: %s", seed, e)
                seed_results.append({"seed": seed, "final_accuracy": None, "error": str(e)})

        valid_acc = [r["final_accuracy"] for r in seed_results if r["final_accuracy"] is not None]
        avg_acc = sum(valid_acc) / len(valid_acc) if valid_acc else None

        if role == "attack":
            baseline_acc = matrix.get(NO_ATTACK, {}).get(opp, {}).get("avg_final_accuracy")
        else:
            baseline_acc = matrix.get(opp, {}).get(NO_DEFENSE, {}).get("avg_final_accuracy")

        accuracy_drop = None
        if avg_acc is not None and baseline_acc is not None:
            accuracy_drop = baseline_acc - avg_acc

        def _avg(key: str) -> float | None:
            vals = [r[key] for r in seed_results if r.get(key) is not None]
            return sum(vals) / len(vals) if vals else None

        results[opp] = {
            "avg_final_accuracy": avg_acc,
            "accuracy_drop": accuracy_drop,
            "baseline_accuracy": baseline_acc,
            "max_accuracy": _avg("max_accuracy"),
            "avg_convergence_speed": _avg("convergence_speed"),
            "avg_stability": _avg("stability"),
            "avg_runtime_seconds": _avg("runtime_seconds"),
            "std_final_accuracy": statistics.stdev(valid_acc) if len(valid_acc) > 1 else 0.0,
            "per_seed": seed_results,
        }

        progress = f"{sc_label} {i + 1}/{total} opponents" if sc_label else f"{i + 1}/{total} opponents done"
        _update_job(
            job_id,
            completed_opponents=i + 1,
            progress=progress,
            results_json=json.dumps(results, ensure_ascii=False),
        )

    results["__summary__"] = _compute_scenario_summary(results)
    return results


def _compute_scenario_summary(results: dict[str, Any]) -> dict[str, Any]:
    all_accs = [r["avg_final_accuracy"] for r in results.values() if r.get("avg_final_accuracy") is not None]
    all_drops = [r["accuracy_drop"] for r in results.values() if r.get("accuracy_drop") is not None]
    all_conv = [r["avg_convergence_speed"] for r in results.values() if r.get("avg_convergence_speed") is not None]
    all_stab = [r["avg_stability"] for r in results.values() if r.get("avg_stability") is not None]
    all_rt = [r["avg_runtime_seconds"] for r in results.values() if r.get("avg_runtime_seconds") is not None]

    summary: dict[str, Any] = {}
    if all_accs:
        summary["avg_accuracy"] = sum(all_accs) / len(all_accs)
        summary["worst_case_accuracy"] = min(all_accs)
        summary["best_case_accuracy"] = max(all_accs)
    if all_drops:
        summary["avg_accuracy_drop"] = sum(all_drops) / len(all_drops)
    if all_conv:
        summary["avg_convergence_speed"] = sum(all_conv) / len(all_conv)
    if all_stab:
        summary["avg_stability"] = sum(all_stab) / len(all_stab)
    if all_rt:
        summary["avg_runtime_seconds"] = sum(all_rt) / len(all_rt)
    return summary


def _compute_global_summary(all_scenario_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Aggregate summaries across all scenarios."""
    summaries = [s.get("__summary__", {}) for s in all_scenario_results.values() if s.get("__summary__")]
    if not summaries:
        return {}

    def _avg_key(key: str) -> float | None:
        vals = [s[key] for s in summaries if key in s and s[key] is not None]
        return sum(vals) / len(vals) if vals else None

    result: dict[str, Any] = {}
    for key in ("avg_accuracy", "avg_accuracy_drop", "avg_convergence_speed", "avg_stability", "avg_runtime_seconds"):
        val = _avg_key(key)
        if val is not None:
            result[key] = val

    worst = [s["worst_case_accuracy"] for s in summaries if "worst_case_accuracy" in s]
    if worst:
        result["worst_case_accuracy"] = min(worst)
    best = [s["best_case_accuracy"] for s in summaries if "best_case_accuracy" in s]
    if best:
        result["best_case_accuracy"] = max(best)

    return result


def _load_config(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
