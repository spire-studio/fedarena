import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { MatrixData, LeaderboardEntry } from "../api/client";

interface MatrixProps {
  compareEntry?: LeaderboardEntry | null;
  onClearCompare?: () => void;
}

export default function Matrix({ compareEntry, onClearCompare }: MatrixProps) {
  const [data, setData] = useState<MatrixData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getMatrix()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-slate-400">Loading matrix...</p>;
  if (error) return <p className="text-red-400">{error}</p>;
  if (!data) return null;

  const { attacks, defenses, matrix } = data;

  // Build display lists, injecting the compare entry as an extra row/column
  const displayAttacks = [...attacks];
  const displayDefenses = [...defenses];
  const augmentedMatrix: Record<string, Record<string, number | null>> = {};

  // Copy baseline matrix
  for (const atk of attacks) {
    augmentedMatrix[atk] = {};
    for (const def of defenses) {
      augmentedMatrix[atk][def] = matrix[atk]?.[def]?.avg_final_accuracy ?? null;
    }
  }

  // Inject compare entry
  if (compareEntry) {
    const scores = compareEntry.opponent_scores;
    if (compareEntry.role === "attack") {
      // Add as extra row
      const key = compareEntry.method_name;
      if (!displayAttacks.includes(key)) displayAttacks.push(key);
      augmentedMatrix[key] = {};
      for (const def of defenses) {
        augmentedMatrix[key][def] = scores[def] ?? null;
      }
    } else {
      // Add as extra column
      const key = compareEntry.method_name;
      if (!displayDefenses.includes(key)) displayDefenses.push(key);
      for (const atk of attacks) {
        augmentedMatrix[atk][key] = scores[atk] ?? null;
      }
    }
  }

  // Color scaling across all values
  const allAccs: number[] = [];
  for (const atk of displayAttacks) {
    for (const def of displayDefenses) {
      const val = augmentedMatrix[atk]?.[def];
      if (val != null) allAccs.push(val);
    }
  }
  const minAcc = allAccs.length ? Math.min(...allAccs) : 0;
  const maxAcc = allAccs.length ? Math.max(...allAccs) : 1;

  const isCompareRow = (atk: string) => compareEntry?.role === "attack" && atk === compareEntry.method_name;
  const isCompareCol = (def: string) => compareEntry?.role === "defense" && def === compareEntry.method_name;

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        Baseline attack x defense accuracy. Green = high (defense wins), Red = low (attack wins).
      </p>

      {compareEntry && (
        <div className="flex items-center gap-2 mb-4 p-2 bg-purple-900/20 border border-purple-700/40 rounded-lg text-sm">
          <span className="text-purple-300">
            Comparing: <span className="font-medium">{compareEntry.display_name}</span> ({compareEntry.role})
          </span>
          <button
            onClick={onClearCompare}
            className="ml-auto text-xs text-slate-400 hover:text-slate-50 px-2 py-0.5 bg-slate-700 rounded"
          >
            Clear
          </button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="text-sm border-collapse">
          <thead>
            <tr>
              <th className="py-2 px-3 text-left text-slate-400 font-medium border-b border-slate-700">
                Attack \ Defense
              </th>
              {displayDefenses.map((def) => (
                <th
                  key={def}
                  className={`py-2 px-3 text-center font-medium border-b border-slate-700 whitespace-nowrap ${
                    isCompareCol(def) ? "text-purple-300 bg-purple-900/10" : "text-slate-400"
                  }`}
                >
                  {formatName(def)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayAttacks.map((atk) => (
              <tr key={atk} className={isCompareRow(atk) ? "bg-purple-900/10" : ""}>
                <td className={`py-2 px-3 font-medium border-b border-slate-800 whitespace-nowrap ${
                  isCompareRow(atk) ? "text-purple-300" : "text-slate-300"
                }`}>
                  {formatName(atk)}
                </td>
                {displayDefenses.map((def) => {
                  const val = augmentedMatrix[atk]?.[def];
                  const highlight = isCompareRow(atk) || isCompareCol(def);
                  return (
                    <td
                      key={def}
                      className={`py-2 px-3 text-center font-mono text-xs border-b border-slate-800 ${
                        highlight ? "font-semibold" : ""
                      }`}
                      style={{
                        backgroundColor: val != null ? accColor(val, minAcc, maxAcc) : undefined,
                        ...(highlight ? { outline: "1px solid rgba(168,85,247,0.3)" } : {}),
                      }}
                    >
                      {val != null ? val.toFixed(4) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-4 mt-6 text-xs text-slate-500">
        <span>Color scale:</span>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: "rgba(239,68,68,0.3)" }} />
          <span>Low accuracy (attack wins)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: "rgba(34,197,94,0.3)" }} />
          <span>High accuracy (defense wins)</span>
        </div>
      </div>
    </div>
  );
}

function formatName(name: string) {
  return name
    .replace("__none__", "none")
    .replace("baseline_", "")
    .replace("arena_attack_", "")
    .replace("arena_defense_", "");
}

function accColor(val: number, min: number, max: number): string {
  const range = max - min || 1;
  const t = (val - min) / range;
  const r = Math.round(239 * (1 - t) + 34 * t);
  const g = Math.round(68 * (1 - t) + 197 * t);
  const b = Math.round(68 * (1 - t) + 94 * t);
  return `rgba(${r},${g},${b},0.2)`;
}
