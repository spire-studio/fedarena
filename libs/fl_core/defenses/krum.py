"""
Krum防御算法实现
Krum defense algorithm implementation for federated learning
"""

import logging
from typing import Any

import torch

from fl_core.federated.aggregation import AggregationStrategy


class KrumDefense(AggregationStrategy):
    def __init__(self, num_malicious: int = 0, multi_krum: bool = False, device: torch.device = None):
        self.num_malicious = num_malicious
        self.multi_krum = multi_krum
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("KrumDefense")

        # 验证参数
        if self.num_malicious < 0:
            raise ValueError("恶意客户端数量不能为负数")

    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        num_clients = len(client_models)

        if num_clients <= 2 * self.num_malicious:
            raise ValueError(f"客户端数量 ({num_clients}) 必须大于 2 * 恶意客户端数量 ({2 * self.num_malicious})")

        self.logger.debug(f"开始Krum防御聚合，客户端数量: {num_clients}, 预期恶意客户端: {self.num_malicious}")

        distance_matrix = self._compute_distance_matrix(client_models)

        krum_scores = self._compute_krum_scores(distance_matrix, num_clients)

        selected_clients = self._select_clients(krum_scores, num_clients)

        if self.multi_krum and len(selected_clients) > 1:
            selected_models = [client_models[i] for i in selected_clients]
            aggregated_params = self._average_models(selected_models)
            self.logger.info(f"Multi-Krum选择了 {len(selected_clients)} 个客户端进行聚合")
        else:
            best_client_idx = selected_clients[0]
            aggregated_params = {k: v.clone().to(self.device) for k, v in client_models[best_client_idx].items()}
            self.logger.info(f"Krum选择了客户端 {best_client_idx} 作为全局模型")

        self.logger.debug("Krum防御聚合完成")

        return aggregated_params

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

    def _compute_krum_scores(self, distance_matrix: torch.Tensor, num_clients: int) -> list[float]:
        krum_scores = []

        num_neighbors = num_clients - self.num_malicious - 2

        if num_neighbors <= 0:
            raise ValueError(f"无法计算Krum分数：需要的邻居数量 ({num_neighbors}) <= 0")

        for i in range(num_clients):
            distances_to_i = distance_matrix[i]

            distances_to_others = torch.cat([distances_to_i[:i], distances_to_i[i + 1 :]])

            closest_distances, _ = torch.topk(
                distances_to_others, min(num_neighbors, len(distances_to_others)), largest=False
            )

            krum_score = torch.sum(closest_distances**2).item()
            krum_scores.append(krum_score)

        return krum_scores

    def _select_clients(self, krum_scores: list[float], num_clients: int) -> list[int]:
        score_index_pairs = [(score, idx) for idx, score in enumerate(krum_scores)]
        score_index_pairs.sort(key=lambda x: x[0])

        if self.multi_krum:
            num_selected = max(1, num_clients - self.num_malicious)
            selected_clients = [idx for _, idx in score_index_pairs[:num_selected]]
        else:
            selected_clients = [score_index_pairs[0][1]]

        self.logger.debug(f"Krum分数: {krum_scores}")
        self.logger.debug(f"选中的客户端: {selected_clients}")

        return selected_clients

    def _average_models(self, models: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
        if not models:
            raise ValueError("模型列表不能为空")

        num_models = len(models)
        param_keys = models[0].keys()

        for i, model in enumerate(models[1:], 1):
            if set(model.keys()) != set(param_keys):
                raise ValueError(f"模型 {i} 的参数键与模型 0 不匹配")

        averaged_params = {}

        for param_name in param_keys:
            params = [model[param_name] for model in models]

            param_shape = params[0].shape
            for i, param in enumerate(params[1:], 1):
                if param.shape != param_shape:
                    raise ValueError(f"模型 {i} 的参数 {param_name} 形状与模型 0 不匹配")

            averaged_param = torch.zeros_like(params[0], device=self.device)
            for param in params:
                averaged_param += param.to(self.device)
            averaged_param /= num_models

            averaged_params[param_name] = averaged_param

        return averaged_params

    def get_name(self) -> str:
        return "krum" if not self.multi_krum else "multi_krum"


def create_krum_defense(config: dict[str, Any] = None, **kwargs) -> KrumDefense:
    num_malicious = 0
    multi_krum = False

    if config is not None:
        defense_params = config.get("defense_params", {})
        num_malicious = defense_params.get("num_malicious", num_malicious)
        multi_krum = defense_params.get("multi_krum", multi_krum)

    num_malicious = kwargs.get("num_malicious", num_malicious)
    multi_krum = kwargs.get("multi_krum", multi_krum)

    if not isinstance(num_malicious, int) or num_malicious < 0:
        raise ValueError(f"num_malicious 必须是非负整数，得到: {num_malicious}")

    if not isinstance(multi_krum, bool):
        raise ValueError(f"multi_krum 必须是布尔值，得到: {multi_krum}")

    return KrumDefense(num_malicious=num_malicious, multi_krum=multi_krum, device=kwargs.get("device"))
