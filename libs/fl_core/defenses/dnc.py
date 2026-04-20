"""
DnC (Divide and Conquer) 防御算法实现
DnC defense: SVD-based outlier detection

Reference: Shejwalkar & Houmansadr, "Manipulating the Byzantine", NDSS 2021

Algorithm:
  For num_iters iterations:
    1. Subsample parameters for dimensionality reduction
    2. Center the subsampled updates (subtract mean)
    3. Compute top right singular vector via SVD
    4. Score each update by squared projection onto this vector
    5. Keep the n - filter_frac * f updates with smallest scores
  Take intersection of benign indices across iterations.
"""

import logging
from typing import Any

import torch

from fl_core.federated.aggregation import AggregationStrategy


class DnCDefense(AggregationStrategy):
    def __init__(
        self,
        num_malicious: int = 0,
        sub_dim: int = 10000,
        num_iters: int = 5,
        filter_frac: float = 1.0,
        device: torch.device = None,
    ):
        self.num_malicious = num_malicious
        self.sub_dim = sub_dim
        self.num_iters = num_iters
        self.filter_frac = filter_frac
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("DnCDefense")

    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        n = len(client_models)
        param_keys = list(client_models[0].keys())

        # Flatten all updates to vectors
        vectors = []
        for model in client_models:
            vec = torch.cat([model[k].to(self.device).float().flatten() for k in param_keys])
            vectors.append(vec)
        all_updates = torch.stack(vectors)  # [n, d]

        d = all_updates.shape[1]
        benign_sets = []

        for _ in range(self.num_iters):
            # Step 1: Subsample parameters
            if d > self.sub_dim:
                indices = torch.randperm(d, device=self.device)[: self.sub_dim]
                sub_updates = all_updates[:, indices]
            else:
                sub_updates = all_updates

            # Step 2: Center
            mean_update = sub_updates.mean(dim=0, keepdim=True)
            centered = sub_updates - mean_update

            # Step 3: Top right singular vector via SVD
            try:
                _, _, Vh = torch.linalg.svd(centered, full_matrices=False)
                top_v = Vh[0]  # Top right singular vector
            except Exception:
                # SVD failed, skip this iteration
                benign_sets.append(set(range(n)))
                continue

            # Step 4: Score by squared projection
            scores = (centered @ top_v).pow(2)

            # Step 5: Keep n - filter_frac * f with smallest scores
            num_keep = max(1, n - int(self.filter_frac * self.num_malicious))
            _, keep_indices = scores.topk(num_keep, largest=False)
            benign_sets.append(set(keep_indices.cpu().tolist()))

        # Intersection across iterations
        if benign_sets:
            benign_indices = benign_sets[0]
            for s in benign_sets[1:]:
                benign_indices = benign_indices & s
            benign_indices = sorted(benign_indices)
        else:
            benign_indices = list(range(n))

        if not benign_indices:
            benign_indices = list(range(n))
            self.logger.warning("DnC: intersection is empty, using all clients")

        # Average benign updates
        aggregated = {}
        for k in param_keys:
            params = torch.stack([client_models[i][k].to(self.device).float() for i in benign_indices])
            aggregated[k] = params.mean(dim=0)

        self.logger.info(f"DnC: kept {len(benign_indices)}/{n} clients after filtering")
        return aggregated

    def get_name(self) -> str:
        return "dnc"


def create_dnc_defense(config: dict[str, Any] = None, **kwargs) -> DnCDefense:
    num_malicious = 0
    sub_dim = 10000
    num_iters = 5
    filter_frac = 1.0
    if config is not None:
        defense_params = config.get("defense_params", {})
        num_malicious = defense_params.get("num_malicious", num_malicious)
        sub_dim = defense_params.get("sub_dim", sub_dim)
        num_iters = defense_params.get("num_iters", num_iters)
        filter_frac = defense_params.get("filter_frac", filter_frac)
    num_malicious = kwargs.get("num_malicious", num_malicious)
    return DnCDefense(
        num_malicious=num_malicious,
        sub_dim=sub_dim,
        num_iters=num_iters,
        filter_frac=filter_frac,
        device=kwargs.get("device"),
    )
