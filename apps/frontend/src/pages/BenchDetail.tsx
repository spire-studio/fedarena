import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  FlaskConical,
  ArrowLeft,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { api } from "../api/client";
import type { BenchJob } from "../api/client";

export default function BenchDetail() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<BenchJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .getBenchJob(Number(id))
      .then(setJob)
      .catch((e) => setError(e.message));
  }, [id]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const interval = setInterval(() => {
      api.getBenchJob(job.id).then(setJob).catch(() => {});
    }, 2000);
    return () => clearInterval(interval);
  }, [job]);

  if (error) return <p className="text-red-400">{error}</p>;
  if (!job) return <p className="text-slate-400">Loading...</p>;

  const isRunning = job.status === "running" || job.status === "queued" || job.status === "planning";

  return (
    <div>
      <Link to="/bench" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to Bench
      </Link>

      {/* Header */}
      <div className="flex items-start gap-3 mb-6">
        <FlaskConical className="w-6 h-6 text-blue-400 mt-0.5" />
        <div className="flex-1">
          <h1 className="text-xl font-bold text-slate-50">Bench #{job.id}</h1>
          <p className="text-sm text-slate-400 mt-1">{job.prompt}</p>
        </div>
        <StatusBadge status={job.status} />
      </div>

      {/* Plan summary */}
      {job.plan_summary && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
          <h2 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Plan Summary</h2>
          <p className="text-sm text-slate-300">{job.plan_summary}</p>
        </div>
      )}

      {/* Progress */}
      {isRunning && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2 text-sm text-slate-400 mb-2">
            <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
            {job.current_experiment ? `Running: ${job.current_experiment}` : "Starting..."}
            <span className="text-slate-600">({job.completed_experiments}/{job.total_experiments})</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all"
              style={{ width: `${job.total_experiments ? (job.completed_experiments / job.total_experiments) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Error */}
      {job.status === "failed" && job.error && (
        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4 mb-6 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-400">Job Failed</p>
            <p className="text-sm text-red-300/80 mt-1 whitespace-pre-wrap">{job.error}</p>
          </div>
        </div>
      )}

      {/* Experiment plan */}
      {job.experiments.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm text-slate-400 mb-3">Experiments ({job.experiments.length})</h2>
          <div className="flex flex-wrap gap-2">
            {job.experiments.map((exp, i) => (
              <span key={i} className="text-xs bg-slate-800 border border-slate-700 text-slate-300 px-2.5 py-1 rounded-md">
                {(exp.attack_method || "none").replace("baseline_", "")} vs {(exp.defense_method || "FedAvg").replace("baseline_", "")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Results table */}
      {job.results && job.results.length > 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <h2 className="text-sm text-slate-400 px-4 pt-4 pb-2">Results</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500 text-xs">
                <th className="text-left py-2 px-4">Experiment</th>
                <th className="text-left py-2 px-4">Attack</th>
                <th className="text-left py-2 px-4">Defense</th>
                <th className="text-right py-2 px-4">Accuracy</th>
                <th className="text-right py-2 px-4">Loss</th>
              </tr>
            </thead>
            <tbody>
              {job.results.map((r, i) => (
                <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                  <td className="py-2.5 px-4 text-slate-300 font-mono text-xs">{r.name}</td>
                  <td className="py-2.5 px-4 text-slate-400 text-xs">{(r.attack_method || "none").replace("baseline_", "")}</td>
                  <td className="py-2.5 px-4 text-slate-400 text-xs">{(r.defense_method || "FedAvg").replace("baseline_", "")}</td>
                  <td className="py-2.5 px-4 text-right font-mono">
                    {r.final_accuracy != null ? (
                      <span className="text-slate-50">{r.final_accuracy.toFixed(4)}</span>
                    ) : (
                      <span className="text-red-400 text-xs">FAIL</span>
                    )}
                  </td>
                  <td className="py-2.5 px-4 text-right font-mono text-slate-400 text-xs">
                    {r.final_loss != null ? r.final_loss.toFixed(4) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Summary stats */}
          {job.results.length > 1 && (() => {
            const accs = job.results!.filter((r) => r.final_accuracy != null).map((r) => r.final_accuracy!);
            if (accs.length === 0) return null;
            const avg = accs.reduce((a, b) => a + b, 0) / accs.length;
            const min = Math.min(...accs);
            const max = Math.max(...accs);
            return (
              <div className="flex gap-6 px-4 py-3 border-t border-slate-700 text-xs text-slate-500">
                <span>Avg: <span className="text-slate-300 font-mono">{avg.toFixed(4)}</span></span>
                <span>Min: <span className="text-slate-300 font-mono">{min.toFixed(4)}</span></span>
                <span>Max: <span className="text-slate-300 font-mono">{max.toFixed(4)}</span></span>
                <span>Completed: <span className="text-slate-300">{accs.length}/{job.results!.length}</span></span>
              </div>
            );
          })()}
        </div>
      )}

      {/* Timestamps */}
      <div className="mt-6 flex gap-6 text-xs text-slate-500">
        {job.started_at && <span>Started: {new Date(job.started_at).toLocaleString()}</span>}
        {job.completed_at && <span>Completed: {new Date(job.completed_at).toLocaleString()}</span>}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { icon: React.ReactNode; cls: string }> = {
    completed: { icon: <CheckCircle className="w-3.5 h-3.5" />, cls: "bg-green-600/20 text-green-400" },
    failed: { icon: <XCircle className="w-3.5 h-3.5" />, cls: "bg-red-600/20 text-red-400" },
    running: { icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />, cls: "bg-blue-600/20 text-blue-400" },
    queued: { icon: <Clock className="w-3.5 h-3.5" />, cls: "bg-yellow-600/20 text-yellow-400" },
    planning: { icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />, cls: "bg-purple-600/20 text-purple-400" },
  };
  const c = cfg[status] || cfg.queued;
  return (
    <span className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full ${c.cls}`}>
      {c.icon}
      {status}
    </span>
  );
}
