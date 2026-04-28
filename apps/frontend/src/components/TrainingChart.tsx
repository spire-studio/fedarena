import { useState } from "react";
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
import type { OpponentResult } from "../api/client";

interface Props {
  results: Record<string, OpponentResult>;
  role: string;
}

const COLORS = [
  "#818cf8", "#34d399", "#f87171", "#fbbf24", "#60a5fa",
  "#a78bfa", "#f472b6", "#2dd4bf", "#fb923c", "#94a3b8",
];

export default function TrainingChart({ results, role }: Props) {
  const opponents = Object.keys(results);
  const [selected, setSelected] = useState(opponents[0] || "");
  const [metric, setMetric] = useState<"accuracy" | "loss">("accuracy");

  const seedData = selected ? results[selected]?.per_seed || [] : [];
  const hasTrajectory = seedData.some((s) => s.accuracy_trajectory && s.accuracy_trajectory.length > 0);

  if (!hasTrajectory) return null;

  const chartData: Record<string, number | string>[] = [];
  const firstSeed = seedData.find((s) => s.rounds && s.rounds.length > 0);
  if (!firstSeed?.rounds) return null;

  for (let i = 0; i < firstSeed.rounds.length; i++) {
    const point: Record<string, number | string> = { round: firstSeed.rounds[i] };
    for (const s of seedData) {
      const traj = metric === "accuracy" ? s.accuracy_trajectory : s.loss_trajectory;
      if (traj && traj[i] != null) {
        point[`seed_${s.seed}`] = Number(traj[i].toFixed(4));
      }
    }
    chartData.push(point);
  }

  const singleSeed = seedData.length === 1;
  let comparisonData: Record<string, number | string>[] = [];
  if (singleSeed) {
    const refSeed = Object.values(results).find(
      (r) => r.per_seed[0]?.rounds?.length
    )?.per_seed[0];
    if (refSeed?.rounds) {
      comparisonData = refSeed.rounds.map((round, i) => {
        const point: Record<string, number | string> = { round };
        for (const [opp, res] of Object.entries(results)) {
          const traj =
            metric === "accuracy"
              ? res.per_seed[0]?.accuracy_trajectory
              : res.per_seed[0]?.loss_trajectory;
          if (traj && traj[i] != null) {
            point[opp] = Number(traj[i].toFixed(4));
          }
        }
        return point;
      });
    }
  }

  const label = (name: string) =>
    name.replace("__none__", "none").replace("baseline_", "");

  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-slate-50 mb-4">Training Curves</h2>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
        >
          {opponents.map((opp) => (
            <option key={opp} value={opp}>
              vs {label(opp)}
            </option>
          ))}
        </select>

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

        <span className="text-xs text-slate-500">
          {role === "attack" ? "Lower accuracy = stronger attack" : "Higher accuracy = stronger defense"}
        </span>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
        <p className="text-xs text-slate-400 mb-3">
          vs {label(selected)} — {metric} per round
          {seedData.length > 1 && ` (${seedData.length} seeds)`}
        </p>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis
              dataKey="round"
              stroke="#64748b"
              tick={{ fontSize: 11 }}
              label={{ value: "Round", position: "insideBottom", offset: -2, fill: "#64748b", fontSize: 11 }}
            />
            <YAxis
              stroke="#64748b"
              tick={{ fontSize: 11 }}
              domain={metric === "accuracy" ? [0, 1] : ["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "6px" }}
              labelStyle={{ color: "#94a3b8" }}
            />
            {seedData.length > 1 && <Legend />}
            {seedData.map((s, i) => (
              <Line
                key={s.seed}
                type="monotone"
                dataKey={`seed_${s.seed}`}
                name={`Seed ${s.seed}`}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={1.5}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {singleSeed && comparisonData.length > 0 && opponents.length > 1 && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mt-4">
          <p className="text-xs text-slate-400 mb-3">
            All opponents — {metric} per round
          </p>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey="round"
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                label={{ value: "Round", position: "insideBottom", offset: -2, fill: "#64748b", fontSize: 11 }}
              />
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
              {opponents.map((opp, i) => (
                <Line
                  key={opp}
                  type="monotone"
                  dataKey={opp}
                  name={label(opp)}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={opp === selected ? 2.5 : 1.2}
                  strokeOpacity={opp === selected ? 1 : 0.5}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
