import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as Tabs from "@radix-ui/react-tabs";
import { Trophy, ArrowUpRight, LayoutGrid, GitCompareArrows } from "lucide-react";
import { api } from "../api/client";
import type { LeaderboardEntry, MatrixData } from "../api/client";
import ScenarioSelector from "../components/ScenarioSelector";
import Matrix from "./Matrix";

interface BaselineScore {
  name: string;
  avg_accuracy: number;
}

function computeBaselineScores(matrixData: MatrixData, role: "attack" | "defense"): BaselineScore[] {
  const { attacks, defenses, matrix } = matrixData;
  const scores: BaselineScore[] = [];

  if (role === "attack") {
    // Each attack row: avg across all defenses
    for (const atk of attacks) {
      if (atk === "__none__") continue;
      const accs: number[] = [];
      for (const def of defenses) {
        const val = matrix[atk]?.[def]?.avg_final_accuracy;
        if (val != null) accs.push(val);
      }
      if (accs.length) scores.push({ name: atk, avg_accuracy: accs.reduce((a, b) => a + b, 0) / accs.length });
    }
  } else {
    // Each defense column: avg across all attacks
    for (const def of defenses) {
      if (def === "__none__") continue;
      const accs: number[] = [];
      for (const atk of attacks) {
        const val = matrix[atk]?.[def]?.avg_final_accuracy;
        if (val != null) accs.push(val);
      }
      if (accs.length) scores.push({ name: def, avg_accuracy: accs.reduce((a, b) => a + b, 0) / accs.length });
    }
  }

  return scores;
}

