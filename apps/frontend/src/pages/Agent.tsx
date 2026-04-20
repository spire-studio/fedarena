import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Loader2, AlertCircle, CheckCircle, ArrowLeft, Play } from "lucide-react";
import { api } from "../api/client";
import type { AgentConfig } from "../api/client";

const EXAMPLE_PROMPTS = [
  "Design an attack that adaptively scales poisoned updates based on the global model's gradient norm to evade norm-based defenses",
  "Create a defense that uses the geometric median of client updates instead of arithmetic mean",
  "Implement an attack that adds carefully crafted noise aligned with the principal component of honest gradients",
  "Design a defense that clusters client updates via k-means and only aggregates the largest cluster",
];

type Phase = "idle" | "generating" | "review" | "submitting";

export default function Agent() {
  const navigate = useNavigate();
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [prompt, setPrompt] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);

  // Review state
  const [code, setCode] = useState("");
  const [role, setRole] = useState<"attack" | "defense">("attack");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    api.getAgentConfig().then(setConfig).catch(() => {});
  }, []);

  const noKey = config && !config.has_api_key;

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setPhase("generating");
    setError(null);
    try {
      const result = await api.generateCode(prompt.trim());
      setCode(result.code);
      setRole(result.role as "attack" | "defense");
      setDisplayName(result.display_name);
      setDescription(result.description);
      setPhase("review");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("idle");
    }
  };

  const handleApprove = async () => {
    setPhase("submitting");
    setError(null);
    try {
      const result = await api.createSubmission({
        code,
        role,
        display_name: displayName.trim() || "Untitled",
        author: "agent",
        description: description.trim() || undefined,
      });
      navigate(`/submissions/${result.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("review");
    }
  };

  const handleBack = () => {
    setPhase("idle");
    setError(null);
  };

  // ── Review view ──
  if (phase === "review" || phase === "submitting") {
    return (
      <div>
        <button
          onClick={handleBack}
          disabled={phase === "submitting"}
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
                    onClick={() => setRole(r)}
                    disabled={phase === "submitting"}
                    className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                      role === r
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
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={phase === "submitting"}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm text-slate-400 mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                disabled={phase === "submitting"}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-50 text-sm focus:outline-none focus:border-blue-500 resize-none"
              />
            </div>

            <button
              onClick={handleApprove}
              disabled={phase === "submitting" || !code.trim()}
              className="w-full py-2.5 bg-green-600 hover:bg-green-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-md text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              {phase === "submitting" ? (
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

            {error && (
              <div className="p-3 bg-red-900/30 border border-red-700/50 rounded-md text-red-400 text-sm whitespace-pre-wrap">
                {error}
              </div>
            )}
          </div>

          {/* Right: code editor */}
          <div className="lg:col-span-2">
            <label className="block text-sm text-slate-400 mb-1">Generated Code (editable)</label>
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              disabled={phase === "submitting"}
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
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe your attack or defense idea..."
          rows={4}
          disabled={phase === "generating" || !!noKey}
          className="w-full bg-transparent text-slate-50 text-sm placeholder-slate-500 focus:outline-none resize-none leading-relaxed disabled:opacity-50"
        />
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-700">
          <div className="text-xs text-slate-500">
            {phase === "generating" && (
              <span className="flex items-center gap-1.5 text-purple-400">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Generating code...
              </span>
            )}
          </div>
          <button
            onClick={handleGenerate}
            disabled={phase === "generating" || !prompt.trim() || !!noKey}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-md text-sm font-medium transition-colors"
          >
            {phase === "generating" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            Generate
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-900/30 border border-red-700/50 rounded-lg text-red-400 text-sm mb-6 whitespace-pre-wrap">
          {error}
        </div>
      )}

      {/* Example prompts */}
      <div>
        <h3 className="text-sm text-slate-400 mb-3">Examples</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {EXAMPLE_PROMPTS.map((example, i) => (
            <button
              key={i}
              onClick={() => setPrompt(example)}
              disabled={phase === "generating"}
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
