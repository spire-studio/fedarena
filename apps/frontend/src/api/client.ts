const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ──────────────────────────────────────────────────

export interface Submission {
  id: number;
  method_name: string;
  role: string;
  display_name: string;
  author: string | null;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SubmissionDetail extends Submission {
  code: string;
  job_id: number | null;
  results: Record<string, OpponentResult> | null;
  error: string | null;
}

export interface SeedResult {
  seed: number;
  final_accuracy: number | null;
  error?: string | null;
  rounds?: number[];
  accuracy_trajectory?: number[];
  loss_trajectory?: number[];
}

export interface OpponentResult {
  avg_final_accuracy: number | null;
  per_seed: SeedResult[];
}

export interface LeaderboardEntry {
  rank: number;
  submission_id: number;
  method_name: string;
  display_name: string;
  author: string | null;
  role: string;
  avg_accuracy: number;
  opponent_scores: Record<string, number | null>;
  submitted_at: string;
}

export interface JobProgress {
  id: number;
  submission_id: number;
  status: string;
  progress: string | null;
  total_opponents: number;
  completed_opponents: number;
  current_opponent: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface MatrixData {
  attacks: string[];
  defenses: string[];
  matrix: Record<string, Record<string, { avg_final_accuracy: number | null }>>;
  config: string | null;
  seeds: number[] | null;
}

export interface AgentConfig {
  has_api_key: boolean;
  model: string;
  api_base: string;
}

export interface PromptResponse {
  submission: SubmissionDetail;
  generated_code: string;
}

export interface GenerateResponse {
  code: string;
  role: string;
  method_name: string;
  class_name: string;
  display_name: string;
  description: string;
}

export interface Draft {
  id: number;
  prompt: string;
  status: string;
  code: string | null;
  role: string | null;
  display_name: string | null;
  description: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchExperiment {
  name: string;
  attack_method: string | null;
  defense_method: string | null;
}

export interface BenchJob {
  id: number;
  prompt: string;
  plan_summary: string | null;
  status: string;
  experiments: BenchExperiment[];
  results: BenchResult[] | null;
  total_experiments: number;
  completed_experiments: number;
  current_experiment: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface BenchResult {
  name: string;
  attack_method: string | null;
  defense_method: string | null;
  final_accuracy: number | null;
  final_loss: number | null;
  error: string | null;
}

// ── API functions ──────────────────────────────────────────

export const api = {
  // Submissions
  createSubmission: (data: {
    code: string;
    role: string;
    display_name: string;
    author?: string;
    description?: string;
  }) => request<SubmissionDetail>("/submissions", {
    method: "POST",
    body: JSON.stringify(data),
  }),

  listSubmissions: (role?: string) =>
    request<Submission[]>(`/submissions${role ? `?role=${role}` : ""}`),

  getSubmission: (id: number) =>
    request<SubmissionDetail>(`/submissions/${id}`),

  getSubmissionReportUrl: (id: number) => `${BASE}/submissions/${id}/report`,

  deleteSubmission: (id: number) =>
    request<void>(`/submissions/${id}`, { method: "DELETE" }),

  // Leaderboard
  getLeaderboard: (role: string) =>
    request<LeaderboardEntry[]>(`/leaderboard?role=${role}`),

  // Matrix
  getMatrix: () => request<MatrixData>("/matrix"),

  // Jobs
  getJobProgress: (jobId: number) =>
    request<JobProgress>(`/jobs/${jobId}/progress`),

  // Agent
  getAgentConfig: () =>
    request<AgentConfig>("/agent/config"),

  updateAgentConfig: (data: { api_key?: string; api_base?: string; model?: string }) =>
    request<AgentConfig>("/agent/config", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  generateCode: (prompt: string) =>
    request<GenerateResponse>("/agent/generate", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),

  submitPrompt: (prompt: string) =>
    request<PromptResponse>("/agent/prompt", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),

  // Bench
  createBenchJob: (prompt: string) =>
    request<BenchJob>("/bench", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),

  getBenchJob: (id: number) => request<BenchJob>(`/bench/${id}`),

  listBenchJobs: () => request<BenchJob[]>("/bench"),
};
