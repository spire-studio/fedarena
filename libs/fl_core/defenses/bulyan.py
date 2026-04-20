"""
Bulyan防御算法实现
Bulyan defense: Krum selection + coordinate-wise trimmed mean

Reference: El Mhamdi et al., "The Hidden Vulnerability of Distributed Learning in Byzantium", ICML 2018

Algorithm:
1. Iteratively apply Krum to select theta = n - 2f candidates
2. For each coordinate, take the beta = theta - 2f closest-to-median values and average them
Requires: n >= 4f + 3
"""

import logging
from typing import Any

import torch

from fl_core.federated.aggregation import AggregationStrategy


class BulyanDefense(AggregationStrategy):
    def __init__(self, num_malicious: int = 0, device: torch.device = None):
        self.num_malicious = num_malicious
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("BulyanDefense")

    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        n = len(client_models)
        f = self.num_malicious

        if n < 4 * f + 3:
            self.logger.warning(f"Bulyan要求 n >= 4f+3 ({n} < {4 * f + 3})，退化为Krum选择+简单平均")

        # Phase 1: Krum iterative selection — select theta = n - 2f candidates
        theta = max(n - 2 * f, 1)
        selected_indices = self._krum_selection(client_models, theta)
        selected_models = [client_models[i] for i in selected_indices]

        # Phase 2: Coordinate-wise trimmed mean on selected set
        # beta = theta - 2f (number of values to keep per coordinate)
        beta = max(theta - 2 * f, 1)

        param_keys = selected_models[0].keys()
        aggregated = {}

        for key in param_keys:
            params = torch.stack([m[key].to(self.device).float() for m in selected_models])
            # For each coordinate, find the beta closest to median
            median_val = params.median(dim=0).values
            distances = (params - median_val.unsqueeze(0)).abs()

            if beta < len(selected_models):
                # Keep only the beta closest-to-median values per coordinate
                _, closest_idx = distances.topk(beta, dim=0, largest=False)
                # Gather the closest values and average
                gathered = params.gather(0, closest_idx)
                aggregated[key] = gathered.mean(dim=0)
            else:
                aggregated[key] = params.mean(dim=0)

        self.logger.info(f"Bulyan: selected {theta} candidates, kept {beta} per coordinate")
        return aggregated

    def _krum_selection(self, client_models: list[dict[str, torch.Tensor]], num_select: int) -> list[int]:
        """Iteratively apply Krum to select num_select candidates."""
        # Flatten all models to vectors
        vectors = []
        for model in client_models:
            vec = torch.cat([p.flatten().to(self.device).float() for p in model.values()])
            vectors.append(vec)
        vectors = torch.stack(vectors)

        n = len(vectors)
        remaining = list(range(n))
        selected = []

        for _ in range(num_select):
            if len(remaining) <= 1:
                selected.extend(remaining)
                break

            # Compute pairwise distances among remaining
            rem_vecs = vectors[remaining]
            num_rem = len(rem_vecs)
            num_neighbors = max(num_rem - self.num_malicious - 2, 1)

            dists = torch.cdist(rem_vecs.unsqueeze(0), rem_vecs.unsqueeze(0)).squeeze(0)

            scores = []
            for i in range(num_rem):
                d = dists[i].clone()
                d[i] = float("inf")  # exclude self
                topk = d.topk(min(num_neighbors, num_rem - 1), largest=False).values
                scores.append(topk.pow(2).sum().item())

            best_local = int(min(range(num_rem), key=lambda i: scores[i]))
            selected.append(remaining[best_local])
            remaining.pop(best_local)

        return selected

    def get_name(self) -> str:
        return "bulyan"


def create_bulyan_defense(config: dict[str, Any] = None, **kwargs) -> BulyanDefense:
    num_malicious = 0
    if config is not None:
        defense_params = config.get("defense_params", {})
        num_malicious = defense_params.get("num_malicious", num_malicious)
    num_malicious = kwargs.get("num_malicious", num_malicious)
    return BulyanDefense(num_malicious=num_malicious, device=kwargs.get("device"))
