import logging
from typing import Any

import torch

from fl_core.federated.aggregation import AggregationStrategy


class MedianDefense(AggregationStrategy):
    def __init__(
        self,
        trimmed_mean: bool = False,
        trim_ratio: float = 0.1,
        coordinate_wise: bool = True,
        device: torch.device = None,
    ):
        self.trimmed_mean = trimmed_mean
        self.trim_ratio = trim_ratio
        self.coordinate_wise = coordinate_wise
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("MedianDefense")

        if not isinstance(trimmed_mean, bool):
            raise ValueError("trimmed_mean 必须是布尔值")

        if not (0.0 <= trim_ratio <= 0.5):
            raise ValueError("trim_ratio 必须在 [0.0, 0.5] 范围内")

        if not isinstance(coordinate_wise, bool):
            raise ValueError("coordinate_wise 必须是布尔值")

    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        num_clients = len(client_models)

        if num_clients < 3:
            self.logger.warning(f"客户端数量 ({num_clients}) 较少，中位数防御效果可能不佳")

        self.logger.debug(f"开始中位数防御聚合，客户端数量: {num_clients}")

        if self.coordinate_wise:
            aggregated_params = self._coordinate_wise_median(client_models)
        else:
            aggregated_params = self._client_wise_median(client_models)

        self.logger.debug("中位数防御聚合完成")

        return aggregated_params

    def _coordinate_wise_median(self, client_models: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
        aggregated_params = {}
        param_keys = client_models[0].keys()

        for param_name in param_keys:
            client_params = [model[param_name].to(self.device) for model in client_models]

            stacked_params = torch.stack(client_params, dim=0)

            if self.trimmed_mean:
                aggregated_param = self._compute_trimmed_mean(stacked_params)
            else:
                aggregated_param = self._compute_median(stacked_params)

            aggregated_params[param_name] = aggregated_param

        return aggregated_params

    def _client_wise_median(self, client_models: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
        num_clients = len(client_models)

        distance_matrix = self._compute_distance_matrix(client_models)

        distance_sums = torch.sum(distance_matrix, dim=1)

        median_idx = torch.argsort(distance_sums)[num_clients // 2].item()

        self.logger.info(f"选择客户端 {median_idx} 作为中位数客户端")

        return {k: v.clone().to(self.device) for k, v in client_models[median_idx].items()}

    def _compute_median(self, stacked_params: torch.Tensor) -> torch.Tensor:
        median_values, _ = torch.median(stacked_params, dim=0)
        return median_values

    def _compute_trimmed_mean(self, stacked_params: torch.Tensor) -> torch.Tensor:
        num_clients = stacked_params.shape[0]

        num_trim = int(num_clients * self.trim_ratio)

        if num_trim == 0:
            return torch.mean(stacked_params, dim=0)

        sorted_params, _ = torch.sort(stacked_params, dim=0)

        if num_trim * 2 >= num_clients:
            start_idx = num_clients // 4
            end_idx = num_clients - num_clients // 4
        else:
            start_idx = num_trim
            end_idx = num_clients - num_trim

        trimmed_params = sorted_params[start_idx:end_idx]

        return torch.mean(trimmed_params, dim=0)

    def _compute_distance_matrix(self, client_models: list[dict[str, torch.Tensor]]) -> torch.Tensor:
        num_clients = len(client_models)
        distance_matrix = torch.zeros(num_clients, num_clients, device=self.device)

        client_vectors = []
        for model in client_models:
            param_vector = torch.cat([param.flatten() for param in model.values()])
            client_vectors.append(param_vector.to(self.device))

        for i in range(num_clients):
            for j in range(i + 1, num_clients):
                distance = torch.norm(client_vectors[i] - client_vectors[j], p=2)
                distance_matrix[i, j] = distance
                distance_matrix[j, i] = distance

        return distance_matrix

    def get_name(self) -> str:
        if self.trimmed_mean:
            return "trimmed_mean"
        elif self.coordinate_wise:
            return "coordinate_median"
        else:
            return "client_median"


def create_median_defense(config: dict[str, Any] = None, **kwargs) -> MedianDefense:

    trimmed_mean = False
    trim_ratio = 0.1
    coordinate_wise = True

    if config is not None:
        defense_params = config.get("defense_params", {})
        trimmed_mean = defense_params.get("trimmed_mean", trimmed_mean)
        trim_ratio = defense_params.get("trim_ratio", trim_ratio)
        coordinate_wise = defense_params.get("coordinate_wise", coordinate_wise)

    trimmed_mean = kwargs.get("trimmed_mean", trimmed_mean)
    trim_ratio = kwargs.get("trim_ratio", trim_ratio)
    coordinate_wise = kwargs.get("coordinate_wise", coordinate_wise)

    if not isinstance(trimmed_mean, bool):
        raise ValueError(f"trimmed_mean 必须是布尔值，得到: {trimmed_mean}")

    if not isinstance(coordinate_wise, bool):
        raise ValueError(f"coordinate_wise 必须是布尔值，得到: {coordinate_wise}")

    if not (0.0 <= trim_ratio <= 0.5):
        raise ValueError(f"trim_ratio 必须在 [0.0, 0.5] 范围内，得到: {trim_ratio}")

    return MedianDefense(
        trimmed_mean=trimmed_mean, trim_ratio=trim_ratio, coordinate_wise=coordinate_wise, device=kwargs.get("device")
    )
