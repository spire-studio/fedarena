import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Loader2, CheckCircle, XCircle, Clock, Download, FileText, AlertTriangle, Sparkles, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import type { SubmissionDetail, JobProgress, ResultsSummary, OpponentResult, VersionInfo } from "../api/client";
import ScenarioSelector from "../components/ScenarioSelector";
import TrainingChart from "../components/TrainingChart";
import { exportPdf } from "../utils/exportPdf";

export default function Detail() {
  const { id } = useParams<{ id: string }>();
  const [submission, setSubmission] = useState<SubmissionDetail | null>(null);
  const [job, setJob] = useState<JobProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [scenario, setScenario] = useState("cifar10_noniid");
  const [versions, setVersions] = useState<VersionInfo[]>([]);

  useEffect(() => {
    if (!id) return;
    api
      .getSubmission(Number(id))
      .then((s) => {
        setSubmission(s);
        api.getVersions(s.id).then(setVersions).catch(() => {});
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!submission?.job_id) return;
    if (submission.status === "completed" || submission.status === "failed") return;

    const poll = () => {
      api.getJobProgress(submission.job_id!).then((j) => {
        setJob(j);
        if (j.status === "completed" || j.status === "failed") {
          api.getSubmission(Number(id)).then(setSubmission);
        }
      });
    };
    poll();
    const interval = setInterval(poll, 1500);
    return () => clearInterval(interval);
  }, [submission?.job_id, submission?.status, id]);

  const handleAnalysis = (regenerate = false) => {
    if (!submission) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    api
      .getAnalysis(submission.id, regenerate)
      .then((res) => setAnalysis(res.analysis))
      .catch((e) => setAnalysisError(e.message))
      .finally(() => setAnalysisLoading(false));
  };

  if (loading) return <p className="text-slate-400">Loading...</p>;
  if (error) return <p className="text-red-400">{error}</p>;
  if (!submission) return <p className="text-red-400">Not found</p>;

  const isRunning = submission.status === "evaluating" || submission.status === "pending";

  const rawResults = submission.results;
  const hasScenarios = rawResults && "scenarios" in rawResults;
  const scenarioResults: Record<string, OpponentResult> | null = hasScenarios
    ? ((rawResults as Record<string, Record<string, Record<string, OpponentResult>>>).scenarios?.[scenario] ?? null)
    : rawResults as Record<string, OpponentResult> | null;

  const summary: ResultsSummary | null = scenarioResults?.["__summary__"] as ResultsSummary | null;
  const opponentEntries = scenarioResults
    ? Object.entries(scenarioResults).filter(([k]) => k !== "__summary__")
    : [];

  return (
    <div>
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 mb-6">
        <ArrowLeft className="w-4 h-4" /> Back to Leaderboard
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-50">{submission.display_name}</h1>
            {(submission.version ?? 1) > 1 && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-600/20 text-amber-400 border border-amber-600/40">
                v{submission.version}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 font-mono mt-1">{submission.method_name}</p>
          {submission.author && (
            <p className="text-sm text-slate-400 mt-1">by {submission.author}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {submission.status === "completed" && (
            <div className="flex gap-1.5">
              <a
                href={api.getSubmissionReportUrl(submission.id)}
                download
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                Markdown
              </a>
              <button
                onClick={() => exportPdf(submission)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors"
              >
                <FileText className="w-3.5 h-3.5" />
                PDF
              </button>
            </div>
          )}
          <StatusBadge status={submission.status} />
        </div>
      </div>

      {submission.description && (
        <p className="text-slate-400 mb-6">{submission.description}</p>
      )}

      {hasScenarios && (
        <div className="flex items-center gap-2 mb-6">
          <span className="text-xs text-slate-500">Scenario:</span>
          <ScenarioSelector value={scenario} onChange={setScenario} />
          {!scenarioResults && (
            <span className="text-xs text-slate-500">No results for this scenario</span>
          )}
        </div>
      )}

      {/* Progress bar while evaluating */}
      {isRunning && job && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
            <span className="text-sm text-slate-300">Evaluating...</span>
            <span className="text-sm text-slate-500">{job.progress}</span>
          </div>
          {job.current_opponent && (
            <p className="text-xs text-slate-500 mb-2">
              Currently running: vs {job.current_opponent}
            </p>
          )}
          <div className="w-full bg-slate-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all"
              style={{
                width: `${job.total_opponents ? (job.completed_opponents / job.total_opponents) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Error panel */}
      {submission.status === "failed" && (submission.error || job?.error) && (
        <div className="bg-red-950/30 border border-red-800/50 rounded-lg p-4 mb-6">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-red-400 mb-1">Evaluation Failed</p>
              <pre className="text-xs text-red-300/80 font-mono whitespace-pre-wrap break-words">
                {submission.error || job?.error}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Summary metrics cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
          <MetricCard label="Avg Accuracy" value={summary.avg_accuracy} fmt={(v) => v.toFixed(4)}
            sub={submission.role === "attack" ? "lower = stronger" : "higher = stronger"} />
          <MetricCard label="Acc. Drop" value={summary.avg_accuracy_drop} fmt={(v) => v.toFixed(4)} />
          <MetricCard label="Worst Case" value={summary.worst_case_accuracy} fmt={(v) => v.toFixed(4)} />
          <MetricCard label="Best Case" value={summary.best_case_accuracy} fmt={(v) => v.toFixed(4)} />
          <MetricCard label="Convergence" value={summary.avg_convergence_speed} fmt={(v) => `${Math.round(v)} rounds`} />
          <MetricCard label="Stability" value={summary.avg_stability} fmt={(v) => v.toFixed(4)} sub="lower = more stable" />
        </div>
      )}

      {/* Results table */}
      {opponentEntries.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-slate-50 mb-4">Per-Opponent Results</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400">
                  <th className="text-left py-3 px-3">Opponent</th>
                  <th className="text-right py-3 px-3">Accuracy</th>
                  <th className="text-right py-3 px-3">Baseline</th>
                  <th className="text-right py-3 px-3">Acc. Drop</th>
                  <th className="text-right py-3 px-3">Max Acc</th>
                  <th className="text-right py-3 px-3">Conv.</th>
                  <th className="text-right py-3 px-3">Stability</th>
                  <th className="text-right py-3 px-3">Runtime</th>
                </tr>
              </thead>
              <tbody>
                {opponentEntries.map(([opp, res]) => (
                  <tr key={opp} className="border-b border-slate-800">
                    <td className="py-3 px-3 text-slate-300 font-mono text-xs">
                      {opp.replace("__none__", "none").replace("baseline_", "")}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-50">
                      {res.avg_final_accuracy != null
                        ? res.avg_final_accuracy.toFixed(4)
                        : <span className="text-red-400" title={
                            res.per_seed.find((s) => s.error)?.error || undefined
                          }>FAIL</span>}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-500">
                      {res.baseline_accuracy != null ? res.baseline_accuracy.toFixed(4) : "-"}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-400">
                      {res.accuracy_drop != null ? res.accuracy_drop.toFixed(4) : "-"}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-400">
                      {res.max_accuracy != null ? res.max_accuracy.toFixed(4) : "-"}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-400">
                      {res.avg_convergence_speed != null ? `${Math.round(res.avg_convergence_speed)}` : "-"}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-400">
                      {res.avg_stability != null ? res.avg_stability.toFixed(4) : "-"}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-400">
                      {res.avg_runtime_seconds != null ? `${res.avg_runtime_seconds.toFixed(1)}s` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Training curves */}
      {submission.results && (
        <TrainingChart results={Object.fromEntries(opponentEntries)} role={submission.role} />
      )}

      {/* LLM Analysis */}
      {submission.status === "completed" && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-50">Analysis</h2>
            <div className="flex gap-1.5">
              {!analysis && !analysisLoading && (
                <button
                  onClick={() => handleAnalysis(false)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-purple-600/20 text-purple-400 border border-purple-600/40 hover:bg-purple-600/30 transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Generate Analysis
                </button>
              )}
              {analysis && !analysisLoading && (
                <button
                  onClick={() => handleAnalysis(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Regenerate
                </button>
              )}
            </div>
          </div>
          {analysisLoading && (
            <div className="flex items-center gap-2 p-4 bg-slate-800 rounded-lg">
              <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
              <span className="text-sm text-slate-400">Generating analysis...</span>
            </div>
          )}
          {analysisError && (
            <p className="text-sm text-red-400">{analysisError}</p>
          )}
          {analysis && !analysisLoading && (
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
              <MarkdownContent content={analysis} />
            </div>
          )}
        </div>
      )}

      {/* Version History */}
      {versions.length > 1 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-50">Version History</h2>
            <Link
              to={`/compare?ids=${versions.map((v) => v.id).join(",")}`}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              Compare versions
            </Link>
          </div>
          <div className="space-y-2">
            {versions.map((v) => (
              <Link
                key={v.id}
                to={`/submissions/${v.id}`}
                className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                  v.id === submission.id
                    ? "bg-blue-600/10 border-blue-600/30"
                    : "bg-slate-800/50 border-slate-700/50 hover:border-slate-600"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-700 text-slate-300">
                    v{v.version}
                  </span>
                  <span className="text-sm text-slate-300">{v.display_name}</span>
                  <StatusBadge status={v.status} />
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  {v.avg_accuracy != null && (
                    <span className="font-mono">{v.avg_accuracy.toFixed(4)}</span>
                  )}
                  <span>{new Date(v.created_at).toLocaleDateString()}</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Code */}
      <div>
        <h2 className="text-lg font-semibold text-slate-50 mb-4">Code</h2>
        <pre className="bg-slate-800 border border-slate-700 rounded-lg p-4 overflow-x-auto text-sm text-green-700 dark:text-green-300 font-mono leading-relaxed">
          {submission.code}
        </pre>
      </div>
    </div>
  );
}

function MetricCard({ label, value, fmt, sub }: {
  label: string;
  value?: number;
  fmt?: (v: number) => string;
  sub?: string;
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-sm font-mono font-bold text-slate-50">
        {value != null ? (fmt ? fmt(value) : value.toFixed(4)) : "-"}
      </p>
      {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  const html = content
    .replace(/^### (.+)$/gm, '<h3 class="text-sm font-semibold text-slate-200 mt-4 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-base font-semibold text-slate-100 mt-5 mb-2">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-slate-200">$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="bg-slate-700 px-1 py-0.5 rounded text-xs">$1</code>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-slate-400">$1</li>')
    .replace(/\n\n/g, '</p><p class="text-sm text-slate-400 mb-2">')
    .replace(/\n/g, "<br/>");

  return (
    <div
      className="text-sm text-slate-400 leading-relaxed"
      dangerouslySetInnerHTML={{ __html: `<p class="text-sm text-slate-400 mb-2">${html}</p>` }}
    />
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { icon: React.ReactNode; cls: string }> = {
    completed: {
      icon: <CheckCircle className="w-4 h-4" />,
      cls: "bg-green-600/20 text-green-400 border-green-600/40",
    },
    failed: {
      icon: <XCircle className="w-4 h-4" />,
      cls: "bg-red-600/20 text-red-400 border-red-600/40",
    },
    evaluating: {
      icon: <Loader2 className="w-4 h-4 animate-spin" />,
      cls: "bg-blue-600/20 text-blue-400 border-blue-600/40",
    },
    pending: {
      icon: <Clock className="w-4 h-4" />,
      cls: "bg-yellow-600/20 text-yellow-400 border-yellow-600/40",
    },
  };
  const c = config[status] || config.pending;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${c.cls}`}>
      {c.icon}
      {status}
    </span>
  );
}
