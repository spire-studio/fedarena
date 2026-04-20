"""
SimpleClustering防御算法实现
Clustering-based defense using DBSCAN or MeanShift

Clusters client updates and selects the largest cluster as benign.
"""

import logging
from typing import Any

import numpy as np
import torch

from fl_core.federated.aggregation import AggregationStrategy


class SimpleClusteringDefense(AggregationStrategy):
    def __init__(
        self, clustering_method: str = "dbscan", eps: float = 0.5, min_samples: int = 2, device: torch.device = None
    ):
        self.clustering_method = clustering_method
        self.eps = eps
        self.min_samples = min_samples
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("SimpleClusteringDefense")

    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        n = len(client_models)
        if n <= 2:
            return self._simple_average(client_models, list(range(n)))

        param_keys = list(client_models[0].keys())

        # Flatten updates to vectors
        vectors = []
        for model in client_models:
            vec = torch.cat([model[k].to(self.device).float().flatten() for k in param_keys])
            vectors.append(vec.cpu().numpy())
        X = np.array(vectors)

        # Cluster
        labels = self._cluster(X)

        # Find largest cluster
        unique_labels = set(labels)
        unique_labels.discard(-1)  # Exclude noise for DBSCAN

        if not unique_labels:
            self.logger.warning("SimpleClustering: no clusters found, using all clients")
            benign_indices = list(range(n))
        else:
            cluster_sizes = {label: np.sum(labels == label) for label in unique_labels}
            largest_cluster = max(cluster_sizes, key=cluster_sizes.get)
            benign_indices = [i for i in range(n) if labels[i] == largest_cluster]

        if not benign_indices:
            benign_indices = list(range(n))

        aggregated = self._simple_average(client_models, benign_indices)
        self.logger.info(
            f"SimpleClustering ({self.clustering_method}): kept {len(benign_indices)}/{n} clients from largest cluster"
        )
        return aggregated

    def _cluster(self, X: np.ndarray) -> np.ndarray:
        if self.clustering_method == "dbscan":
            from sklearn.cluster import DBSCAN

            clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples)
            return clustering.fit_predict(X)
        elif self.clustering_method == "meanshift":
            from sklearn.cluster import MeanShift, estimate_bandwidth

            bandwidth = estimate_bandwidth(X, quantile=0.5)
            if bandwidth <= 0:
                bandwidth = 1.0
            clustering = MeanShift(bandwidth=bandwidth)
            return clustering.fit_predict(X)
        else:
            raise ValueError(f"Unknown clustering method: {self.clustering_method}")

    def _simple_average(
        self, client_models: list[dict[str, torch.Tensor]], indices: list[int]
    ) -> dict[str, torch.Tensor]:
        param_keys = client_models[0].keys()
        aggregated = {}
        for k in param_keys:
            params = torch.stack([client_models[i][k].to(self.device).float() for i in indices])
            aggregated[k] = params.mean(dim=0)
        return aggregated

    def get_name(self) -> str:
        return "simple_clustering"


def create_simple_clustering_defense(config: dict[str, Any] = None, **kwargs) -> SimpleClusteringDefense:
    clustering_method = "dbscan"
    eps = 0.5
    min_samples = 2
    if config is not None:
        defense_params = config.get("defense_params", {})
        clustering_method = defense_params.get("clustering_method", clustering_method)
        eps = defense_params.get("eps", eps)
        min_samples = defense_params.get("min_samples", min_samples)
    return SimpleClusteringDefense(
        clustering_method=clustering_method, eps=eps, min_samples=min_samples, device=kwargs.get("device")
    )
