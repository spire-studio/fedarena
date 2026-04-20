import { useEffect, useState } from "react";
import { FlaskConical, Send, Loader2 } from "lucide-react";
import { api } from "../api/client";
import type { AgentConfig, BenchJob } from "../api/client";

const EXAMPLES = [
  "Compare IPM and Scaling attacks against Krum and Median defenses",
  "Test all attacks against FedAvg (no defense)",
  "Run baseline_alie against all defenses",
  "Run a vanilla CIFAR-10 non-IID FedAvg baseline with no attack",
];

export default function Bench() {
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<BenchJob | null>(null);
  const [history, setHistory] = useState<BenchJob[]>([]);

  useEffect(() => {
    api.getAgentConfig().then(setConfig).catch(() => {});
    api.listBenchJobs().then(setHistory).catch(() => {});
  }, []);

  // Poll active job
  useEffect(() => {
    if (!activeJob || activeJob.status === "completed" || activeJob.status === "failed") return;
    const interval = setInterval(() => {
      api.getBenchJob(activeJob.id).then((j) => {
        setActiveJob(j);
        if (j.status === "completed" || j.status === "failed") {
          api.listBenchJobs().then(setHistory).catch(() => {});
        }
      });
    }, 2000);
    return () => clearInterval(interval);
  }, [activeJob?.id, activeJob?.status]);

  const handleSubmit = async () => {
    if (!prompt.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const job = await api.createBenchJob(prompt.trim());
      setActiveJob(job);
      setPrompt("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const noKey = config && !config.has_api_key;

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <FlaskConical className="w-6 h-6 text-blue-400" />
        <h1 className="text-2xl font-bold text-slate-50">Bench</h1>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Describe experiments in natural language. The system parses your intent, plans the experiment matrix, runs them, and reports results.
      </p>

      {/* Prompt input */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. Compare IPM and Scaling against Krum and Median"
          rows={3}
          disabled={submitting || !!noKey}
          className="w-full bg-transparent text-slate-50 text-sm placeholder-slate-500 focus:outline-none resize-none leading-relaxed disabled:opacity-50"
        />
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-700">
          <div className="text-xs text-slate-500">
            {noKey && <span className="text-red-400">API key not configured</span>}
          </div>
          <button
            onClick={handleSubmit}
            disabled={submitting || !prompt.trim() || !!noKey}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-md text-sm font-medium transition-colors"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Run Experiments
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-700/50 rounded-md text-red-400 text-sm mb-6">
          {error}
        </div>
      )}

      {/* Examples */}
      {!activeJob && (
        <div className="mb-8">
          <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Examples</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {EXAMPLES.map((ex, i) => (
              <button
                key={i}
                onClick={() => setPrompt(ex)}
                className="text-left p-3 bg-slate-800/50 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600 rounded-lg text-sm text-slate-400 hover:text-slate-200 transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Active job */}
      {activeJob && <BenchJobCard job={activeJob} />}

      {/* History */}
      {history.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm text-slate-400 mb-3">Recent Jobs</h3>
          <div className="space-y-3">
            {history
              .filter((j) => j.id !== activeJob?.id)
              .slice(0, 5)
              .map((j) => (
                <BenchJobCard key={j.id} job={j} compact />
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BenchJobCard({ job, compact }: { job: BenchJob; compact?: boolean }) {
  const isRunning = job.status === "running" || job.status === "queued" || job.status === "planning";

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-sm text-slate-50 font-medium">{job.prompt}</p>
          {job.plan_summary && <p className="text-xs text-slate-500 mt-1">{job.plan_summary}</p>}
        </div>
        <span className={`text-xs px-2 py-1 rounded-full ${
          job.status === "completed" ? "bg-green-600/20 text-green-400" :
          job.status === "failed" ? "bg-red-600/20 text-red-400" :
          "bg-blue-600/20 text-blue-400"
        }`}>
          {job.status}
        </span>
      </div>

      {/* Progress */}
      {isRunning && (
        <div className="mb-3">
          <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            {job.current_experiment ? `Running: ${job.current_experiment}` : "Starting..."}
            <span className="text-slate-600">({job.completed_experiments}/{job.total_experiments})</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all"
              style={{ width: `${job.total_experiments ? (job.completed_experiments / job.total_experiments) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Experiment plan */}
      {!compact && job.experiments.length > 0 && (
        <div className="mb-3">
          <h4 className="text-xs text-slate-500 mb-1">Plan ({job.experiments.length} experiments)</h4>
          <div className="flex flex-wrap gap-1">
            {job.experiments.map((exp, i) => (
              <span key={i} className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">
                {(exp.attack_method || "none").replace("baseline_", "")} vs {(exp.defense_method || "FedAvg").replace("baseline_", "")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Results table */}
      {job.results && job.results.length > 0 && (
        <div>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="text-left py-1.5 pr-3">Experiment</th>
                <th className="text-left py-1.5 pr-3">Attack</th>
                <th className="text-left py-1.5 pr-3">Defense</th>
                <th className="text-right py-1.5">Accuracy</th>
              </tr>
            </thead>
            <tbody>
              {job.results.map((r, i) => (
                <tr key={i} className="border-b border-slate-800">
                  <td className="py-1.5 pr-3 text-slate-300 font-mono">{r.name}</td>
                  <td className="py-1.5 pr-3 text-slate-400">{(r.attack_method || "none").replace("baseline_", "")}</td>
                  <td className="py-1.5 pr-3 text-slate-400">{(r.defense_method || "FedAvg").replace("baseline_", "")}</td>
                  <td className="py-1.5 text-right font-mono text-slate-50">
                    {r.final_accuracy != null ? r.final_accuracy.toFixed(4) : <span className="text-red-400">FAIL</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {job.error && (
        <p className="text-xs text-red-400 mt-2">{job.error}</p>
      )}
    </div>
  );
}
