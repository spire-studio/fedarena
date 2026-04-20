"""
Centered Clipping防御算法实现
Centered Clipping defense with momentum

Reference: Karimireddy et al., "Learning from History for Byzantine Robust Optimization", ICML 2021

Algorithm:
  Maintain momentum vector v.
  Each round: v = v + (1/n) * sum(clip(x_i - v, tau))
  where clip(z, tau) = z * min(1, tau / ||z||_2)
"""

import logging
from typing import Any

import torch

from fl_core.federated.aggregation import AggregationStrategy


class CenteredClippingDefense(AggregationStrategy):
    def __init__(self, norm_threshold: float = 100.0, num_iters: int = 1, device: torch.device = None):
        self.norm_threshold = norm_threshold
        self.num_iters = num_iters
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("CenteredClippingDefense")
        # Persistent momentum across rounds
        self._momentum: dict[str, torch.Tensor] | None = None

    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        n = len(client_models)
        param_keys = client_models[0].keys()

        # Initialize momentum on first call
        if self._momentum is None:
            self._momentum = {k: torch.zeros_like(client_models[0][k], device=self.device) for k in param_keys}

        for _ in range(self.num_iters):
            clipped_sum = {k: torch.zeros_like(self._momentum[k]) for k in param_keys}

            for model in client_models:
                # Compute centered difference and clip
                diff_vec = []
                for k in param_keys:
                    diff_vec.append((model[k].to(self.device).float() - self._momentum[k]).flatten())
                diff_flat = torch.cat(diff_vec)
                diff_norm = diff_flat.norm()

                clip_factor = min(1.0, self.norm_threshold / (diff_norm.item() + 1e-10))

                for k in param_keys:
                    diff = model[k].to(self.device).float() - self._momentum[k]
                    clipped_sum[k] += diff * clip_factor

            # Update momentum
            for k in param_keys:
                self._momentum[k] = self._momentum[k] + clipped_sum[k] / n

        self.logger.info(f"Centered Clipping: tau={self.norm_threshold}, iters={self.num_iters}")
        return {k: v.clone() for k, v in self._momentum.items()}

    def get_name(self) -> str:
        return "centered_clipping"


def create_centered_clipping_defense(config: dict[str, Any] = None, **kwargs) -> CenteredClippingDefense:
    norm_threshold = 100.0
    num_iters = 1
    if config is not None:
        defense_params = config.get("defense_params", {})
        norm_threshold = defense_params.get("norm_threshold", norm_threshold)
        num_iters = defense_params.get("num_iters", num_iters)
    norm_threshold = kwargs.get("norm_threshold", norm_threshold)
    num_iters = kwargs.get("num_iters", num_iters)
    return CenteredClippingDefense(norm_threshold=norm_threshold, num_iters=num_iters, device=kwargs.get("device"))
