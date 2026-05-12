"""Scenario registry for FedArena multi-scenario evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_CONFIG_DIR = PROJECT_ROOT / "configs" / "research" / "scenarios"
ARENA_RESULTS_DIR = PROJECT_ROOT / "results" / "arena"

DEFAULT_SCENARIO = "cifar10_noniid"


@dataclass(frozen=True)
class ScenarioInfo:
    id: str
    name: str
    description: str
    is_default: bool = False


SCENARIOS: dict[str, ScenarioInfo] = {
    "cifar10_noniid": ScenarioInfo(
        id="cifar10_noniid",
        name="CIFAR-10 non-IID",
        description="CIFAR-10, Dirichlet non-IID (α=0.5), 30% malicious, CNN",
        is_default=True,
    ),
    "mnist_iid": ScenarioInfo(
        id="mnist_iid",
        name="MNIST IID",
        description="MNIST, IID distribution, 30% malicious, CNN",
    ),
    "cifar10_high_malicious": ScenarioInfo(
        id="cifar10_high_malicious",
        name="CIFAR-10 High Malicious",
        description="CIFAR-10, non-IID (α=0.5), 50% malicious, CNN",
    ),
    "cifar100_noniid": ScenarioInfo(
        id="cifar100_noniid",
        name="CIFAR-100 non-IID",
        description="CIFAR-100, non-IID (α=0.5), 30% malicious, CNN (100 classes)",
    ),
}


def list_scenarios() -> list[ScenarioInfo]:
    return list(SCENARIOS.values())


def get_scenario(scenario_id: str) -> ScenarioInfo | None:
    return SCENARIOS.get(scenario_id)


def get_config_path(scenario_id: str) -> Path:
    return SCENARIOS_CONFIG_DIR / f"{scenario_id}.yaml"


def get_matrix_path(scenario_id: str) -> Path:
    return ARENA_RESULTS_DIR / scenario_id / "benchmark_matrix.json"


def get_matrix_path_with_fallback(scenario_id: str) -> Path | None:
    """Return the matrix path if it exists, with fallback for the default scenario."""
    path = get_matrix_path(scenario_id)
    if path.exists():
        return path
    if scenario_id == DEFAULT_SCENARIO:
        legacy = ARENA_RESULTS_DIR / "benchmark_matrix.json"
        if legacy.exists():
            return legacy
    return None


def has_matrix(scenario_id: str) -> bool:
    return get_matrix_path_with_fallback(scenario_id) is not None
