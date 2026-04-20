"""
FLTrust防御算法实现
FLTrust: trust-score-based aggregation using a server-side root dataset

Reference: Cao et al., "FLTrust: Byzantine-robust Federated Learning via Trust Bootstrapping", NDSS 2021

Algorithm:
  Server maintains a small clean root dataset and computes a server update.
  1. Compute trust scores: ReLU(cosine_similarity(client_update, server_update))
  2. Normalize each client update to have the same norm as server update
  3. Weighted average using normalized trust scores
"""

import logging
from typing import Any

import torch
import torch.nn.functional as F

from fl_core.federated.aggregation import AggregationStrategy


class FLTrustDefense(AggregationStrategy):
    def __init__(self, device: torch.device = None):
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("FLTrustDefense")

    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        server_update: dict[str, torch.Tensor] | None = None,
        **kwargs,
    ) -> dict[str, torch.Tensor]:
        """Aggregate with FLTrust.

        Args:
            client_models: List of client model updates (deltas).
            server_update: Server-side update from root dataset. If None,
                           falls back to simple averaging.
        """
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        # If no server update provided, fall back to simple averaging
        if server_update is None:
            server_update = kwargs.get("server_update")
        if server_update is None:
            self.logger.warning("FLTrust: no server_update provided, falling back to FedAvg")
            return self._simple_average(client_models)

        n = len(client_models)
        param_keys = list(client_models[0].keys())

        # Flatten server update
        server_vec = torch.cat([server_update[k].to(self.device).float().flatten() for k in param_keys])
        server_norm = server_vec.norm()

        if server_norm < 1e-10:
            self.logger.warning("FLTrust: server update norm is near zero")
            return self._simple_average(client_models)

        # Compute trust scores and normalize
        trust_scores = []
        client_vecs = []
        for model in client_models:
            vec = torch.cat([model[k].to(self.device).float().flatten() for k in param_keys])
            client_vecs.append(vec)

            # Trust score = ReLU(cosine_similarity)
            cos_sim = F.cosine_similarity(vec.unsqueeze(0), server_vec.unsqueeze(0)).item()
            trust_scores.append(max(0.0, cos_sim))

        total_trust = sum(trust_scores)
        if total_trust < 1e-10:
            self.logger.warning("FLTrust: all trust scores are zero, using uniform weights")
            trust_scores = [1.0 / n] * n
            total_trust = 1.0

        # Normalize trust scores
        trust_scores = [s / total_trust for s in trust_scores]

        # Weighted aggregation with magnitude normalization
        aggregated = {k: torch.zeros_like(client_models[0][k], device=self.device).float() for k in param_keys}

        for i, model in enumerate(client_models):
            vec = client_vecs[i]
            vec_norm = vec.norm()
            # Normalize client update to have server update's norm
            if vec_norm > 1e-10:
                scale = server_norm / vec_norm
            else:
                scale = 0.0

            for k in param_keys:
                aggregated[k] += trust_scores[i] * scale * model[k].to(self.device).float()

        self.logger.info(
            f"FLTrust: trust scores = [{', '.join(f'{s:.3f}' for s in trust_scores[:5])}{'...' if n > 5 else ''}]"
        )
        return aggregated

    def _simple_average(self, client_models: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
        param_keys = client_models[0].keys()
        aggregated = {}
        for k in param_keys:
            params = torch.stack([m[k].to(self.device).float() for m in client_models])
            aggregated[k] = params.mean(dim=0)
        return aggregated

    def get_name(self) -> str:
        return "fltrust"


def create_fltrust_defense(config: dict[str, Any] = None, **kwargs) -> FLTrustDefense:
    return FLTrustDefense(device=kwargs.get("device"))
