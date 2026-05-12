import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, Loader2, Zap, Shield } from "lucide-react";
import { api } from "../api/client";
import IntensitySelector from "../components/IntensitySelector";

const ATTACK_TEMPLATE = `from typing import Any, Dict, List, Optional

import torch

from fl_core.research.base_attack import ResearchAttackStrategy


class MyAttack(ResearchAttackStrategy):
    """Your attack description."""

    method_name = "arena_attack_my_method"

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        pass

    def attack(
        self,
        local_model_params: Dict[str, torch.Tensor],
        global_model_params: Dict[str, torch.Tensor],
        all_client_params: Optional[List[Dict[str, torch.Tensor]]] = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> Dict[str, torch.Tensor]:
        # Your attack logic here
        return local_model_params
`;

const DEFENSE_TEMPLATE = `from typing import Any, Dict, List, Optional

import torch

from fl_core.research.base_defense import ResearchDefenseStrategy


class MyDefense(ResearchDefenseStrategy):
    """Your defense description."""

    method_name = "arena_defense_my_method"

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        pass

    def aggregate(
        self,
        client_models: List[Dict[str, torch.Tensor]],
        client_weights: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> Dict[str, torch.Tensor]:
        # Your aggregation logic here
        n = len(client_models)
        out: Dict[str, torch.Tensor] = {}
        for k in client_models[0]:
            out[k] = sum(cm[k] for cm in client_models) / n
        return out
`;

interface Template {
  label: string;
  role: "attack" | "defense";
  icon: React.ReactNode;
  description: string;
  displayName: string;
  code: string;
}

const TEMPLATES: Template[] = [
  {
    label: "Gaussian Noise",
    role: "attack",
    icon: <Zap className="w-4 h-4" />,
    description: "Add calibrated Gaussian noise to local model updates",
    displayName: "Gaussian Noise Attack",
    code: `from typing import Any, Dict, List, Optional

import torch

from fl_core.research.base_attack import ResearchAttackStrategy


class GaussianNoiseAttack(ResearchAttackStrategy):
    method_name = "arena_attack_gaussian_custom"

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.noise_scale = 0.1

    def attack(
        self,
        local_model_params: Dict[str, torch.Tensor],
        global_model_params: Dict[str, torch.Tensor],
        all_client_params: Optional[List[Dict[str, torch.Tensor]]] = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> Dict[str, torch.Tensor]:
        poisoned = {}
        for k, v in local_model_params.items():
            noise = torch.randn_like(v) * self.noise_scale
            poisoned[k] = v + noise
        return poisoned
`,
  },
  {
    label: "Gradient Scaling",
    role: "attack",
    icon: <Zap className="w-4 h-4" />,
    description: "Scale the difference between local and global to amplify poisoned updates",
    displayName: "Gradient Scaling Attack",
    code: `from typing import Any, Dict, List, Optional

import torch

from fl_core.research.base_attack import ResearchAttackStrategy


class GradientScalingAttack(ResearchAttackStrategy):
    method_name = "arena_attack_grad_scaling"

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.scale_factor = 5.0

    def attack(
        self,
        local_model_params: Dict[str, torch.Tensor],
        global_model_params: Dict[str, torch.Tensor],
        all_client_params: Optional[List[Dict[str, torch.Tensor]]] = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> Dict[str, torch.Tensor]:
        poisoned = {}
        for k in local_model_params:
            delta = local_model_params[k] - global_model_params[k]
            poisoned[k] = global_model_params[k] + delta * self.scale_factor
        return poisoned
`,
  },
  {
    label: "Coordinate Median",
    role: "defense",
    icon: <Shield className="w-4 h-4" />,
    description: "Aggregate using coordinate-wise median to resist outlier updates",
    displayName: "Coordinate Median Defense",
    code: `from typing import Any, Dict, List, Optional

import torch

from fl_core.research.base_defense import ResearchDefenseStrategy


class CoordinateMedianDefense(ResearchDefenseStrategy):
    method_name = "arena_defense_coord_median"

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        pass

    def aggregate(
        self,
        client_models: List[Dict[str, torch.Tensor]],
        client_weights: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> Dict[str, torch.Tensor]:
        out: Dict[str, torch.Tensor] = {}
        for k in client_models[0]:
            stacked = torch.stack([cm[k] for cm in client_models])
            out[k] = stacked.median(dim=0).values
        return out
`,
  },
  {
    label: "Trimmed Mean",
    role: "defense",
    icon: <Shield className="w-4 h-4" />,
    description: "Remove top/bottom fraction of values per coordinate before averaging",
    displayName: "Trimmed Mean Defense",
    code: `from typing import Any, Dict, List, Optional

import torch

from fl_core.research.base_defense import ResearchDefenseStrategy


class TrimmedMeanDefense(ResearchDefenseStrategy):
    method_name = "arena_defense_trimmed_mean"

    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.trim_ratio = 0.1

    def aggregate(
        self,
        client_models: List[Dict[str, torch.Tensor]],
        client_weights: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> Dict[str, torch.Tensor]:
        n = len(client_models)
        trim_count = max(1, int(n * self.trim_ratio))
        out: Dict[str, torch.Tensor] = {}
        for k in client_models[0]:
            stacked = torch.stack([cm[k] for cm in client_models])
            sorted_vals, _ = stacked.sort(dim=0)
            trimmed = sorted_vals[trim_count : n - trim_count]
            out[k] = trimmed.mean(dim=0)
        return out
`,
  },
];

