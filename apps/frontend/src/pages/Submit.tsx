import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, Loader2 } from "lucide-react";
import { api } from "../api/client";

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

export default function Submit() {
  const navigate = useNavigate();
  const [role, setRole] = useState<"attack" | "defense">("attack");
  const [code, setCode] = useState(ATTACK_TEMPLATE);
  const [displayName, setDisplayName] = useState("");
  const [author, setAuthor] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRoleChange = (newRole: "attack" | "defense") => {
    setRole(newRole);
    setCode(newRole === "attack" ? ATTACK_TEMPLATE : DEFENSE_TEMPLATE);
  };

  const handleSubmit = async () => {
    if (!displayName.trim()) {
      setError("Display name is required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.createSubmission({
        code,
        role,
        display_name: displayName.trim(),
        author: author.trim() || undefined,
        description: description.trim() || undefined,
      });
      navigate(`/submissions/${result.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: metadata */}
        <div className="space-y-4">
          {/* Role */}
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

          {/* Display name */}
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

          {/* Author */}
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

          {/* Description */}
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

          {/* Submit button */}
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
