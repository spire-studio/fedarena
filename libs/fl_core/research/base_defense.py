"""
Abstract base class for research defense (aggregation) strategies.

Subclasses set ``method_name`` and implement ``aggregate()``.  Because
``ResearchDefenseStrategy`` extends the existing ``AggregationStrategy`` ABC,
instances can be passed directly to ``AggregationFactory`` or
``FederatedServer`` — no adapter needed.

Example::

    from fl_core.research.base_defense import ResearchDefenseStrategy

    class MyDefense(ResearchDefenseStrategy):
        method_name = "claude_def1_v1"

        def aggregate(self, client_models, client_weights=None, **kw):
            # ... your aggregation logic ...
            return aggregated_params
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, ClassVar

import torch

from fl_core.federated.aggregation import AggregationStrategy

from . import registry

logger = logging.getLogger(__name__)


class ResearchDefenseStrategy(AggregationStrategy):
    """Base class for agent-designed robust aggregation defenses.

    Inherits from ``AggregationStrategy`` so it plugs directly into the
    existing FL pipeline.
    """

    method_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        name = getattr(cls, "method_name", None)
        if name is not None and name != getattr(cls.__bases__[0], "method_name", None):
            registry.register_defense(name, cls)
            logger.debug("Registered defense strategy: %s", name)

    # ------------------------------------------------------------------
    # Optional lifecycle hooks
    # ------------------------------------------------------------------

    def setup(self, config: dict[str, Any] | None = None) -> None:
        """Called once before the first round.  Override to parse config."""

    # ------------------------------------------------------------------
    # AggregationStrategy interface
    # ------------------------------------------------------------------

    @abstractmethod
    def aggregate(
        self,
        client_models: list[dict[str, torch.Tensor]],
        client_weights: list[float] | None = None,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        """Return aggregated model parameters.

        Parameters
        ----------
        client_models : list of dict
            Per-client model update dicts (may include poisoned updates).
        client_weights : list of float, optional
            Relative weight per client.

        Returns
        -------
        dict
            Aggregated model parameters.
        """
        ...

    def get_name(self) -> str:
        return self.method_name
