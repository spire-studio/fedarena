import logging
from abc import ABC, abstractmethod
from typing import Any

import torch


class AggregationStrategy(ABC):
    @abstractmethod
    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class FedAvgAggregation(AggregationStrategy):
    def __init__(self, device: torch.device = None):
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("FedAvgAggregation")

    def aggregate(
        self, client_models: list[dict[str, torch.Tensor]], client_weights: list[float] | None = None, **kwargs
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        num_clients = len(client_models)

        if client_weights is None:
            client_weights = [1.0 / num_clients] * num_clients

        total_weight = sum(client_weights)
        if total_weight > 0:
            client_weights = [w / total_weight for w in client_weights]
        else:
            client_weights = [1.0 / num_clients] * num_clients

        if len(client_weights) != num_clients:
            raise ValueError(f"权重数量 ({len(client_weights)}) 与客户端数量 ({num_clients}) 不匹配")

        self.logger.debug(f"开始FedAvg聚合，客户端数量: {num_clients}")

        param_keys = client_models[0].keys()

        aggregated_params = {}

        for param_name in param_keys:
            client_params = [model[param_name] for model in client_models]

            weighted_param = torch.zeros_like(client_params[0], device=self.device)
            for param, weight in zip(client_params, client_weights):
                weighted_param += param.to(self.device) * weight

            aggregated_params[param_name] = weighted_param

        self.logger.debug("FedAvg聚合完成")

        return aggregated_params

    def get_name(self) -> str:
        return "fedavg"


class WeightedAggregation(AggregationStrategy):
    def __init__(self, device: torch.device = None):
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger = logging.getLogger("WeightedAggregation")

    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        client_info: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> dict[str, torch.Tensor]:
        if not client_models:
            raise ValueError("客户端模型列表不能为空")

        num_clients = len(client_models)

        if client_weights is None and client_info is not None:
            client_weights = [info.get("samples", 1) for info in client_info]
            total_samples = sum(client_weights)
            if total_samples > 0:
                client_weights = [w / total_samples for w in client_weights]
            else:
                client_weights = [1.0 / num_clients] * num_clients
        elif client_weights is None:
            client_weights = [1.0 / num_clients] * num_clients

        self.logger.debug(f"开始加权聚合，客户端数量: {num_clients}")

        # 使用FedAvg的聚合逻辑
        fedavg_aggregator = FedAvgAggregation(self.device)
        return fedavg_aggregator.aggregate(client_models, client_weights)

    def get_name(self) -> str:
        return "weighted_avg"


class AggregationFactory:
    _strategies = {
        "fedavg": FedAvgAggregation,
        "weighted_avg": WeightedAggregation,
        "simple_avg": FedAvgAggregation,
    }

    _defense_strategies = {}

    @classmethod
    def create_aggregator(
        cls, strategy_name: str, device: torch.device = None, config: dict[str, Any] | None = None, **kwargs
    ) -> AggregationStrategy:
        strategy_name = strategy_name.lower()

        if strategy_name in cls._defense_strategies:
            strategy_class = cls._defense_strategies[strategy_name]

            if strategy_name in ["krum", "multi_krum"]:
                from fl_core.defenses.krum import create_krum_defense

                if strategy_name == "multi_krum":
                    kwargs["multi_krum"] = True

                if config and "defense_params" in config:
                    defense_params = config["defense_params"]
                    kwargs.update(defense_params)

                return create_krum_defense(config=config, device=device, **kwargs)

            elif strategy_name in ["median", "coordinate_median", "client_median", "trimmed_mean"]:
                from fl_core.defenses.median import create_median_defense

                if strategy_name == "coordinate_median":
                    kwargs["coordinate_wise"] = True
                elif strategy_name == "client_median":
                    kwargs["coordinate_wise"] = False
                elif strategy_name == "trimmed_mean":
                    kwargs["trimmed_mean"] = True

                if config and "defense_params" in config:
                    defense_params = config["defense_params"]
                    kwargs.update(defense_params)

                return create_median_defense(config=config, device=device, **kwargs)

            elif strategy_name == "bulyan":
                from fl_core.defenses.bulyan import create_bulyan_defense

                if config and "defense_params" in config:
                    kwargs.update(config["defense_params"])
                return create_bulyan_defense(config=config, device=device, **kwargs)

            elif strategy_name == "centered_clipping":
                from fl_core.defenses.centered_clipping import create_centered_clipping_defense

                if config and "defense_params" in config:
                    kwargs.update(config["defense_params"])
                return create_centered_clipping_defense(config=config, device=device, **kwargs)

            elif strategy_name == "dnc":
                from fl_core.defenses.dnc import create_dnc_defense

                if config and "defense_params" in config:
                    kwargs.update(config["defense_params"])
                return create_dnc_defense(config=config, device=device, **kwargs)

            elif strategy_name == "fltrust":
                from fl_core.defenses.fltrust import create_fltrust_defense

                return create_fltrust_defense(config=config, device=device, **kwargs)

            elif strategy_name == "fldetector":
                from fl_core.defenses.fldetector import create_fldetector_defense

                if config and "defense_params" in config:
                    kwargs.update(config["defense_params"])
                return create_fldetector_defense(config=config, device=device, **kwargs)

            elif strategy_name == "simple_clustering":
                from fl_core.defenses.simple_clustering import create_simple_clustering_defense

                if config and "defense_params" in config:
                    kwargs.update(config["defense_params"])
                return create_simple_clustering_defense(config=config, device=device, **kwargs)

            else:
                return strategy_class(device=device, **kwargs)

        if strategy_name not in cls._strategies:
            all_strategies = list(cls._strategies.keys()) + list(cls._defense_strategies.keys())
            raise ValueError(f"不支持的聚合策略: {strategy_name}. 支持的策略: {all_strategies}")

        strategy_class = cls._strategies[strategy_name]
        return strategy_class(device=device, **kwargs)

    @classmethod
    def get_supported_strategies(cls) -> list[str]:
        return list(cls._strategies.keys()) + list(cls._defense_strategies.keys())

    @classmethod
    def register_strategy(cls, name: str, strategy_class: type) -> None:
        if not issubclass(strategy_class, AggregationStrategy):
            raise ValueError("策略类必须继承自AggregationStrategy")

        cls._strategies[name.lower()] = strategy_class

    @classmethod
    def register_defense_strategy(cls, name: str, strategy_class: type) -> None:
        if not issubclass(strategy_class, AggregationStrategy):
            raise ValueError("防御策略类必须继承自AggregationStrategy")

        cls._defense_strategies[name.lower()] = strategy_class


def create_aggregator(
    strategy_name: str, device: torch.device = None, config: dict[str, Any] | None = None, **kwargs
) -> AggregationStrategy:
    return AggregationFactory.create_aggregator(strategy_name, device, config, **kwargs)


def get_supported_aggregation_methods() -> list[str]:
    return AggregationFactory.get_supported_strategies()


def register_defense_strategies():
    try:
        from fl_core.defenses.krum import KrumDefense

        AggregationFactory.register_defense_strategy("krum", KrumDefense)
        AggregationFactory.register_defense_strategy("multi_krum", KrumDefense)
    except ImportError as e:
        logging.getLogger("AggregationFactory").warning(f"无法导入Krum防御策略: {e}")

    try:
        from fl_core.defenses.median import MedianDefense

        AggregationFactory.register_defense_strategy("median", MedianDefense)
        AggregationFactory.register_defense_strategy("coordinate_median", MedianDefense)
        AggregationFactory.register_defense_strategy("client_median", MedianDefense)
        AggregationFactory.register_defense_strategy("trimmed_mean", MedianDefense)
    except ImportError as e:
        logging.getLogger("AggregationFactory").warning(f"无法导入中位数防御策略: {e}")

    try:
        from fl_core.defenses.bulyan import BulyanDefense

        AggregationFactory.register_defense_strategy("bulyan", BulyanDefense)
    except ImportError as e:
        logging.getLogger("AggregationFactory").warning(f"无法导入Bulyan防御策略: {e}")

    try:
        from fl_core.defenses.centered_clipping import CenteredClippingDefense

        AggregationFactory.register_defense_strategy("centered_clipping", CenteredClippingDefense)
    except ImportError as e:
        logging.getLogger("AggregationFactory").warning(f"无法导入CenteredClipping防御策略: {e}")

    try:
        from fl_core.defenses.dnc import DnCDefense

        AggregationFactory.register_defense_strategy("dnc", DnCDefense)
    except ImportError as e:
        logging.getLogger("AggregationFactory").warning(f"无法导入DnC防御策略: {e}")

    try:
        from fl_core.defenses.fltrust import FLTrustDefense

        AggregationFactory.register_defense_strategy("fltrust", FLTrustDefense)
    except ImportError as e:
        logging.getLogger("AggregationFactory").warning(f"无法导入FLTrust防御策略: {e}")

    try:
        from fl_core.defenses.fldetector import FLDetectorDefense

        AggregationFactory.register_defense_strategy("fldetector", FLDetectorDefense)
    except ImportError as e:
        logging.getLogger("AggregationFactory").warning(f"无法导入FLDetector防御策略: {e}")

    try:
        from fl_core.defenses.simple_clustering import SimpleClusteringDefense

        AggregationFactory.register_defense_strategy("simple_clustering", SimpleClusteringDefense)
    except ImportError as e:
        logging.getLogger("AggregationFactory").warning(f"无法导入SimpleClustering防御策略: {e}")


register_defense_strategies()
