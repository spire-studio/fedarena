import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { api } from "../api/client";
import type { MatrixData, MatrixCellData, LeaderboardEntry } from "../api/client";

interface MatrixProps {
  compareEntry?: LeaderboardEntry | null;
  onClearCompare?: () => void;
  scenario?: string;
}

interface SelectedCell {
  attack: string;
  defense: string;
  cell: MatrixCellData;
}

export default function Matrix({ compareEntry, onClearCompare, scenario }: MatrixProps) {
  const [data, setData] = useState<MatrixData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SelectedCell | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetching pattern
    setLoading(true);
    setError(null);
    api
      .getMatrix(scenario)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [scenario]);

  if (loading) return <p className="text-slate-400">Loading matrix...</p>;
  if (error) return <p className="text-red-400">{error}</p>;
  if (!data) return null;

  const { attacks, defenses, matrix } = data;

  const displayAttacks = [...attacks];
  const displayDefenses = [...defenses];
  const augmentedMatrix: Record<string, Record<string, number | null>> = {};

  for (const atk of attacks) {
    augmentedMatrix[atk] = {};
    for (const def of defenses) {
      augmentedMatrix[atk][def] = matrix[atk]?.[def]?.avg_final_accuracy ?? null;
    }
  }

  if (compareEntry) {
    const scores = compareEntry.opponent_scores;
    if (compareEntry.role === "attack") {
      const key = compareEntry.method_name;
      if (!displayAttacks.includes(key)) displayAttacks.push(key);
      augmentedMatrix[key] = {};
      for (const def of defenses) {
        augmentedMatrix[key][def] = scores[def] ?? null;
      }
    } else {
      const key = compareEntry.method_name;
      if (!displayDefenses.includes(key)) displayDefenses.push(key);
      for (const atk of attacks) {
        augmentedMatrix[atk][key] = scores[atk] ?? null;
      }
    }
  }

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

  const handleCellClick = (atk: string, def: string) => {
    const cell = matrix[atk]?.[def];
    if (cell) setSelected({ attack: atk, defense: def, cell });
  };

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        Baseline attack x defense accuracy. Click a cell for details. Green = high, Red = low.
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
                  const isBaseline = matrix[atk]?.[def] != null;
                  const isSelected = selected?.attack === atk && selected?.defense === def;
                  return (
                    <td
                      key={def}
                      onClick={() => isBaseline && handleCellClick(atk, def)}
                      className={`py-2 px-3 text-center font-mono text-xs border-b border-slate-800 ${
                        highlight ? "font-semibold" : ""
                      } ${isBaseline ? "cursor-pointer hover:ring-1 hover:ring-blue-500/50" : ""} ${
                        isSelected ? "ring-2 ring-blue-400" : ""
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

      {/* Cell detail panel */}
      {selected && (
        <CellDetail cell={selected} onClose={() => setSelected(null)} />
      )}

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

function CellDetail({ cell, onClose }: { cell: SelectedCell; onClose: () => void }) {
  const { attack, defense, cell: data } = cell;
  const seeds = data.per_seed || [];

  return (
    <div className="mt-4 bg-slate-800 border border-slate-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-50">
          {formatName(attack)} vs {formatName(defense)}
        </h3>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-slate-900 rounded-md p-3">
          <p className="text-xs text-slate-500">Avg Accuracy</p>
          <p className="text-lg font-mono font-bold text-slate-50">
            {data.avg_final_accuracy != null ? data.avg_final_accuracy.toFixed(4) : "—"}
          </p>
        </div>
        <div className="bg-slate-900 rounded-md p-3">
          <p className="text-xs text-slate-500">Seeds Succeeded</p>
          <p className="text-lg font-mono font-bold text-slate-50">
            {data.seeds_succeeded ?? seeds.length} / {seeds.length}
          </p>
        </div>
      </div>

      {seeds.length > 0 && (
        <div>
          <p className="text-xs text-slate-500 mb-2">Per-Seed Results</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="text-left py-1.5 px-2">Seed</th>
                <th className="text-right py-1.5 px-2">Accuracy</th>
                <th className="text-left py-1.5 px-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {seeds.map((s) => (
                <tr key={s.seed} className="border-b border-slate-800">
                  <td className="py-1.5 px-2 font-mono text-slate-300">{s.seed}</td>
                  <td className="py-1.5 px-2 text-right font-mono text-slate-50">
                    {s.final_accuracy != null ? s.final_accuracy.toFixed(4) : "—"}
                  </td>
                  <td className="py-1.5 px-2">
                    {s.error ? (
                      <span className="text-red-400" title={s.error}>FAIL</span>
                    ) : s.final_accuracy != null ? (
                      <span className="text-green-400">OK</span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {seeds.length > 1 && (() => {
            const accs = seeds.map(s => s.final_accuracy).filter((v): v is number => v != null);
            if (accs.length < 2) return null;
            const mean = accs.reduce((a, b) => a + b, 0) / accs.length;
            const std = Math.sqrt(accs.reduce((s, v) => s + (v - mean) ** 2, 0) / (accs.length - 1));
            return (
              <p className="text-xs text-slate-500 mt-2">
                Std: {std.toFixed(4)} | Range: [{Math.min(...accs).toFixed(4)}, {Math.max(...accs).toFixed(4)}]
              </p>
            );
          })()}
        </div>
      )}
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
