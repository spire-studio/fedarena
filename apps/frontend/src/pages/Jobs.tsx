import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  FlaskConical,
  Swords,
  ArrowUpRight,
} from "lucide-react";
import { api } from "../api/client";
import type { JobListItem } from "../api/client";

export default function Jobs() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = () => {
      api.listJobs().then(setJobs).catch(() => {});
      setLoading(false);
    };
    fetch();
    const interval = setInterval(fetch, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && jobs.length === 0) return <p className="text-slate-400">Loading...</p>;

  const active = jobs.filter((j) => j.status === "running" || j.status === "queued");
  const done = jobs.filter((j) => j.status !== "running" && j.status !== "queued");

  const grouped = groupByDate(done);

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Activity className="w-6 h-6 text-blue-400" />
        <h1 className="text-2xl font-bold text-slate-50">Jobs</h1>
      </div>

      {active.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm text-slate-400 mb-3">Active</h2>
          <div className="space-y-2">
            {active.map((j) => (
              <JobRow key={`${j.job_type}-${j.id}`} job={j} />
            ))}
          </div>
        </div>
      )}

      {done.length === 0 && active.length === 0 ? (
        <p className="text-sm text-slate-500">No jobs yet.</p>
      ) : (
        <div>
          {active.length > 0 && <h2 className="text-sm text-slate-400 mb-3">History</h2>}
          {grouped.map(([date, items]) => (
            <div key={date} className="mb-5">
              <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">{date}</h3>
              <div className="space-y-2">
                {items.map((j) => (
                  <JobRow key={`${j.job_type}-${j.id}`} job={j} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function groupByDate(jobs: JobListItem[]): [string, JobListItem[]][] {
  const map = new Map<string, JobListItem[]>();
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const todayStr = fmt(today);
  const yesterdayStr = fmt(yesterday);

  for (const job of jobs) {
    const dateStr = fmt(new Date(job.created_at));
    let label: string;
    if (dateStr === todayStr) label = "Today";
    else if (dateStr === yesterdayStr) label = "Yesterday";
    else label = new Date(job.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

    if (!map.has(label)) map.set(label, []);
    map.get(label)!.push(job);
  }
  return [...map.entries()];
}

function JobRow({ job }: { job: JobListItem }) {
  const link =
    job.job_type === "evaluation" && job.submission_id
      ? `/submissions/${job.submission_id}`
      : job.job_type === "bench"
        ? `/bench/${job.id}`
        : undefined;

  const content = (
    <div className="flex items-center gap-3 px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg hover:border-slate-600 transition-colors group">
      <StatusIcon status={job.status} />
      <TypeBadge type={job.job_type} />
      <div className="flex-1 min-w-0">
        <span className="text-sm text-slate-50 font-medium truncate block">{job.label}</span>
        {job.progress && (
          <span className="text-xs text-slate-500">{job.progress}</span>
        )}
        {job.error && (
          <span className="text-xs text-red-400 truncate block">{job.error}</span>
        )}
      </div>
      {link && <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-slate-300 transition-colors shrink-0" />}
    </div>
  );

  if (link) {
    return <Link to={link}>{content}</Link>;
  }
  return content;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-3.5 h-3.5 text-green-400 shrink-0" />;
    case "failed":
      return <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />;
    case "running":
      return <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin shrink-0" />;
    default:
      return <Clock className="w-3.5 h-3.5 text-yellow-400 shrink-0" />;
  }
}

function TypeBadge({ type }: { type: string }) {
  if (type === "evaluation") {
    return (
      <span className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 shrink-0">
        <Swords className="w-3 h-3" />
        Eval
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 shrink-0">
      <FlaskConical className="w-3 h-3" />
      Bench
    </span>
  );
}
