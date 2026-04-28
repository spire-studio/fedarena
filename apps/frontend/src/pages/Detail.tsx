import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Loader2, CheckCircle, XCircle, Clock, Download, FileText, AlertTriangle } from "lucide-react";
import { api } from "../api/client";
import type { SubmissionDetail, JobProgress } from "../api/client";
import TrainingChart from "../components/TrainingChart";
import { exportPdf } from "../utils/exportPdf";

export default function Detail() {
  const { id } = useParams<{ id: string }>();
  const [submission, setSubmission] = useState<SubmissionDetail | null>(null);
  const [job, setJob] = useState<JobProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch submission
  useEffect(() => {
    if (!id) return;
    api
      .getSubmission(Number(id))
      .then(setSubmission)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Poll job progress while evaluating
  useEffect(() => {
    if (!submission?.job_id) return;
    if (submission.status === "completed" || submission.status === "failed") return;

    const poll = () => {
      api.getJobProgress(submission.job_id!).then((j) => {
        setJob(j);
        if (j.status === "completed" || j.status === "failed") {
          // Refresh submission to get results
          api.getSubmission(Number(id)).then(setSubmission);
        }
      });
    };
    poll();
    const interval = setInterval(poll, 1500);
    return () => clearInterval(interval);
  }, [submission?.job_id, submission?.status, id]);

  if (loading) return <p className="text-slate-400">Loading...</p>;
  if (error) return <p className="text-red-400">{error}</p>;
  if (!submission) return <p className="text-red-400">Not found</p>;

  const isRunning = submission.status === "evaluating" || submission.status === "pending";

  return (
    <div>
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 mb-6">
        <ArrowLeft className="w-4 h-4" /> Back to Leaderboard
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-50">{submission.display_name}</h1>
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

      {/* Results table */}
      {submission.results && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-slate-50 mb-4">Results</h2>
          {(() => {
            const entries = Object.entries(submission.results!);
            const multiSeed = entries.some(([, res]) => res.per_seed.length > 1);
            return (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400">
                      <th className="text-left py-3 px-4">Opponent</th>
                      <th className="text-right py-3 px-4">Accuracy</th>
                      {multiSeed && <th className="text-right py-3 px-4">Per Seed</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map(([opp, res]) => (
                      <tr key={opp} className="border-b border-slate-800">
                        <td className="py-3 px-4 text-slate-300 font-mono text-xs">
                          {opp.replace("__none__", "none").replace("baseline_", "")}
                        </td>
                        <td className="py-3 px-4 text-right font-mono text-slate-50">
                          {res.avg_final_accuracy != null
                            ? res.avg_final_accuracy.toFixed(4)
                            : <span className="text-red-400" title={
                                res.per_seed.find((s) => s.error)?.error || undefined
                              }>FAIL</span>}
                        </td>
                        {multiSeed && (
                          <td className="py-3 px-4 text-right font-mono text-xs">
                            {res.per_seed.map((s, i) => (
                              <span key={s.seed}>
                                {i > 0 && ", "}
                                {s.final_accuracy != null
                                  ? <span className="text-slate-500">{s.final_accuracy.toFixed(4)}</span>
                                  : <span className="text-red-400" title={s.error || undefined}>fail</span>}
                              </span>
                            ))}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })()}

          {/* Avg summary */}
          {(() => {
            const accs = Object.values(submission.results!)
              .map((r) => r.avg_final_accuracy)
              .filter((a): a is number => a != null);
            const avg = accs.length ? accs.reduce((a, b) => a + b, 0) / accs.length : null;
            return avg != null ? (
              <div className="mt-4 p-4 bg-slate-800 rounded-lg">
                <span className="text-slate-400 text-sm">Overall avg accuracy: </span>
                <span className="text-slate-50 font-mono font-bold">{avg.toFixed(4)}</span>
                <span className="text-slate-500 text-xs ml-2">
                  ({submission.role === "attack" ? "lower = stronger" : "higher = stronger"})
                </span>
              </div>
            ) : null;
          })()}
        </div>
      )}

      {/* Training curves */}
      {submission.results && (
        <TrainingChart results={submission.results} role={submission.role} />
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