export default function Leaderboard() {
  const [tab, setTab] = useState("attack");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [matrixData, setMatrixData] = useState<MatrixData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [compareEntry, setCompareEntry] = useState<LeaderboardEntry | null>(null);
  const [sortBy, setSortBy] = useState("avg_accuracy");
  const [scenario, setScenario] = useState("cifar10_noniid");
  const [showAllVersions, setShowAllVersions] = useState(false);

  const role = tab === "attack" || tab === "defense" ? tab : null;

  useEffect(() => {
    api.getMatrix(scenario).then(setMatrixData).catch(() => setMatrixData(null));
  }, [scenario]);

  useEffect(() => {
    if (!role) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetching pattern
    setLoading(true);
    setError(null);
    api
      .getLeaderboard(role, sortBy, scenario, showAllVersions)
      .then((data) => { if (!cancelled) setEntries(data); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [role, sortBy, scenario, showAllVersions]);

  // Merge baselines + submissions into unified ranking
  const mergedRanking = (() => {
    if (!role || !matrixData) return [];

    const baselines = computeBaselineScores(matrixData, role);
    const submissionNames = new Set(entries.map((e) => e.method_name));

    type RankRow = {
      rank: number;
      name: string;
      display_name: string;
      author: string | null;
      avg_accuracy: number;
      submitted_at: string | null;
      submission_id: number | null;
      is_baseline: boolean;
      entry: LeaderboardEntry | null;
    };

    const all: RankRow[] = [];

    // Add baselines not already in submissions
    for (const b of baselines) {
      if (!submissionNames.has(b.name)) {
        all.push({
          rank: 0,
          name: b.name,
          display_name: formatName(b.name),
          author: "baseline",
          avg_accuracy: b.avg_accuracy,
          submitted_at: null,
          submission_id: null,
          is_baseline: true,
          entry: null,
        });
      }
    }

    // Add submissions
    for (const e of entries) {
      all.push({
        rank: 0,
        name: e.method_name,
        display_name: e.display_name,
        author: e.author,
        avg_accuracy: e.avg_accuracy,
        submitted_at: e.submitted_at,
        submission_id: e.submission_id,
        is_baseline: false,
        entry: e,
      });
    }

    // Sort
    const reverse = role === "defense";
    all.sort((a, b) => reverse ? b.avg_accuracy - a.avg_accuracy : a.avg_accuracy - b.avg_accuracy);
    all.forEach((r, i) => (r.rank = i + 1));

    return all;
  })();

  const handleCompare = (entry: LeaderboardEntry) => {
    setCompareEntry(entry);
    setTab("matrix");
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <Trophy className="w-6 h-6 text-yellow-400" />
        <h1 className="text-2xl font-bold text-slate-50">Leaderboard</h1>
      </div>
      <div className="flex items-center gap-3 mb-6">
        <p className="text-sm text-slate-500">
          Rankings and baseline benchmark matrix.
        </p>
        <ScenarioSelector value={scenario} onChange={setScenario} />
      </div>

      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List className="flex gap-1 mb-6 bg-slate-800 p-1 rounded-lg w-fit">
          <Tabs.Trigger value="attack" className="px-4 py-2 rounded-md text-sm font-medium transition-colors data-[state=active]:bg-red-600/20 data-[state=active]:text-red-400 text-slate-400 hover:text-slate-200">
            Attack Ranking
          </Tabs.Trigger>
          <Tabs.Trigger value="defense" className="px-4 py-2 rounded-md text-sm font-medium transition-colors data-[state=active]:bg-green-600/20 data-[state=active]:text-green-400 text-slate-400 hover:text-slate-200">
            Defense Ranking
          </Tabs.Trigger>
          <Tabs.Trigger value="matrix" className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors data-[state=active]:bg-blue-600/20 data-[state=active]:text-blue-400 text-slate-400 hover:text-slate-200">
            <LayoutGrid className="w-3.5 h-3.5" />
            Baseline Matrix
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="matrix">
          <Matrix compareEntry={compareEntry} onClearCompare={() => setCompareEntry(null)} scenario={scenario} />
        </Tabs.Content>
      </Tabs.Root>

      {/* Ranking table */}
      {role && (
        <>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-slate-500">
              {role === "attack" ? "Lower avg accuracy = stronger attack" : "Higher avg accuracy = stronger defense"}
            </p>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showAllVersions}
                  onChange={(e) => setShowAllVersions(e.target.checked)}
                  className="accent-blue-500"
                />
                All versions
              </label>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Sort by:</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-slate-300 text-xs rounded px-2 py-1"
                >
                  <option value="avg_accuracy">Avg Accuracy</option>
                  <option value="avg_accuracy_drop">Accuracy Drop</option>
                  <option value="worst_case_accuracy">Worst Case</option>
                  <option value="avg_convergence_speed">Convergence</option>
                  <option value="avg_stability">Stability</option>
                </select>
              </div>
            </div>
          </div>

          {loading && <p className="text-slate-400">Loading...</p>}
          {error && <p className="text-red-400">{error}</p>}

          {!loading && mergedRanking.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="text-left py-3 px-3 w-12">#</th>
                    <th className="text-left py-3 px-3">Method</th>
                    <th className="text-left py-3 px-3">Author</th>
                    <th className="text-right py-3 px-3">Avg Acc</th>
                    <th className="text-right py-3 px-3">Acc Drop</th>
                    <th className="text-right py-3 px-3">Worst</th>
                    <th className="text-right py-3 px-3">Conv.</th>
                    <th className="text-right py-3 px-3">Stab.</th>
                    <th className="py-3 px-3 w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {mergedRanking.map((row) => (
                    <tr
                      key={row.name}
                      className={`border-b border-slate-800 transition-colors ${
                        row.is_baseline ? "opacity-60" : "hover:bg-slate-800/50"
                      }`}
                    >
                      <td className="py-3 px-3"><RankBadge rank={row.rank} /></td>
                      <td className="py-3 px-3">
                        <div className={`font-medium flex items-center gap-1.5 ${row.is_baseline ? "text-slate-400" : "text-slate-50"}`}>
                          {row.display_name}
                          {row.entry?.version && row.entry.version > 1 && (
                            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-amber-600/20 text-amber-400 border border-amber-600/40">
                              v{row.entry.version}
                            </span>
                          )}
                          {row.entry?.has_older_versions && (
                            <span className="text-[10px] text-slate-500" title="Has older versions">+</span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500 font-mono">{row.name}</div>
                      </td>
                      <td className="py-3 px-3 text-slate-400">
                        {row.is_baseline ? (
                          <span className="text-xs bg-slate-700 px-1.5 py-0.5 rounded">baseline</span>
                        ) : (
                          row.author || "-"
                        )}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-50">
                        {row.avg_accuracy.toFixed(4)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-400">
                        {row.entry?.avg_accuracy_drop != null ? row.entry.avg_accuracy_drop.toFixed(4) : "-"}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-400">
                        {row.entry?.worst_case_accuracy != null ? row.entry.worst_case_accuracy.toFixed(4) : "-"}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-400">
                        {row.entry?.avg_convergence_speed != null ? `${Math.round(row.entry.avg_convergence_speed)}r` : "-"}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-400">
                        {row.entry?.avg_stability != null ? row.entry.avg_stability.toFixed(4) : "-"}
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1">
                          {row.entry && (
                            <button
                              onClick={() => handleCompare(row.entry!)}
                              title="Compare in Matrix"
                              className="text-purple-400 hover:text-purple-300 p-1"
                            >
                              <GitCompareArrows className="w-4 h-4" />
                            </button>
                          )}
                          {row.submission_id && (
                            <Link to={`/submissions/${row.submission_id}`} className="text-blue-400 hover:text-blue-300 p-1">
                              <ArrowUpRight className="w-4 h-4" />
                            </Link>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function RankBadge({ rank }: { rank: number }) {
  const colors: Record<number, string> = {
    1: "bg-yellow-500/20 text-yellow-400",
    2: "bg-slate-400/20 text-slate-300",
    3: "bg-amber-700/20 text-amber-500",
  };
  const cls = colors[rank] || "bg-slate-800 text-slate-400";
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${cls}`}>
      {rank}
    </span>
  );
}

function formatName(name: string) {
  return name
    .replace("__none__", "none")
    .replace("baseline_", "")
    .replace("arena_attack_", "")
    .replace("arena_defense_", "");
}
