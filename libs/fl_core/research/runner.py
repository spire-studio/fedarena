#!/usr/bin/env python3
"""
Research benchmark runner.

Runs an attack and/or defense strategy against a fixed FL experiment
environment and saves structured results. Used by Arena and Bench to
execute individual matrix cells.

Usage::

    # Attack vs defense:
    python -m fl_core.research.runner \\
        --attack-method baseline_ipm \\
        --defense-method baseline_krum \\
        --experiment-name ipm_vs_krum \\
        --config configs/research/bench_baseline.yaml

    # Vanilla FL (no attack, no defense override):
    python -m fl_core.research.runner \\
        --experiment-name vanilla_fedavg \\
        --config configs/research/bench_baseline.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Path setup — same approach as the existing experiment_runner.py
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # libs/fl_core/research/runner.py -> project root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
FL_CORE_PARENT = PROJECT_ROOT / "libs"
if str(FL_CORE_PARENT) not in sys.path:
    sys.path.insert(0, str(FL_CORE_PARENT))
RUNNERS_DIR = PROJECT_ROOT / "apps" / "backend" / "runners"
if str(RUNNERS_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNERS_DIR))

logger = logging.getLogger("fl_core.research.runner")


# ---------------------------------------------------------------------------
# Bridge classes
# ---------------------------------------------------------------------------


class ResearchModelPoisonAttack:
    """Drop-in replacement for ``ModelPoisonAttack`` that delegates to a
    ``ResearchAttackStrategy`` instance.
    """

    def __init__(
        self,
        strategy: Any,
        attack_config: dict[str, Any],
        global_model_getter: Any = None,
    ):
        self.strategy = strategy
        self.attack_config = attack_config
        self.malicious_clients = attack_config.get("malicious_clients", [])
        self.logger = logging.getLogger(__name__)
        self._global_model_getter = global_model_getter

    def is_malicious_client(self, client_id: int) -> bool:
        return client_id in self.malicious_clients

    def apply_attack(
        self,
        client_id: int,
        model_params: dict[str, Any],
        target_params: Any = None,
        override_type: str | None = None,
        override_params: dict | None = None,
    ) -> dict[str, Any]:
        if not self.is_malicious_client(client_id):
            return model_params

        global_params = target_params or {}
        self.logger.info(
            "Research attack '%s' on client %d",
            self.strategy.method_name,
            client_id,
        )
        return self.strategy.attack(
            local_model_params=model_params,
            global_model_params=global_params,
            round_num=0,
            client_id=client_id,
        )

    def get_attack_info(self) -> dict[str, Any]:
        return {
            "attack_type": f"research:{self.strategy.method_name}",
            "malicious_clients": self.malicious_clients,
            "num_malicious_clients": len(self.malicious_clients),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Config must be a YAML/JSON object")
    return loaded


def _set_value_by_path(obj: dict[str, Any], path: str, value: Any) -> None:
    parts = [p for p in path.split(".") if p]
    cur = obj
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _run_single_seed(
    config: dict[str, Any],
    experiment_name: str,
    seed: int,
    results_dir: Path,
    attack_method: str | None = None,
    defense_method: str | None = None,
) -> dict[str, Any]:
    """Run one FL simulation for a single seed, returning metrics dict.

    Pass ``attack_method`` and/or ``defense_method`` to inject the
    corresponding research strategies; ``experiment_name`` is used only
    for the per-seed results directory.
    """
    import copy
    import random

    import numpy as np
    import torch

    # Reproducibility
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    cfg = copy.deepcopy(config)

    # Force simulation mode
    _set_value_by_path(cfg, "system.mode", "simulation")
    _set_value_by_path(cfg, "system.role", "server")
    _set_value_by_path(cfg, "system.node_role", "server")

    # If attack_method is given, ensure attack is enabled in config
    if attack_method:
        _set_value_by_path(cfg, "attack.enable", True)

    # Unique results dir per seed to avoid collisions
    seed_results_dir = results_dir / experiment_name / f"seed_{seed}"
    seed_results_dir.mkdir(parents=True, exist_ok=True)
    _set_value_by_path(cfg, "logging.results_dir", str(seed_results_dir))
    _set_value_by_path(cfg, "logging.log_dir", str(seed_results_dir / "logs"))

    # Write temp config
    tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    yaml.safe_dump(cfg, tmp, allow_unicode=True, sort_keys=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    fw = None
    try:
        from core_runtime import FederatedLearningFramework

        fw = FederatedLearningFramework(config_path=str(tmp_path))

        # -- Phase 1: init, data, model, components ---
        if not fw.initialize_system():
            return {"error": "initialize_system failed", "seed": seed}
        if not fw.prepare_data():
            return {"error": "prepare_data failed", "seed": seed}
        if not fw.setup_models():
            return {"error": "setup_models failed", "seed": seed}
        if not fw.setup_federated_components():
            return {"error": "setup_federated_components failed", "seed": seed}

        # -- Phase 2: inject research strategies ---
        if attack_method:
            from fl_core.research.registry import get_attack

            strategy_cls = get_attack(attack_method)
            strategy = strategy_cls()
            strategy.setup(cfg.get("attack", {}).get("attack_params"))

            bridge = ResearchModelPoisonAttack(
                strategy=strategy,
                attack_config=cfg.get("attack", {}),
            )
            fw.client_manager.model_attacker.model_poison_attack = bridge
            fw.client_manager.model_attacker.apply_model_poison_attack = bridge.apply_attack

        if defense_method:
            from fl_core.research.registry import get_defense

            strategy_cls = get_defense(defense_method)
            strategy = strategy_cls()
            strategy.setup(cfg.get("defense", {}).get("defense_params"))
            fw.server.aggregator = strategy

        # -- Phase 3: run training ---
        if not fw.run_federated_training():
            return {"error": "run_federated_training failed", "seed": seed}

        # -- Phase 4: collect metrics ---
        metrics = _extract_metrics(fw)
        metrics["seed"] = seed
        metrics["experiment_name"] = experiment_name
        if attack_method:
            metrics["attack_method"] = attack_method
        if defense_method:
            metrics["defense_method"] = defense_method

        # Save per-seed result
        result_file = results_dir / experiment_name / f"seed_{seed}.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

        return metrics

    finally:
        if fw is not None:
            fw.cleanup_resources()
        del fw
        import gc

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        tmp_path.unlink(missing_ok=True)


def _extract_metrics(fw: Any) -> dict[str, Any]:
    """Extract metrics from the framework's logger after training."""
    metrics: dict[str, Any] = {}

    if fw.logger and hasattr(fw.logger, "training_results"):
        results = fw.logger.training_results
        global_results = results.get("global_results", {})
        client_results = results.get("client_results", {})

        metrics["global_results"] = global_results
        metrics["client_results"] = client_results

        # Extract key scalars
        acc_list = global_results.get("global_accuracy", [])
        loss_list = global_results.get("global_loss", [])
        if acc_list:
            metrics["final_accuracy"] = acc_list[-1]
            metrics["initial_accuracy"] = acc_list[0]
            metrics["accuracy_trajectory"] = acc_list
        if loss_list:
            metrics["final_loss"] = loss_list[-1]

    return metrics


