"""Baseline attack wrappers.

Wraps the existing model poisoning attacks (gaussian, scaling, ipm) from
``fl_core.attacks.model_poison`` as ``ResearchAttackStrategy`` subclasses so
they appear in the research registry and can be used as comparison baselines.
"""

from __future__ import annotations

from typing import Any

import torch

from fl_core.research.base_attack import ResearchAttackStrategy


class BaselineGaussianAttack(ResearchAttackStrategy):
    """Baseline: add Gaussian noise to all model parameters."""

    method_name = "baseline_gaussian"

    def __init__(self, noise_scale: float = 0.1):
        self.noise_scale = noise_scale

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config and "noise_scale" in config:
            self.noise_scale = config["noise_scale"]

    def attack(
        self,
        local_model_params: dict[str, torch.Tensor],
        global_model_params: dict[str, torch.Tensor],
        all_client_params: list[dict[str, torch.Tensor]] | None = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        poisoned = {}
        for k, v in local_model_params.items():
            noise = torch.randn_like(v) * self.noise_scale
            poisoned[k] = v + noise
        return poisoned


class BaselineScalingAttack(ResearchAttackStrategy):
    """Baseline: multiply all model parameters by a scale factor."""

    method_name = "baseline_scaling"

    def __init__(self, scale_factor: float = 10.0):
        self.scale_factor = scale_factor

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config and "scale_factor" in config:
            self.scale_factor = config["scale_factor"]

    def attack(
        self,
        local_model_params: dict[str, torch.Tensor],
        global_model_params: dict[str, torch.Tensor],
        all_client_params: list[dict[str, torch.Tensor]] | None = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        return {k: v * self.scale_factor for k, v in local_model_params.items()}


class BaselineIPMAttack(ResearchAttackStrategy):
    """Baseline: Inner Product Manipulation — move local params toward the
    global model scaled by attack_strength."""

    method_name = "baseline_ipm"

    def __init__(self, attack_strength: float = 5.0):
        self.attack_strength = attack_strength

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config and "attack_strength" in config:
            self.attack_strength = config["attack_strength"]

    def attack(
        self,
        local_model_params: dict[str, torch.Tensor],
        global_model_params: dict[str, torch.Tensor],
        all_client_params: list[dict[str, torch.Tensor]] | None = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        poisoned = {}
        for k in local_model_params:
            local_v = local_model_params[k]
            global_v = global_model_params.get(k, local_v)
            if global_v.shape != local_v.shape:
                poisoned[k] = local_v
                continue
            direction = global_v.to(local_v.device) - local_v
            poisoned[k] = local_v + self.attack_strength * direction
        return poisoned


class BaselineSignFlipAttack(ResearchAttackStrategy):
    """Baseline: sign-flipping — reverse the update direction.

    poisoned = global - scale * (local - global)
    """

    method_name = "baseline_sign_flip"

    def __init__(self, scale_factor: float = 1.0):
        self.scale_factor = scale_factor

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config and "scale_factor" in config:
            self.scale_factor = config["scale_factor"]

    def attack(
        self,
        local_model_params: dict[str, torch.Tensor],
        global_model_params: dict[str, torch.Tensor],
        all_client_params: list[dict[str, torch.Tensor]] | None = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        poisoned = {}
        for k in local_model_params:
            local_v = local_model_params[k]
            global_v = global_model_params.get(k, local_v).to(local_v.device)
            update = local_v - global_v
            poisoned[k] = global_v - self.scale_factor * update
        return poisoned


class BaselineALIEAttack(ResearchAttackStrategy):
    """Baseline: A Little Is Enough (Baruch et al., NeurIPS 2019).

    Crafts ``poisoned = global + (1 + z_max) * (local - global)`` as a
    non-omniscient approximation — the runner bridge does not pass
    ``all_client_params``, so we cannot compute the true benign mean/std.
    """

    method_name = "baseline_alie"

    def __init__(self, z_max: float = 1.5):
        self.z_max = z_max

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config and "z_max" in config:
            self.z_max = config["z_max"]

    def attack(
        self,
        local_model_params: dict[str, torch.Tensor],
        global_model_params: dict[str, torch.Tensor],
        all_client_params: list[dict[str, torch.Tensor]] | None = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        poisoned = {}
        scale = 1.0 + self.z_max
        for k in local_model_params:
            local_v = local_model_params[k]
            global_v = global_model_params.get(k, local_v).to(local_v.device)
            if local_v.shape != global_v.shape:
                poisoned[k] = local_v
                continue
            update = local_v - global_v
            poisoned[k] = global_v + scale * update
        return poisoned
