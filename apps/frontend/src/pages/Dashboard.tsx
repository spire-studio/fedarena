import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  LayoutDashboard,
  Trophy,
  Swords,
  Shield,
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ArrowUpRight,
} from "lucide-react";
import { api } from "../api/client";
import type { DashboardData } from "../api/client";

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = () => {
      api.getDashboard().then(setData).catch(() => {});
      setLoading(false);
    };
    fetch();
    const interval = setInterval(fetch, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) return <p className="text-slate-400">Loading...</p>;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <LayoutDashboard className="w-6 h-6 text-blue-400" />
        <h1 className="text-2xl font-bold text-slate-50">Dashboard</h1>
      </div>

      {/* Stats cards */}
      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard
              label="Submissions"
              value={data.total_submissions}
              icon={<Trophy className="w-4 h-4 text-yellow-400" />}
            />
            <StatCard
              label="Completed"
              value={data.completed_evaluations}
              icon={<CheckCircle className="w-4 h-4 text-green-400" />}
            />
            <StatCard
              label="Failed"
              value={data.failed_evaluations}
              icon={<XCircle className="w-4 h-4 text-red-400" />}
            />
            <StatCard
              label="Active Jobs"
              value={data.active_jobs}
              icon={<Activity className="w-4 h-4 text-blue-400" />}
              extra={data.queue_pending > 0 ? `${data.queue_pending} queued` : undefined}
            />
          </div>

          {/* Top methods */}
          <div className="grid md:grid-cols-2 gap-4 mb-8">
            <TopMethodCard
              title="Best Attack"
              icon={<Swords className="w-4 h-4 text-red-400" />}
              method={data.top_attack}
              note="lower accuracy = stronger"
            />
            <TopMethodCard
              title="Best Defense"
              icon={<Shield className="w-4 h-4 text-blue-400" />}
              method={data.top_defense}
              note="higher accuracy = stronger"
            />
          </div>

          {/* Recent submissions */}
          <div>
            <h2 className="text-sm text-slate-400 mb-3">Recent Submissions</h2>
            {data.recent_submissions.length === 0 ? (
              <p className="text-sm text-slate-500">No submissions yet. Head to <Link to="/arena" className="text-blue-400 hover:underline">Arena</Link> to get started.</p>
            ) : (
              <div className="space-y-2">
                {data.recent_submissions.map((s) => (
                  <Link
                    key={s.id}
                    to={`/submissions/${s.id}`}
                    className="flex items-center gap-3 px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg hover:border-slate-600 transition-colors group"
                  >
                    <StatusIcon status={s.status} />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-slate-50 font-medium">{s.display_name}</span>
                      <span className="text-xs text-slate-500 ml-2">{s.role}</span>
                    </div>
                    <span className="text-xs text-slate-500">
                      <Clock className="w-3 h-3 inline mr-1" />
                      {new Date(s.created_at).toLocaleDateString()}
                    </span>
                    <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-slate-300 transition-colors" />
                  </Link>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, extra }: {
  label: string;
  value: number;
  icon: React.ReactNode;
  extra?: string;
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <p className="text-2xl font-bold text-slate-50">{value}</p>
      {extra && <p className="text-xs text-slate-500 mt-1">{extra}</p>}
    </div>
  );
}

function TopMethodCard({ title, icon, method, note }: {
  title: string;
  icon: React.ReactNode;
  method: DashboardData["top_attack"];
  note: string;
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <span className="text-sm text-slate-400">{title}</span>
      </div>
      {method ? (
        <Link to={`/submissions/${method.submission_id}`} className="group">
          <p className="text-lg font-semibold text-slate-50 group-hover:text-blue-400 transition-colors">
            {method.display_name}
          </p>
          <p className="text-xs text-slate-500 font-mono mt-0.5">{method.method_name}</p>
          {method.author && <p className="text-xs text-slate-500 mt-0.5">by {method.author}</p>}
          <p className="text-sm font-mono text-slate-300 mt-2">
            {method.avg_accuracy.toFixed(4)}
            <span className="text-xs text-slate-500 ml-1">({note})</span>
          </p>
        </Link>
      ) : (
        <p className="text-sm text-slate-500">No completed evaluations yet</p>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-3.5 h-3.5 text-green-400" />;
    case "failed":
      return <XCircle className="w-3.5 h-3.5 text-red-400" />;
    case "evaluating":
      return <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />;
    default:
      return <Clock className="w-3.5 h-3.5 text-yellow-400" />;
  }
}
