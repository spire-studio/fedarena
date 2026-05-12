import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Loader2, AlertCircle, CheckCircle, ArrowLeft, Play } from "lucide-react";
import { api } from "../api/client";
import type { AgentConfig } from "../api/client";
import IntensitySelector from "../components/IntensitySelector";
import { useAgent } from "../context/AgentContext";

const EXAMPLE_PROMPTS = [
  "Design an attack that adaptively scales poisoned updates based on the global model's gradient norm to evade norm-based defenses",
  "Create a defense that uses the geometric median of client updates instead of arithmetic mean",
  "Implement an attack that adds carefully crafted noise aligned with the principal component of honest gradients",
  "Design a defense that clusters client updates via k-means and only aggregates the largest cluster",
];

export default function Agent() {
  const navigate = useNavigate();
  const agent = useAgent();
  const [config, setConfig] = useState<AgentConfig | null>(null);

  useEffect(() => {
    api.getAgentConfig().then(setConfig).catch(() => {});
  }, []);

  const noKey = config && !config.has_api_key;

  const [versionConflict, setVersionConflict] = useState(false);

  const handleApprove = async (updateExisting = false) => {
    agent.setPhase("submitting");
    agent.setError(null);
    setVersionConflict(false);
    try {
      const result = await api.createSubmission({
        code: agent.code,
        role: agent.role,
        display_name: agent.displayName.trim() || "Untitled",
        author: "agent",
        description: agent.description.trim() || undefined,
        num_seeds: agent.numSeeds || undefined,
        update_existing: updateExisting,
      });
      agent.reset();
      navigate(`/submissions/${result.id}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("already exists") && msg.includes("update_existing")) {
        setVersionConflict(true);
      }
      agent.setError(msg);
      agent.setPhase("review");
    }
  };

  // ── Review view ──
  if (agent.phase === "review" || agent.phase === "submitting") {
    return (
      <div>
        <button
          onClick={agent.reset}
          disabled={agent.phase === "submitting"}
          className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 mb-4 disabled:opacity-50"
        >
          <ArrowLeft className="w-4 h-4" /> Back to prompt
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: metadata */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Role</label>
              <div className="flex gap-2">
                {(["attack", "defense"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => agent.setRole(r)}
                    disabled={agent.phase === "submitting"}
                    className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                      agent.role === r
                        ? r === "attack"
                          ? "bg-red-600/20 text-red-400 border border-red-600/40"
                          : "bg-green-600/20 text-green-400 border border-green-600/40"
                        : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm text-slate-400 mb-1">Display Name</label>
              <input
                value={agent.displayName}
                onChange={(e) => agent.setDisplayName(e.target.value)}
                disabled={agent.phase === "submitting"}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm text-slate-400 mb-1">Description</label>
              <textarea
                value={agent.description}
                onChange={(e) => agent.setDescription(e.target.value)}
                rows={3}
                disabled={agent.phase === "submitting"}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500 resize-none"
              />
            </div>

            <IntensitySelector
              value={agent.numSeeds}
              onChange={agent.setNumSeeds}
              disabled={agent.phase === "submitting"}
            />

            <button
              onClick={() => handleApprove()}
              disabled={agent.phase === "submitting" || !agent.code.trim()}
              className="w-full py-2.5 bg-green-600 hover:bg-green-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              {agent.phase === "submitting" ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Approve &amp; Evaluate
                </>
              )}
            </button>

            {agent.error && (
              <div className="p-3 bg-red-900/30 border border-red-700/50 rounded-md text-red-400 text-sm whitespace-pre-wrap">
                {agent.error}
                {versionConflict && (
                  <button
                    onClick={() => handleApprove(true)}
                    disabled={agent.phase === "submitting"}
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
            <label className="block text-sm text-slate-400 mb-1">Generated Code (editable)</label>
            <textarea
              value={agent.code}
              onChange={(e) => agent.setCode(e.target.value)}
              disabled={agent.phase === "submitting"}
              spellCheck={false}
              className="w-full h-[500px] px-4 py-3 bg-slate-800 border border-slate-700 rounded-md text-green-700 dark:text-green-300 text-sm font-mono focus:outline-none focus:border-blue-500 resize-none leading-relaxed"
            />
          </div>
        </div>
      </div>
    );
  }

  // ── Idle / Generating view ──
  return (
    <div>
      <p className="text-slate-400 text-sm mb-4">
        Describe your attack or defense idea in natural language.
      </p>

      {config && (
        <div className={`flex items-center gap-2 text-xs mb-4 ${noKey ? "text-red-400" : "text-slate-500"}`}>
          {noKey ? (
            <>
              <AlertCircle className="w-3.5 h-3.5" />
              API key not configured. Set OPENAI_API_KEY in .env
            </>
          ) : (
            <>
              <CheckCircle className="w-3.5 h-3.5 text-green-500" />
              Model: {config.model} | Base: {config.api_base}
            </>
          )}
        </div>
      )}

      {/* Prompt input */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
        <textarea
          value={agent.prompt}
          onChange={(e) => agent.setPrompt(e.target.value)}
          placeholder="Describe your attack or defense idea..."
          rows={4}
          disabled={agent.phase === "generating" || !!noKey}
          className="w-full bg-transparent text-slate-50 text-sm placeholder-slate-500 focus:outline-none resize-none leading-relaxed disabled:opacity-50"
        />
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-700">
          <div className="text-xs text-slate-500">
            {agent.phase === "generating" && (
              <span className="flex items-center gap-1.5 text-purple-400">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Generating code...
              </span>
            )}
          </div>
          <button
            onClick={agent.generate}
            disabled={agent.phase === "generating" || !agent.prompt.trim() || !!noKey}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-md text-sm font-medium transition-colors"
          >
            {agent.phase === "generating" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            Generate
          </button>
        </div>
      </div>

      {agent.error && (
        <div className="p-4 bg-red-900/30 border border-red-700/50 rounded-lg text-red-400 text-sm mb-6 whitespace-pre-wrap">
          {agent.error}
        </div>
      )}

      {/* Example prompts */}
      <div>
        <h3 className="text-sm text-slate-400 mb-3">Examples</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {EXAMPLE_PROMPTS.map((example, i) => (
            <button
              key={i}
              onClick={() => agent.setPrompt(example)}
              disabled={agent.phase === "generating"}
              className="text-left p-3 bg-slate-800/50 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600 rounded-lg text-sm text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-50"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
