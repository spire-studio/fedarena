import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ScenarioInfo } from "../api/client";

interface Props {
  value: string;
  onChange: (id: string) => void;
}

export default function ScenarioSelector({ value, onChange }: Props) {
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);

  useEffect(() => {
    api.getScenarios().then(setScenarios).catch(() => {});
  }, []);

  if (scenarios.length === 0) return null;

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-slate-800 border border-slate-700 text-slate-300 text-xs rounded px-2 py-1"
    >
      {scenarios.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name}{!s.has_matrix ? " (no data)" : ""}
        </option>
      ))}
    </select>
  );
}
