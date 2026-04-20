#!/usr/bin/env python3
"""
FedArena Arena — benchmark matrix generator and evaluator.

Generates the full attack × defense benchmark matrix and provides
tools to evaluate user-submitted methods against it.

Usage::

    # Generate benchmark matrix (run all attack × defense combinations)
    python -m fl_core.research.arena generate \\
        --config configs/research/bench_baseline.yaml \\
        --seeds 0 \\
        --output results/arena

    # Evaluate a new attack against the matrix
    python -m fl_core.research.arena evaluate \\
        --method my_new_attack \\
        --role attack \\
        --config configs/research/bench_baseline.yaml \\
        --matrix results/arena/benchmark_matrix.json

    # Evaluate a new defense against the matrix
    python -m fl_core.research.arena evaluate \\
        --method my_new_defense \\
        --role defense \\
        --config configs/research/bench_baseline.yaml \\
        --matrix results/arena/benchmark_matrix.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
FL_CORE_PARENT = PROJECT_ROOT / "libs"
if str(FL_CORE_PARENT) not in sys.path:
    sys.path.insert(0, str(FL_CORE_PARENT))
RUNNERS_DIR = PROJECT_ROOT / "apps" / "backend" / "runners"
if str(RUNNERS_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNERS_DIR))

logger = logging.getLogger("fl_core.research.arena")

# Special sentinel for "no attack" / "no defense"
NO_ATTACK = "__none__"
NO_DEFENSE = "__none__"


def _load_config(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _run_combination(
    config: dict[str, Any],
    attack_method: str | None,
    defense_method: str | None,
    seed: int,
    results_dir: Path,
) -> dict[str, Any]:
    """Run a single attack × defense combination for one seed."""
    from fl_core.research.runner import _run_single_seed

    experiment_name = f"{attack_method or NO_ATTACK}_vs_{defense_method or NO_DEFENSE}"

    return _run_single_seed(
        config=config,
        experiment_name=experiment_name,
        seed=seed,
        results_dir=results_dir,
        attack_method=attack_method,
        defense_method=defense_method,
    )


def generate_matrix(
    config_path: Path,
    seeds: list[int],
    output_dir: Path,
) -> dict[str, Any]:
    """Generate the full benchmark matrix."""
    from fl_core.research.registry import _ensure_discovered, list_attacks, list_defenses

    _ensure_discovered()

    # The baseline matrix only includes the built-in ``baseline_*`` methods;
    # user submissions under ``attacks/submissions/`` or ``defenses/submissions/``
    # are excluded so arena generate produces a stable reference grid.
    attacks = [None] + [a for a in list_attacks() if a.startswith("baseline_")]
    defenses = [None] + [d for d in list_defenses() if d.startswith("baseline_")]

    config = _load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix: dict[str, dict[str, dict[str, Any]]] = {}
    total = len(attacks) * len(defenses) * len(seeds)
    done = 0

    print(f"\n{'=' * 60}")
    print("  FedArena Arena — Benchmark Matrix Generation")
    print(f"  Attacks:  {[a or 'none' for a in attacks]}")
    print(f"  Defenses: {[d or 'none' for d in defenses]}")
    print(f"  Seeds:    {seeds}")
    print(f"  Total:    {total} runs")
    print(f"{'=' * 60}\n")

    for atk in attacks:
        atk_key = atk or NO_ATTACK
        if atk_key not in matrix:
            matrix[atk_key] = {}

        for dfn in defenses:
            dfn_key = dfn or NO_DEFENSE
            seed_results = []

            for seed in seeds:
                done += 1
                label = f"[{done}/{total}] {atk_key} vs {dfn_key} (seed={seed})"
                print(f"  {label} ...", end=" ", flush=True)
                t0 = time.time()

                try:
                    metrics = _run_combination(
                        config=config,
                        attack_method=atk,
                        defense_method=dfn,
                        seed=seed,
                        results_dir=output_dir / "runs",
                    )
                    acc = metrics.get("final_accuracy", None)
                    elapsed = time.time() - t0
                    print(f"acc={acc:.4f} ({elapsed:.0f}s)" if acc else f"FAILED ({elapsed:.0f}s)")
                    seed_results.append(
                        {
                            "seed": seed,
                            "final_accuracy": acc,
                            "error": metrics.get("error"),
                        }
                    )
                except Exception as e:
                    elapsed = time.time() - t0
                    print(f"ERROR: {e} ({elapsed:.0f}s)")
                    seed_results.append(
                        {
                            "seed": seed,
                            "final_accuracy": None,
                            "error": str(e),
                        }
                    )

            # Aggregate seeds
            valid_accs = [r["final_accuracy"] for r in seed_results if r["final_accuracy"] is not None]
            matrix[atk_key][dfn_key] = {
                "avg_final_accuracy": sum(valid_accs) / len(valid_accs) if valid_accs else None,
                "per_seed": seed_results,
                "seeds_succeeded": len(valid_accs),
            }

    # Save matrix
    matrix_path = output_dir / "benchmark_matrix.json"
    matrix_meta = {
        "config": str(config_path),
        "seeds": seeds,
        "attacks": [a or NO_ATTACK for a in attacks],
        "defenses": [d or NO_DEFENSE for d in defenses],
        "matrix": matrix,
    }
    matrix_path.write_text(json.dumps(matrix_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print summary table
    _print_matrix_table(matrix, attacks, defenses)

    print(f"\n  Matrix saved to: {matrix_path}")
    return matrix_meta


def evaluate_method(
    method_name: str,
    role: str,
    config_path: Path,
    matrix_path: Path,
    seeds: list[int],
    output_dir: Path,
) -> dict[str, Any]:
    """Evaluate a user-submitted method against the benchmark matrix."""
    from fl_core.research.registry import _ensure_discovered

    _ensure_discovered()

    matrix_data = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix = matrix_data["matrix"]
    config = _load_config(config_path)

    if role == "attack":
        # New attack vs all defenses in the matrix
        opponents = [d for d in matrix_data["defenses"]]
    else:
        # New defense vs all attacks in the matrix
        opponents = [a for a in matrix_data["attacks"]]

    print(f"\n{'=' * 60}")
    print(f"  FedArena Arena — Evaluating {role}: {method_name}")
    print(f"  Against: {opponents}")
    print(f"{'=' * 60}\n")

    results = {}
    for opp in opponents:
        if role == "attack":
            atk = method_name
            dfn = opp if opp != NO_DEFENSE else None
        else:
            atk = opp if opp != NO_ATTACK else None
            dfn = method_name

        seed_results = []
        for seed in seeds:
            label = f"{method_name} vs {opp} (seed={seed})"
            print(f"  {label} ...", end=" ", flush=True)
            t0 = time.time()
            try:
                metrics = _run_combination(config, atk, dfn, seed, output_dir / "runs")
                acc = metrics.get("final_accuracy")
                elapsed = time.time() - t0
                print(f"acc={acc:.4f} ({elapsed:.0f}s)" if acc else f"FAILED ({elapsed:.0f}s)")
                seed_results.append({"seed": seed, "final_accuracy": acc})
            except Exception as e:
                elapsed = time.time() - t0
                print(f"ERROR: {e} ({elapsed:.0f}s)")
                seed_results.append({"seed": seed, "final_accuracy": None, "error": str(e)})

        valid = [r["final_accuracy"] for r in seed_results if r["final_accuracy"] is not None]
        results[opp] = {
            "avg_final_accuracy": sum(valid) / len(valid) if valid else None,
            "per_seed": seed_results,
        }

    # Print comparison
    _print_evaluation_report(method_name, role, results, matrix)

    # Save
    eval_path = output_dir / f"eval_{method_name}.json"
    eval_path.parent.mkdir(parents=True, exist_ok=True)
    eval_path.write_text(
        json.dumps(
            {
                "method": method_name,
                "role": role,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\n  Evaluation saved to: {eval_path}")
    return results


def _print_matrix_table(matrix, attacks, defenses):
    """Print the benchmark matrix as a formatted table."""
    print(f"\n{'=' * 60}")
    print("  Benchmark Matrix (avg_final_accuracy)")
    print(f"{'=' * 60}")

    def_keys = [d or NO_DEFENSE for d in defenses]
    header = f"{'Attack':<20}" + "".join(f"{d:>14}" for d in def_keys)
    print(header)
    print("-" * len(header))

    for atk in attacks:
        atk_key = atk or NO_ATTACK
        row = f"{atk_key:<20}"
        for dfn_key in def_keys:
            val = matrix.get(atk_key, {}).get(dfn_key, {}).get("avg_final_accuracy")
            row += f"{val:>14.4f}" if val is not None else f"{'FAIL':>14}"
        print(row)


def _print_evaluation_report(method_name, role, results, matrix):
    """Print comparison of new method vs existing methods."""
    print(f"\n{'=' * 60}")
    print(f"  Evaluation Report: {method_name} ({role})")
    print(f"{'=' * 60}")

    if role == "attack":
        # Compare new attack's row vs existing attacks' rows
        print(f"\n  {'Defense':<20} {'New Attack':>14}", end="")
        # Get existing attacks from matrix
        existing_attacks = [a for a in matrix if a != NO_ATTACK]
        for ea in existing_attacks:
            print(f" {ea:>14}", end="")
        print()
        print("-" * (34 + 14 * len(existing_attacks)))

        for opp, res in results.items():
            new_acc = res.get("avg_final_accuracy")
            row = f"  {opp:<20}"
            row += f"{new_acc:>14.4f}" if new_acc else f"{'FAIL':>14}"
            for ea in existing_attacks:
                ea_acc = matrix.get(ea, {}).get(opp, {}).get("avg_final_accuracy")
                row += f" {ea_acc:>14.4f}" if ea_acc else f" {'N/A':>14}"
            print(row)

        # Overall ranking
        all_attacks = {}
        for ea in existing_attacks:
            accs = [
                matrix[ea][d].get("avg_final_accuracy")
                for d in results
                if matrix.get(ea, {}).get(d, {}).get("avg_final_accuracy") is not None
            ]
            if accs:
                all_attacks[ea] = sum(accs) / len(accs)
        new_accs = [r["avg_final_accuracy"] for r in results.values() if r["avg_final_accuracy"] is not None]
        if new_accs:
            all_attacks[method_name] = sum(new_accs) / len(new_accs)

        # Lower is better for attacks
        ranking = sorted(all_attacks.items(), key=lambda x: x[1])
        print("\n  Overall Ranking (lower accuracy = stronger attack):")
        for i, (name, avg) in enumerate(ranking, 1):
            marker = " <<<" if name == method_name else ""
            print(f"    {i}. {name}: {avg:.4f}{marker}")

    else:
        # Compare new defense's column vs existing defenses' columns
        print(f"\n  {'Attack':<20} {'New Defense':>14}", end="")
        existing_defenses = [d for d in list(matrix.get(NO_ATTACK, {}).keys()) if d != NO_DEFENSE]
        for ed in existing_defenses:
            print(f" {ed:>14}", end="")
        print()
        print("-" * (34 + 14 * len(existing_defenses)))

        for opp, res in results.items():
            new_acc = res.get("avg_final_accuracy")
            row = f"  {opp:<20}"
            row += f"{new_acc:>14.4f}" if new_acc else f"{'FAIL':>14}"
            for ed in existing_defenses:
                ed_acc = matrix.get(opp, {}).get(ed, {}).get("avg_final_accuracy")
                row += f" {ed_acc:>14.4f}" if ed_acc else f" {'N/A':>14}"
            print(row)

        # Higher is better for defenses
        all_defenses = {}
        for ed in existing_defenses:
            accs = [
                matrix[a][ed].get("avg_final_accuracy")
                for a in results
                if matrix.get(a, {}).get(ed, {}).get("avg_final_accuracy") is not None
            ]
            if accs:
                all_defenses[ed] = sum(accs) / len(accs)
        new_accs = [r["avg_final_accuracy"] for r in results.values() if r["avg_final_accuracy"] is not None]
        if new_accs:
            all_defenses[method_name] = sum(new_accs) / len(new_accs)

        ranking = sorted(all_defenses.items(), key=lambda x: -x[1])
        print("\n  Overall Ranking (higher accuracy = stronger defense):")
        for i, (name, avg) in enumerate(ranking, 1):
            marker = " <<<" if name == method_name else ""
            print(f"    {i}. {name}: {avg:.4f}{marker}")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="FedArena Arena")
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = sub.add_parser("generate", help="Generate benchmark matrix")
    gen.add_argument("--config", type=Path, required=True)
    gen.add_argument("--seeds", type=str, default="0")
    gen.add_argument("--output", type=Path, default=Path("results/arena"))

    # evaluate
    evl = sub.add_parser("evaluate", help="Evaluate a new method")
    evl.add_argument("--method", required=True)
    evl.add_argument("--role", required=True, choices=("attack", "defense"))
    evl.add_argument("--config", type=Path, required=True)
    evl.add_argument("--matrix", type=Path, required=True)
    evl.add_argument("--seeds", type=str, default="0")
    evl.add_argument("--output", type=Path, default=Path("results/arena"))

    args = parser.parse_args()
    seeds = [int(s.strip()) for s in args.seeds.split(",")]

    from fl_core.research.registry import _ensure_discovered

    _ensure_discovered()

    if args.command == "generate":
        generate_matrix(args.config, seeds, args.output)
    elif args.command == "evaluate":
        evaluate_method(args.method, args.role, args.config, args.matrix, seeds, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
