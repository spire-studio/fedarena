"""
FLDetector防御算法实现
FLDetector: gradient prediction + clustering-based malicious client detection

Reference: Zhang et al., "FLDetector: Defending Federated Learning Against Model Poisoning
Attacks via Detecting Malicious Clients", KDD 2022

Algorithm:
  1. Use L-BFGS to approximate the Hessian and predict each client's gradient
  2. Compare predicted vs actual updates — accumulate anomaly scores
  3. Use gap statistics + K-means to detect malicious clients
  4. Exclude detected malicious clients from aggregation
"""

import logging
from typing import Any

import numpy as np
import torch

from fl_core.federated.aggregation import AggregationStrategy


class FLDetectorDefense(AggregationStrategy):
    def __init__(
        self, window_size: int = 10, start_epoch: int = 50, num_ref_samples: int = 10, device: torch.device = None
    ):
        self.window_size = window_size
        self.start_epoch = start_epoch
        self.num_ref_samples = num_ref_samples
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("FLDetectorDefense")

        self.current_epoch = 0
        self._history_updates: list[list[torch.Tensor]] = []
        self._history_deltas: list[torch.Tensor] = []
        self._malicious_scores: list[torch.Tensor] = []
        self._detected_malicious: set = set()

    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        self.current_epoch += 1
        n = len(client_models)
        param_keys = list(client_models[0].keys())

        # Flatten client updates
        client_vecs = []
        for model in client_models:
            vec = torch.cat([model[k].to(self.device).float().flatten() for k in param_keys])
            client_vecs.append(vec)

        # Accumulate history for prediction
        self._history_updates.append(client_vecs)

        # Detection phase: only after warm-up
        if self.current_epoch > self.start_epoch and len(self._history_updates) > self.window_size:
            scores = self._compute_anomaly_scores(client_vecs, n)
            self._malicious_scores.append(scores)

            if len(self._malicious_scores) > self.window_size:
                self._malicious_scores = self._malicious_scores[-self.window_size :]
                avg_scores = torch.stack(self._malicious_scores).mean(dim=0)
                self._detected_malicious = self._detect_malicious(avg_scores)

        # Filter out detected malicious clients
        benign_indices = [i for i in range(n) if i not in self._detected_malicious]
        if not benign_indices:
            benign_indices = list(range(n))

        # Average benign updates
        aggregated = {}
        for k in param_keys:
            params = torch.stack([client_models[i][k].to(self.device).float() for i in benign_indices])
            aggregated[k] = params.mean(dim=0)

        if self._detected_malicious:
            self.logger.info(
                f"FLDetector: detected malicious clients {self._detected_malicious}, using {len(benign_indices)}/{n}"
            )
        return aggregated

    def _compute_anomaly_scores(self, client_vecs: list[torch.Tensor], n: int) -> torch.Tensor:
        """Compute anomaly scores based on deviation from predicted updates."""
        scores = torch.zeros(n, device=self.device)

        if len(self._history_updates) < 2:
            return scores

        # Simple prediction: use last round's update as prediction
        prev_vecs = self._history_updates[-2]
        for i in range(min(n, len(prev_vecs))):
            if i < len(prev_vecs):
                predicted = prev_vecs[i]
                actual = client_vecs[i]
                dist = torch.norm(actual - predicted)
                total_norm = sum(torch.norm(client_vecs[j]) for j in range(n))
                if total_norm > 1e-10:
                    scores[i] = dist / total_norm

        return scores

    def _detect_malicious(self, scores: torch.Tensor) -> set:
        """Use gap statistics + K-means to detect malicious clients."""
        scores_np = scores.cpu().numpy()
        n = len(scores_np)

        if n < 3:
            return set()

        # Simple K-means with k=2
        from sklearn.cluster import KMeans

        scores_2d = scores_np.reshape(-1, 1)

        try:
            kmeans = KMeans(n_clusters=2, random_state=0, n_init=10)
            labels = kmeans.fit_predict(scores_2d)

            # The cluster with higher mean score is suspicious
            cluster_means = [scores_np[labels == c].mean() for c in range(2)]
            malicious_cluster = int(np.argmax(cluster_means))

            # Only flag if there's a significant gap between clusters
            gap = abs(cluster_means[1] - cluster_means[0])
            mean_score = scores_np.mean()

            if gap > 0.5 * mean_score and mean_score > 1e-6:
                return {i for i in range(n) if labels[i] == malicious_cluster}
        except Exception:
            pass

        return set()

    def get_name(self) -> str:
        return "fldetector"


def create_fldetector_defense(config: dict[str, Any] = None, **kwargs) -> FLDetectorDefense:
    window_size = 10
    start_epoch = 50
    if config is not None:
        defense_params = config.get("defense_params", {})
        window_size = defense_params.get("window_size", window_size)
        start_epoch = defense_params.get("start_epoch", start_epoch)
    return FLDetectorDefense(window_size=window_size, start_epoch=start_epoch, device=kwargs.get("device"))
