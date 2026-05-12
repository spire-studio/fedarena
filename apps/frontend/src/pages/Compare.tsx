import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { GitCompareArrows, Plus, X, Loader2 } from "lucide-react";
import { api } from "../api/client";
import type { Submission, SubmissionDetail, OpponentResult } from "../api/client";

const COLORS = [
  "#818cf8", "#34d399", "#f87171", "#fbbf24", "#60a5fa",
  "#a78bfa", "#f472b6", "#2dd4bf", "#fb923c", "#94a3b8",
];

export default function Compare() {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [details, setDetails] = useState<SubmissionDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [metric, setMetric] = useState<"accuracy" | "loss">("accuracy");

  useEffect(() => {
    api.listSubmissions().then((subs) => {
      setSubmissions(subs.filter((s) => s.status === "completed"));
    });
  }, []);

  useEffect(() => {
    if (selectedIds.length === 0) {
      setDetails([]);
      return;
    }
    setLoading(true);
    Promise.all(selectedIds.map((id) => api.getSubmission(id)))
      .then(setDetails)
      .finally(() => setLoading(false));
  }, [selectedIds]);

  const toggle = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const remove = (id: number) => {
    setSelectedIds((prev) => prev.filter((x) => x !== id));
  };

  const extractResults = (d: SubmissionDetail): Record<string, OpponentResult> | null => {
    if (!d.results) return null;
    if ("scenarios" in d.results) {
      const scenarios = d.results.scenarios as Record<string, Record<string, OpponentResult>>;
      return scenarios?.cifar10_noniid ?? Object.values(scenarios)[0] ?? null;
    }
    return d.results as Record<string, OpponentResult>;
  };

  const comparisonTable = details.length >= 2 ? buildComparisonTable(details, extractResults) : null;
  const overlayData = details.length >= 2 ? buildOverlayChart(details, extractResults, metric) : null;

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <GitCompareArrows className="w-6 h-6 text-purple-400" />
        <h1 className="text-2xl font-bold text-slate-50">Compare</h1>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Select 2+ completed submissions to compare side by side.
      </p>

      {/* Submission selector */}
      <div className="mb-6">
        <div className="flex flex-wrap gap-2 mb-3">
          {selectedIds.map((id) => {
            const sub = submissions.find((s) => s.id === id);
            return (
              <span
                key={id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-600/20 text-purple-300 border border-purple-600/40"
              >
                {sub?.display_name || `#${id}`}
                <button onClick={() => remove(id)} className="hover:text-purple-100">
                  <X className="w-3 h-3" />
                </button>
              </span>
            );
          })}
          {selectedIds.length < 6 && (
            <SubmissionPicker
              submissions={submissions}
              selectedIds={selectedIds}
              onSelect={toggle}
            />
          )}
        </div>
        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading results...
          </div>
        )}
      </div>

      {details.length < 2 && !loading && (
        <p className="text-sm text-slate-500">Select at least 2 submissions to compare.</p>
      )}

      {/* Comparison table */}
      {comparisonTable && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-slate-50 mb-4">Metrics Comparison</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400">
                  <th className="text-left py-3 px-3">Metric</th>
                  {comparisonTable.headers.map((h, i) => (
                    <th key={i} className="text-right py-3 px-3">
                      <span style={{ color: COLORS[i % COLORS.length] }}>{h}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonTable.rows.map((row) => (
                  <tr key={row.label} className="border-b border-slate-800">
                    <td className="py-2 px-3 text-slate-300">{row.label}</td>
                    {row.values.map((v, i) => (
                      <td key={i} className="py-2 px-3 text-right font-mono text-slate-50">
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Overlay training curves */}
      {overlayData && overlayData.opponents.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-lg font-semibold text-slate-50">Training Curves</h2>
            <div className="flex gap-1 bg-slate-800 p-0.5 rounded-md">
              {(["accuracy", "loss"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMetric(m)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    metric === m
                      ? "bg-blue-600/20 text-blue-400"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {m.charAt(0).toUpperCase() + m.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {overlayData.opponents.map((opp) => (
            <div key={opp} className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-4">
              <p className="text-xs text-slate-400 mb-3">
                vs {opp.replace("__none__", "none").replace("baseline_", "")}
              </p>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={overlayData.charts[opp]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="round" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    domain={metric === "accuracy" ? [0, 1] : ["auto", "auto"]}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "6px" }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Legend />
                  {details.map((d, i) => (
                    <Line
                      key={d.id}
                      type="monotone"
                      dataKey={`sub_${d.id}`}
                      name={d.display_name}
                      stroke={COLORS[i % COLORS.length]}
                      strokeWidth={1.5}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      )}

      {/* Per-opponent comparison */}
      {comparisonTable && comparisonTable.opponentRows.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-slate-50 mb-4">Per-Opponent Accuracy</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400">
                  <th className="text-left py-3 px-3">Opponent</th>
                  {comparisonTable.headers.map((h, i) => (
                    <th key={i} className="text-right py-3 px-3">
                      <span style={{ color: COLORS[i % COLORS.length] }}>{h}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonTable.opponentRows.map((row) => (
                  <tr key={row.opponent} className="border-b border-slate-800">
                    <td className="py-2 px-3 font-mono text-xs text-slate-300">
                      {row.opponent.replace("__none__", "none").replace("baseline_", "")}
                    </td>
                    {row.values.map((v, i) => (
                      <td key={i} className="py-2 px-3 text-right font-mono text-slate-50">
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function SubmissionPicker({
  submissions,
  selectedIds,
  onSelect,
}: {
  submissions: Submission[];
  selectedIds: number[];
  onSelect: (id: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const available = submissions.filter((s) => !selectedIds.includes(s.id));

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
      >
        <Plus className="w-3 h-3" /> Add
      </button>
    );
  }

  return (
    <div className="relative">
      <div className="absolute top-0 left-0 z-10 w-64 max-h-48 overflow-y-auto bg-slate-800 border border-slate-700 rounded-lg shadow-xl">
        <div className="p-2">
          {available.length === 0 ? (
            <p className="text-xs text-slate-500 p-2">No more completed submissions</p>
          ) : (
            available.map((s) => (
              <button
                key={s.id}
                onClick={() => { onSelect(s.id); setOpen(false); }}
                className="w-full text-left px-3 py-2 rounded-md text-sm hover:bg-slate-700 transition-colors"
              >
                <span className="text-slate-200">{s.display_name}</span>
                <span className={`ml-2 text-xs ${s.role === "attack" ? "text-red-400" : "text-green-400"}`}>
                  {s.role}
                </span>
              </button>
            ))
          )}
        </div>
        <div className="border-t border-slate-700 p-1">
          <button
            onClick={() => setOpen(false)}
            className="w-full text-center text-xs text-slate-400 py-1 hover:text-slate-200"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

type ExtractFn = (d: SubmissionDetail) => Record<string, OpponentResult> | null;

interface ComparisonData {
  headers: string[];
  rows: { label: string; values: string[] }[];
  opponentRows: { opponent: string; values: string[] }[];
}

function buildComparisonTable(details: SubmissionDetail[], extractResults: ExtractFn): ComparisonData {
  const headers = details.map((d) => d.display_name);

  const metricDefs: { label: string; key: string; fmt: (v: number) => string }[] = [
    { label: "Role", key: "_role", fmt: () => "" },
    { label: "Avg Accuracy", key: "avg_accuracy", fmt: (v) => v.toFixed(4) },
    { label: "Accuracy Drop", key: "avg_accuracy_drop", fmt: (v) => v.toFixed(4) },
    { label: "Worst Case", key: "worst_case_accuracy", fmt: (v) => v.toFixed(4) },
    { label: "Best Case", key: "best_case_accuracy", fmt: (v) => v.toFixed(4) },
    { label: "Convergence", key: "avg_convergence_speed", fmt: (v) => `${Math.round(v)}r` },
    { label: "Stability", key: "avg_stability", fmt: (v) => v.toFixed(4) },
  ];

  const rows = metricDefs.map((m) => ({
    label: m.label,
    values: details.map((d) => {
      if (m.key === "_role") return d.role;
      const results = extractResults(d);
      const summary = results?.["__summary__"] as Record<string, number> | undefined;
      const val = summary?.[m.key];
      return val != null ? m.fmt(val) : "-";
    }),
  }));

  const allOpponents = new Set<string>();
  for (const d of details) {
    const results = extractResults(d);
    if (results) {
      for (const k of Object.keys(results)) {
        if (k !== "__summary__") allOpponents.add(k);
      }
    }
  }

  const opponentRows = [...allOpponents].sort().map((opp) => ({
    opponent: opp,
    values: details.map((d) => {
      const results = extractResults(d);
      const r = results?.[opp] as OpponentResult | undefined;
      return r?.avg_final_accuracy != null ? r.avg_final_accuracy.toFixed(4) : "-";
    }),
  }));

  return { headers, rows, opponentRows };
}

function buildOverlayChart(
  details: SubmissionDetail[],
  extractResults: ExtractFn,
  metric: "accuracy" | "loss",
): { opponents: string[]; charts: Record<string, Record<string, number | string>[]> } {
  const allOpponents = new Set<string>();
  for (const d of details) {
    const results = extractResults(d);
    if (results) {
      for (const k of Object.keys(results)) {
        if (k !== "__summary__") allOpponents.add(k);
      }
    }
  }

  const charts: Record<string, Record<string, number | string>[]> = {};

  for (const opp of allOpponents) {
    let maxRounds = 0;
    const trajBySubmission: { id: number; traj: number[] }[] = [];

    for (const d of details) {
      const results = extractResults(d);
      const oppData = results?.[opp] as OpponentResult | undefined;
      const seed0 = oppData?.per_seed?.[0];
      const traj = metric === "accuracy" ? seed0?.accuracy_trajectory : seed0?.loss_trajectory;
      if (traj && traj.length > 0) {
        trajBySubmission.push({ id: d.id, traj });
        maxRounds = Math.max(maxRounds, traj.length);
      }
    }

    if (trajBySubmission.length < 2) continue;

    const data: Record<string, number | string>[] = [];
    for (let i = 0; i < maxRounds; i++) {
      const point: Record<string, number | string> = { round: i + 1 };
      for (const { id, traj } of trajBySubmission) {
        if (i < traj.length && traj[i] != null) {
          point[`sub_${id}`] = Number(traj[i].toFixed(4));
        }
      }
      data.push(point);
    }
    charts[opp] = data;
  }

  return { opponents: Object.keys(charts), charts };
}
