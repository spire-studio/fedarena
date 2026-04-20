import copy
import logging
from typing import Any

import numpy as np
import torch


class ModelPoisonAttack:
    def __init__(self, attack_config: dict[str, Any]):
        self.attack_config = attack_config
        self.attack_type = attack_config.get("attack_type", "gaussian")
        self.attack_params = attack_config.get("attack_params", {})
        self.malicious_clients = attack_config.get("malicious_clients", [])

        # 验证攻击参数
        self._validate_attack_params()

        self.logger = logging.getLogger(__name__)

    def _validate_attack_params(self):
        if self.attack_type == "gaussian":
            noise_scale = self.attack_params.get("noise_scale", 0.1)
            if noise_scale < 0:
                raise ValueError(f"noise_scale must be non-negative, got {noise_scale}")

        elif self.attack_type == "scaling":
            scale_factor = self.attack_params.get("scale_factor", 10)
            if scale_factor <= 0:
                raise ValueError(f"scale_factor must be positive, got {scale_factor}")

        elif self.attack_type == "ipm":
            pass

        if not isinstance(self.malicious_clients, list):
            raise ValueError("malicious_clients must be a list")

        for client_id in self.malicious_clients:
            if not isinstance(client_id, int) or client_id < 0:
                raise ValueError(f"Invalid malicious client ID: {client_id}")

    def is_malicious_client(self, client_id: int) -> bool:
        return client_id in self.malicious_clients

    def _dict_to_tensor_dict(self, param_dict: dict[str, Any]) -> dict[str, torch.Tensor]:
        tensor_dict = {}
        for key, value in param_dict.items():
            if isinstance(value, torch.Tensor):
                tensor_dict[key] = value
            elif isinstance(value, np.ndarray):
                tensor_dict[key] = torch.from_numpy(value)
            else:
                tensor_dict[key] = torch.tensor(value)
        return tensor_dict

    def _tensor_dict_to_dict(self, tensor_dict: dict[str, torch.Tensor]) -> dict[str, Any]:
        result_dict = {}
        for key, value in tensor_dict.items():
            if isinstance(value, torch.Tensor):
                result_dict[key] = value.detach().clone()
            else:
                result_dict[key] = value
        return result_dict

    def gaussian_noise(self, model_params: dict[str, Any], noise_scale: float | None = None) -> dict[str, Any]:
        if noise_scale is None:
            noise_scale = self.attack_params.get("noise_scale", 0.1)

        if noise_scale < 0:
            raise ValueError(f"noise_scale must be non-negative, got {noise_scale}")

        tensor_params = self._dict_to_tensor_dict(model_params)
        poisoned_params = {}

        for key, param in tensor_params.items():
            noise = torch.randn_like(param) * noise_scale
            poisoned_params[key] = param + noise

        self.logger.info(f"Gaussian noise attack: added noise (scale={noise_scale:.4f}) ")

        return self._tensor_dict_to_dict(poisoned_params)

    def scaling_attack(self, model_params: dict[str, Any], scale_factor: float | None = None) -> dict[str, Any]:
        if scale_factor is None:
            scale_factor = self.attack_params.get("scale_factor", 10)

        if scale_factor <= 0:
            raise ValueError(f"scale_factor must be positive, got {scale_factor}")

        tensor_params = self._dict_to_tensor_dict(model_params)
        poisoned_params = {}

        total_params = 0
        for key, param in tensor_params.items():
            poisoned_params[key] = param * scale_factor
            total_params += param.numel()

        self.logger.info(
            f"Scaling attack: scaled {len(poisoned_params)} parameter tensors "
            f"by factor {scale_factor} ({total_params} total parameters)"
        )

        return self._tensor_dict_to_dict(poisoned_params)

    def sign_flipping(
        self, model_params: dict[str, Any], target_params: dict[str, Any], scale_factor: float | None = None
    ) -> dict[str, Any]:
        """Sign-flipping attack: reverse the sign of the model update.

        Reference: Damaskinos et al., "Asynchronous Byzantine Machine Learning", ICML 2018

        Formula: poisoned = global - scale * (local - global) = (1+scale)*global - scale*local
        When scale=1 (default): poisoned = 2*global - local (simple sign flip of the update)
        """
        if scale_factor is None:
            scale_factor = self.attack_params.get("scale_factor", 1.0)

        current_params = self._dict_to_tensor_dict(model_params)
        target_tensor_params = self._dict_to_tensor_dict(target_params)
        poisoned_params = {}

        for key in current_params:
            local_v = current_params[key]
            global_v = target_tensor_params.get(key, local_v).to(local_v.device)
            if local_v.shape == global_v.shape:
                update = local_v - global_v
                poisoned_params[key] = global_v - scale_factor * update
            else:
                poisoned_params[key] = local_v

        self.logger.info(f"Sign-flipping attack: scale_factor={scale_factor:.2f}")
        return self._tensor_dict_to_dict(poisoned_params)

    def alie_attack(
        self,
        model_params: dict[str, Any],
        target_params: dict[str, Any],
        all_client_models: list[dict[str, Any]] | None = None,
        z_max: float | None = None,
        num_clients: int | None = None,
        num_adv: int | None = None,
    ) -> dict[str, Any]:
        """A Little Is Enough (ALIE) attack.

        Reference: Baruch et al., "A Little Is Enough", NeurIPS 2019

        Crafts a poisoned update as mean + z_max * std of benign updates.
        The z-score is computed from the inverse CDF of the normal distribution
        so that the poisoned update is just barely enough to shift the aggregated
        result past the honest majority.

        When all_client_models is available (omniscient mode): uses actual benign
        updates to compute mean/std.
        When unavailable: uses local update as a proxy (non-omniscient fallback).
        """
        from scipy.stats import norm as normal_dist

        if z_max is None:
            z_max = self.attack_params.get("z_max", None)
        if num_clients is None:
            num_clients = self.attack_params.get("num_clients", 10)
        if num_adv is None:
            num_adv = self.attack_params.get("num_adv", 3)

        current_params = self._dict_to_tensor_dict(model_params)
        target_tensor_params = self._dict_to_tensor_dict(target_params)

        # Compute z_max from attacker/client ratio if not provided
        if z_max is None:
            s = int(np.floor(num_clients / 2 + 1)) - num_adv
            n_benign = num_clients - num_adv
            if n_benign > 0 and s > 0:
                cdf_value = (n_benign - s) / n_benign
                cdf_value = max(0.0001, min(0.9999, cdf_value))
                z_max = normal_dist.ppf(cdf_value)
            else:
                z_max = 1.0

        poisoned_params = {}

        if all_client_models and len(all_client_models) > 1:
            # Omniscient mode: compute mean/std from all client updates
            for key in current_params:
                local_v = current_params[key]
                global_v = target_tensor_params.get(key, local_v).to(local_v.device)

                updates = []
                for cm in all_client_models:
                    if key in cm:
                        cv = cm[key]
                        if isinstance(cv, torch.Tensor):
                            cv = cv.to(local_v.device)
                        else:
                            cv = torch.tensor(cv, device=local_v.device)
                        if cv.shape == global_v.shape:
                            updates.append(cv - global_v)

                if len(updates) > 1:
                    stacked = torch.stack(updates)
                    mean_update = stacked.mean(dim=0)
                    std_update = stacked.std(dim=0)
                    poisoned_params[key] = global_v + mean_update + z_max * std_update
                else:
                    poisoned_params[key] = local_v
        else:
            # Non-omniscient fallback: use local update with z_max scaling
            for key in current_params:
                local_v = current_params[key]
                global_v = target_tensor_params.get(key, local_v).to(local_v.device)
                if local_v.shape == global_v.shape:
                    update = local_v - global_v
                    poisoned_params[key] = global_v + (1.0 + z_max) * update
                else:
                    poisoned_params[key] = local_v

        self.logger.info(f"ALIE attack: z_max={z_max:.4f}")
        return self._tensor_dict_to_dict(poisoned_params)

    def ipm_attack(
        self, model_params: dict[str, Any], target_params: dict[str, Any], attack_strength: float | None = None
    ) -> dict[str, Any]:
        if attack_strength is None:
            attack_strength = self.attack_params.get("attack_strength", 1.0)

        if attack_strength < 0:
            raise ValueError(f"attack_strength must be non-negative, got {attack_strength}")

        current_params = self._dict_to_tensor_dict(model_params)
        target_tensor_params = self._dict_to_tensor_dict(target_params)

        common_keys = set(current_params.keys()) & set(target_tensor_params.keys())
        if not common_keys:
            self.logger.warning("IPM攻击失败：本地模型与目标模型无公共键")
            return model_params

        poisoned_params = copy.deepcopy(current_params)
        total_params = 0

        for key in common_keys:
            current_param = current_params[key]
            target_param = target_tensor_params[key].to(current_param.device)

            if current_param.shape != target_param.shape:
                raise ValueError(f"Parameter {key} shape mismatch: {current_param.shape} vs {target_param.shape}")

            direction = target_param - current_param
            poisoned_params[key] = current_param + attack_strength * direction
            total_params += current_param.numel()

        self.logger.info(
            f"IPM attack: manipulated {len(poisoned_params)} parameter tensors "
            f"with strength {attack_strength} ({total_params} total parameters)"
        )

        return self._tensor_dict_to_dict(poisoned_params)

    def apply_attack(
        self,
        client_id: int,
        model_params: dict[str, Any],
        target_params: dict[str, Any] | None = None,
        override_type: str | None = None,
        override_params: dict | None = None,
    ) -> dict[str, Any]:

        if not self.is_malicious_client(client_id):
            return model_params

        # 确定本次使用的攻击策略
        attack_type = override_type if override_type else self.attack_type
        params = override_params if override_params else self.attack_params

        self.logger.info(f"客户端 {client_id} 模型投毒类型: {attack_type}")

        if attack_type == "gaussian":
            return self.gaussian_noise(model_params, noise_scale=params.get("noise_scale"))
        elif attack_type == "scaling":
            return self.scaling_attack(model_params, scale_factor=params.get("scale_factor"))
        elif attack_type == "ipm":
            return self.ipm_attack(model_params, target_params, attack_strength=params.get("attack_strength"))
        elif attack_type == "sign_flipping":
            return self.sign_flipping(model_params, target_params, scale_factor=params.get("scale_factor"))
        elif attack_type == "alie":
            return self.alie_attack(
                model_params,
                target_params,
                z_max=params.get("z_max"),
                num_clients=params.get("num_clients"),
                num_adv=params.get("num_adv"),
            )
        else:
            return model_params

    def get_attack_info(self) -> dict[str, Any]:
        return {
            "attack_type": self.attack_type,
            "attack_params": self.attack_params,
            "malicious_clients": self.malicious_clients,
            "num_malicious_clients": len(self.malicious_clients),
        }


