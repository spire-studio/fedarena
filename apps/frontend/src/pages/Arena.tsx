import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as Tabs from "@radix-ui/react-tabs";
import { Swords, Bot, Upload, Loader2, CheckCircle, XCircle, Clock, ArrowUpRight } from "lucide-react";
import { api } from "../api/client";
import type { Submission } from "../api/client";
import Agent from "./Agent";
import Submit from "./Submit";

export default function Arena() {
  const [mode, setMode] = useState("prompt");
  const [submissions, setSubmissions] = useState<Submission[]>([]);

  const fetchSubmissions = () => {
    api.listSubmissions().then(setSubmissions).catch(() => {});
  };

  useEffect(() => {
    fetchSubmissions();
    const interval = setInterval(fetchSubmissions, 5000);
    return () => clearInterval(interval);
  }, []);

  const active = submissions.filter((s) => s.status === "evaluating" || s.status === "pending");
  const recent = submissions
    .filter((s) => s.status !== "evaluating" && s.status !== "pending")
    .slice(0, 5);

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <Swords className="w-6 h-6 text-red-400" />
        <h1 className="text-2xl font-bold text-slate-50">Arena</h1>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Submit an attack or defense algorithm to be ranked against the benchmark matrix.
      </p>

      <Tabs.Root value={mode} onValueChange={setMode}>
        <Tabs.List className="flex gap-1 mb-6 bg-slate-800 p-1 rounded-lg w-fit">
          <Tabs.Trigger
            value="prompt"
            className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors data-[state=active]:bg-purple-600/20 data-[state=active]:text-purple-400 text-slate-400 hover:text-slate-200"
          >
            <Bot className="w-4 h-4" />
            Prompt Mode
          </Tabs.Trigger>
          <Tabs.Trigger
            value="upload"
            className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors data-[state=active]:bg-blue-600/20 data-[state=active]:text-blue-400 text-slate-400 hover:text-slate-200"
          >
            <Upload className="w-4 h-4" />
            File Upload
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="prompt" forceMount className="data-[state=inactive]:hidden">
          <Agent />
        </Tabs.Content>
        <Tabs.Content value="upload" forceMount className="data-[state=inactive]:hidden">
          <Submit />
        </Tabs.Content>
      </Tabs.Root>

      {/* Active submissions */}
      {active.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm text-slate-400 mb-3">Running</h3>
          <div className="space-y-2">
            {active.map((s) => (
              <SubmissionRow key={s.id} submission={s} />
            ))}
          </div>
        </div>
      )}

      {/* Recent submissions */}
      {recent.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm text-slate-400 mb-3">Recent Submissions</h3>
          <div className="space-y-2">
            {recent.map((s) => (
              <SubmissionRow key={s.id} submission={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; cls: string }> = {
  evaluating: { icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />, cls: "text-blue-400" },
  pending: { icon: <Clock className="w-3.5 h-3.5" />, cls: "text-yellow-400" },
  completed: { icon: <CheckCircle className="w-3.5 h-3.5" />, cls: "text-green-400" },
  failed: { icon: <XCircle className="w-3.5 h-3.5" />, cls: "text-red-400" },
};

function SubmissionRow({ submission: s }: { submission: Submission }) {
  const cfg = STATUS_CONFIG[s.status] || STATUS_CONFIG.pending;
  return (
    <Link
      to={`/submissions/${s.id}`}
      className="flex items-center gap-3 px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg hover:border-slate-600 transition-colors group"
    >
      <span className={cfg.cls}>{cfg.icon}</span>
      <div className="flex-1 min-w-0">
        <span className="text-sm text-slate-50 font-medium">{s.display_name}</span>
        <span className="text-xs text-slate-500 ml-2">{s.role}</span>
      </div>
      <span className={`text-xs ${cfg.cls}`}>{s.status}</span>
      <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-slate-300 transition-colors" />
    </Link>
  );
}