export default function Submit() {
  const navigate = useNavigate();
  const [role, setRole] = useState<"attack" | "defense">("attack");
  const [code, setCode] = useState(ATTACK_TEMPLATE);
  const [displayName, setDisplayName] = useState("");
  const [author, setAuthor] = useState("");
  const [description, setDescription] = useState("");
  const [numSeeds, setNumSeeds] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [versionConflict, setVersionConflict] = useState(false);

  const handleRoleChange = (newRole: "attack" | "defense") => {
    setRole(newRole);
    setCode(newRole === "attack" ? ATTACK_TEMPLATE : DEFENSE_TEMPLATE);
  };

  const handleTemplate = (t: Template) => {
    setRole(t.role);
    setCode(t.code);
    setDisplayName(t.displayName);
    setDescription(t.description);
  };

  const handleSubmit = async (updateExisting = false) => {
    if (!displayName.trim()) {
      setError("Display name is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    setVersionConflict(false);
    try {
      const result = await api.createSubmission({
        code,
        role,
        display_name: displayName.trim(),
        author: author.trim() || undefined,
        description: description.trim() || undefined,
        num_seeds: numSeeds || undefined,
        update_existing: updateExisting,
      });
      navigate(`/submissions/${result.id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("already exists") && msg.includes("update_existing")) {
        setVersionConflict(true);
      }
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      {/* Template cards */}
      <div className="mb-6">
        <p className="text-xs text-slate-500 mb-2">Quick start from a template:</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {TEMPLATES.map((t) => (
            <button
              key={t.label}
              onClick={() => handleTemplate(t)}
              className="text-left p-3 bg-slate-800/50 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600 rounded-lg transition-colors group"
            >
              <div className="flex items-center gap-1.5 mb-1">
                <span className={t.role === "attack" ? "text-red-400" : "text-green-400"}>{t.icon}</span>
                <span className="text-sm font-medium text-slate-200 group-hover:text-slate-50">{t.label}</span>
              </div>
              <p className="text-xs text-slate-500 leading-tight">{t.description}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: metadata */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Role</label>
            <div className="flex gap-2">
              <button
                onClick={() => handleRoleChange("attack")}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                  role === "attack"
                    ? "bg-red-600/20 text-red-400 border border-red-600/40"
                    : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
                }`}
              >
                Attack
              </button>
              <button
                onClick={() => handleRoleChange("defense")}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                  role === "defense"
                    ? "bg-green-600/20 text-green-400 border border-green-600/40"
                    : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
                }`}
              >
                Defense
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Display Name *</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Gradient Inversion Attack"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Author</label>
            <input
              type="text"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="Your name"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of your method"
              rows={3}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>

          <IntensitySelector value={numSeeds} onChange={setNumSeeds} />

          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Submit & Evaluate
              </>
            )}
          </button>

          {error && (
            <div className="p-3 bg-red-900/30 border border-red-700/50 rounded-md text-red-400 text-sm">
              {error}
              {versionConflict && (
                <button
                  onClick={() => handleSubmit(true)}
                  disabled={submitting}
                  className="mt-2 w-full py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-700 text-white rounded-md text-sm font-medium transition-colors"
                >
                  Submit as New Version
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right: code editor */}
        <div className="lg:col-span-2">
          <label className="block text-sm text-slate-400 mb-1">strategy.py</label>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            spellCheck={false}
            className="w-full h-[500px] px-4 py-3 bg-slate-800 border border-slate-700 rounded-md text-green-700 dark:text-green-300 text-sm font-mono focus:outline-none focus:border-blue-500 resize-none leading-relaxed"
          />
        </div>
      </div>
    </div>
  );
}