class ModelAttackManager:
    def __init__(self, attack_config: dict[str, Any]):
        self.attack_config = attack_config
        self.attack_enabled = attack_config.get("enable", False)

        if self.attack_enabled:
            self.model_poison_attack = ModelPoisonAttack(attack_config)
        else:
            self.model_poison_attack = None

        self.logger = logging.getLogger(__name__)

    def is_attack_enabled(self) -> bool:
        return self.attack_enabled

    def is_malicious_client(self, client_id: int) -> bool:
        if not self.attack_enabled or self.model_poison_attack is None:
            return False
        return self.model_poison_attack.is_malicious_client(client_id)

    def apply_model_poison_attack(
        self,
        client_id: int,
        model_params: dict[str, Any],
        target_params: dict[str, Any] | None = None,
        override_type: str | None = None,
        override_params: dict | None = None,
    ) -> dict[str, Any]:
        if not self.attack_enabled or self.model_poison_attack is None:
            return model_params

        return self.model_poison_attack.apply_attack(
            client_id, model_params, target_params, override_type=override_type, override_params=override_params
        )

    def get_attack_summary(self) -> dict[str, Any]:
        if not self.attack_enabled or self.model_poison_attack is None:
            return {"attack_enabled": False}

        summary = {"attack_enabled": True}
        summary.update(self.model_poison_attack.get_attack_info())
        return summary