def _build_summary(
    all_seed_metrics: list[dict[str, Any]],
    experiment_name: str,
    config_name: str,
) -> dict[str, Any]:
    """Aggregate metrics across seeds into a summary."""
    valid = [m for m in all_seed_metrics if "error" not in m]
    failed = [m for m in all_seed_metrics if "error" in m]

    summary: dict[str, Any] = {
        "experiment_name": experiment_name,
        "config": config_name,
        "seeds_total": len(all_seed_metrics),
        "seeds_succeeded": len(valid),
        "seeds_failed": len(failed),
    }

    if not valid:
        summary["metrics"] = {"error": "All seeds failed"}
        summary["errors"] = [m.get("error", "unknown") for m in failed]
        return summary

    # Average scalar metrics
    final_accs = [m["final_accuracy"] for m in valid if "final_accuracy" in m]
    final_losses = [m["final_loss"] for m in valid if "final_loss" in m]
    initial_accs = [m["initial_accuracy"] for m in valid if "initial_accuracy" in m]

    metrics: dict[str, Any] = {}
    if final_accs:
        metrics["avg_final_accuracy"] = sum(final_accs) / len(final_accs)
        metrics["min_final_accuracy"] = min(final_accs)
        metrics["max_final_accuracy"] = max(final_accs)
    if initial_accs and final_accs:
        metrics["avg_accuracy_drop"] = sum(initial_accs) / len(initial_accs) - sum(final_accs) / len(final_accs)
    if final_losses:
        metrics["avg_final_loss"] = sum(final_losses) / len(final_losses)

    metrics["per_seed"] = [
        {
            "seed": m.get("seed"),
            "final_accuracy": m.get("final_accuracy"),
            "final_loss": m.get("final_loss"),
        }
        for m in valid
    ]

    summary["metrics"] = metrics
    if failed:
        summary["errors"] = [m.get("error", "unknown") for m in failed]

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="FedArena FL research benchmark runner")

    parser.add_argument(
        "--attack-method",
        default=None,
        help="Attack strategy name (e.g. baseline_ipm, arena_attack_const_bias)",
    )
    parser.add_argument(
        "--defense-method",
        default=None,
        help="Defense strategy name (e.g. baseline_krum, arena_defense_clipped_mean)",
    )
    parser.add_argument(
        "--experiment-name",
        default=None,
        help="Name for the experiment (used for results dir). Auto-generated if not specified.",
    )

    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to baseline YAML config",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default="0,1,2",
        help="Comma-separated seed list (default: 0,1,2)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/research"),
        help="Root directory for results output",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run ID for backend integration",
    )
    args = parser.parse_args()

    if args.attack_method is None and args.defense_method is None and args.experiment_name is None:
        parser.error("Provide at least one of --attack-method, --defense-method, or --experiment-name.")

    if args.experiment_name:
        experiment_name = args.experiment_name
    else:
        atk_part = args.attack_method or "none"
        def_part = args.defense_method or "fedavg"
        experiment_name = f"{atk_part}_vs_{def_part}"

    seeds = [int(s.strip()) for s in args.seeds.split(",")]
    config = _load_config(args.config)
    config_name = args.config.stem

    print(f"\n{'=' * 60}")
    print("  FedArena Research Benchmark")
    print(f"  Experiment: {experiment_name}")
    print(f"  Attack:     {args.attack_method or '(none)'}")
    print(f"  Defense:    {args.defense_method or '(config default)'}")
    print(f"  Config:  {args.config}")
    print(f"  Seeds:   {seeds}")
    print(f"  Output:  {args.results_dir}")
    print(f"{'=' * 60}\n")

    # Trigger registry discovery
    from fl_core.research.registry import _ensure_discovered

    _ensure_discovered()

    all_metrics: list[dict[str, Any]] = []
    for seed in seeds:
        print(f"\n--- Seed {seed} ---")
        t0 = time.time()
        metrics = _run_single_seed(
            config=config,
            experiment_name=experiment_name,
            seed=seed,
            results_dir=args.results_dir,
            attack_method=args.attack_method,
            defense_method=args.defense_method,
        )
        elapsed = time.time() - t0
        all_metrics.append(metrics)

        if "error" in metrics:
            print(f"  FAILED: {metrics['error']} ({elapsed:.1f}s)")
        else:
            acc = metrics.get("final_accuracy", "N/A")
            print(f"  final_accuracy={acc}  ({elapsed:.1f}s)")

    # Build and save summary
    summary = _build_summary(all_metrics, experiment_name, config_name)
    if args.attack_method:
        summary["attack_method"] = args.attack_method
    if args.defense_method:
        summary["defense_method"] = args.defense_method
    summary_path = args.results_dir / experiment_name / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"  Summary saved to: {summary_path}")
    avg_acc = summary.get("metrics", {}).get("avg_final_accuracy")
    if avg_acc is not None:
        print(f"  avg_final_accuracy: {avg_acc:.4f}")
    print(f"  seeds: {summary['seeds_succeeded']}/{summary['seeds_total']} succeeded")
    print(f"{'=' * 60}\n")

    return 0 if summary["seeds_succeeded"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
