"""Baseline defense wrappers.

Wraps the existing aggregation defenses (Krum, Median, Trimmed Mean) from
``fl_core.defenses`` as ``ResearchDefenseStrategy`` subclasses so they appear
in the research registry and can be used as comparison baselines.
"""

from __future__ import annotations

from typing import Any

import torch

from fl_core.research.base_defense import ResearchDefenseStrategy


class BaselineKrumDefense(ResearchDefenseStrategy):
    """Baseline: Krum — select the client closest to majority."""

    method_name = "baseline_krum"

    def __init__(self, num_malicious: int = 1, device: torch.device | None = None):
        self.num_malicious = num_malicious
        self.device = device or torch.device("cpu")

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config and "num_malicious" in config:
            self.num_malicious = config["num_malicious"]

    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        from fl_core.defenses.krum import KrumDefense

        krum = KrumDefense(
            num_malicious=self.num_malicious,
            multi_krum=False,
            device=self.device,
        )
        return krum.aggregate(client_models, client_weights, **kwargs)


class BaselineMedianDefense(ResearchDefenseStrategy):
    """Baseline: coordinate-wise median aggregation."""

    method_name = "baseline_median"

    def __init__(self, device: torch.device | None = None):
        self.device = device or torch.device("cpu")

    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        from fl_core.defenses.median import MedianDefense

        median = MedianDefense(coordinate_wise=True, device=self.device)
        return median.aggregate(client_models, client_weights, **kwargs)


class BaselineTrimmedMeanDefense(ResearchDefenseStrategy):
    """Baseline: trimmed mean — discard top/bottom trim_ratio before averaging."""

    method_name = "baseline_trimmed_mean"

    def __init__(self, trim_ratio: float = 0.1, device: torch.device | None = None):
        self.trim_ratio = trim_ratio
        self.device = device or torch.device("cpu")

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config and "trim_ratio" in config:
            self.trim_ratio = config["trim_ratio"]

    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        from fl_core.defenses.median import MedianDefense

        defense = MedianDefense(
            trimmed_mean=True,
            trim_ratio=self.trim_ratio,
            device=self.device,
        )
        return defense.aggregate(client_models, client_weights, **kwargs)


class BaselineBulyanDefense(ResearchDefenseStrategy):
    """Baseline: Bulyan — iterative Krum selection + coordinate-wise trimmed mean."""

    method_name = "baseline_bulyan"

    def __init__(self, num_malicious: int = 1, device: torch.device | None = None):
        self.num_malicious = num_malicious
        self.device = device or torch.device("cpu")

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config and "num_malicious" in config:
            self.num_malicious = config["num_malicious"]

    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        from fl_core.defenses.bulyan import BulyanDefense

        defense = BulyanDefense(
            num_malicious=self.num_malicious,
            device=self.device,
        )
        return defense.aggregate(client_models, client_weights, **kwargs)


class BaselineCenteredClippingDefense(ResearchDefenseStrategy):
    """Baseline: Centered Clipping with momentum (Karimireddy et al., ICML 2021)."""

    method_name = "baseline_centered_clipping"

    def __init__(
        self,
        norm_threshold: float = 10.0,
        num_iters: int = 1,
        device: torch.device | None = None,
    ):
        self.norm_threshold = norm_threshold
        self.num_iters = num_iters
        self.device = device or torch.device("cpu")
        self._impl = None

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config:
            if "norm_threshold" in config:
                self.norm_threshold = config["norm_threshold"]
            if "num_iters" in config:
                self.num_iters = config["num_iters"]

    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        # Lazily construct and reuse across rounds so the momentum persists.
        if self._impl is None:
            from fl_core.defenses.centered_clipping import CenteredClippingDefense

            self._impl = CenteredClippingDefense(
                norm_threshold=self.norm_threshold,
                num_iters=self.num_iters,
                device=self.device,
            )
        return self._impl.aggregate(client_models, client_weights, **kwargs)


class BaselineDnCDefense(ResearchDefenseStrategy):
    """Baseline: Divide-and-Conquer SVD filtering (Shejwalkar & Houmansadr, NDSS 2021)."""

    method_name = "baseline_dnc"

    def __init__(
        self,
        num_malicious: int = 1,
        sub_dim: int = 10000,
        num_iters: int = 5,
        filter_frac: float = 1.0,
        device: torch.device | None = None,
    ):
        self.num_malicious = num_malicious
        self.sub_dim = sub_dim
        self.num_iters = num_iters
        self.filter_frac = filter_frac
        self.device = device or torch.device("cpu")

    def setup(self, config: dict[str, Any] | None = None) -> None:
        if config:
            for k in ("num_malicious", "sub_dim", "num_iters", "filter_frac"):
                if k in config:
                    setattr(self, k, config[k])

    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        from fl_core.defenses.dnc import DnCDefense

        defense = DnCDefense(
            num_malicious=self.num_malicious,
            sub_dim=self.sub_dim,
            num_iters=self.num_iters,
            filter_frac=self.filter_frac,
            device=self.device,
        )
        return defense.aggregate(client_models, client_weights, **kwargs)
