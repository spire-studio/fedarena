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
  method_group: string | null;
  version: number | null;
  created_at: string;
  updated_at: string;
}

export interface SubmissionDetail extends Submission {
  code: string;
  job_id: number | null;
  results: Record<string, unknown> | null;
  error: string | null;
}

export interface SeedResult {
  seed: number;
  final_accuracy: number | null;
  error?: string | null;
  rounds?: number[];
  accuracy_trajectory?: number[];
  loss_trajectory?: number[];
  max_accuracy?: number | null;
  convergence_speed?: number | null;
  stability?: number | null;
  runtime_seconds?: number | null;
}

export interface OpponentResult {
  avg_final_accuracy: number | null;
  accuracy_drop?: number | null;
  baseline_accuracy?: number | null;
  max_accuracy?: number | null;
  avg_convergence_speed?: number | null;
  avg_stability?: number | null;
  avg_runtime_seconds?: number | null;
  std_final_accuracy?: number | null;
  per_seed: SeedResult[];
}

export interface ResultsSummary {
  avg_accuracy?: number;
  avg_accuracy_drop?: number;
  worst_case_accuracy?: number;
  best_case_accuracy?: number;
  avg_convergence_speed?: number;
  avg_stability?: number;
  avg_runtime_seconds?: number;
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
  avg_accuracy_drop?: number | null;
  worst_case_accuracy?: number | null;
  avg_convergence_speed?: number | null;
  avg_stability?: number | null;
  version?: number | null;
  has_older_versions?: boolean;
}

export interface VersionInfo {
  id: number;
  version: number;
  method_name: string;
  display_name: string;
  status: string;
  avg_accuracy: number | null;
  created_at: string;
}

export interface AnalysisResponse {
  analysis: string;
  cached: boolean;
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

export interface MatrixCellData {
  avg_final_accuracy: number | null;
  per_seed?: { seed: number; final_accuracy: number | null; error?: string | null }[];
  seeds_succeeded?: number;
}

export interface MatrixData {
  attacks: string[];
  defenses: string[];
  matrix: Record<string, Record<string, MatrixCellData>>;
  config: string | null;
  seeds: number[] | null;
  scenario_id: string | null;
}

export interface ScenarioInfo {
  id: string;
  name: string;
  description: string;
  has_matrix: boolean;
  is_default: boolean;
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
  created_at: string | null;
}

export interface BenchResult {
  name: string;
  attack_method: string | null;
  defense_method: string | null;
  final_accuracy: number | null;
  final_loss: number | null;
  error: string | null;
}

export interface TopMethod {
  submission_id: number;
  display_name: string;
  method_name: string;
  author: string | null;
  avg_accuracy: number;
}

export interface DashboardData {
  total_submissions: number;
  completed_evaluations: number;
  failed_evaluations: number;
  active_jobs: number;
  queue_pending: number;
  top_attack: TopMethod | null;
  top_defense: TopMethod | null;
  recent_submissions: {
    id: number;
    display_name: string;
    method_name: string;
    role: string;
    status: string;
    created_at: string;
  }[];
}

export interface JobListItem {
  id: number;
  job_type: "evaluation" | "bench";
  status: string;
  label: string;
  submission_id: number | null;
  progress: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// ── API functions ──────────────────────────────────────────

export const api = {
  // Dashboard
  getDashboard: () => request<DashboardData>("/dashboard"),

  // Submissions
  createSubmission: (data: {
    code: string;
    role: string;
    display_name: string;
    author?: string;
    description?: string;
    num_seeds?: number;
    update_existing?: boolean;
  }) => request<SubmissionDetail>("/submissions", {
    method: "POST",
    body: JSON.stringify(data),
  }),

  listSubmissions: (role?: string) =>
    request<Submission[]>(`/submissions${role ? `?role=${role}` : ""}`),

  getSubmission: (id: number) =>
    request<SubmissionDetail>(`/submissions/${id}`),

  getSubmissionReportUrl: (id: number) => `${BASE}/submissions/${id}/report`,

  getVersions: (id: number) =>
    request<VersionInfo[]>(`/submissions/${id}/versions`),

  deleteSubmission: (id: number) =>
    request<void>(`/submissions/${id}`, { method: "DELETE" }),

  // Analysis
  getAnalysis: (submissionId: number, regenerate?: boolean) =>
    request<AnalysisResponse>(
      `/submissions/${submissionId}/analysis${regenerate ? "?regenerate=true" : ""}`
    ),

  // Scenarios
  getScenarios: () => request<ScenarioInfo[]>("/scenarios"),

  // Leaderboard
  getLeaderboard: (role: string, sortBy?: string, scenario?: string, showAllVersions?: boolean) =>
    request<LeaderboardEntry[]>(
      `/leaderboard?role=${role}${sortBy ? `&sort_by=${sortBy}` : ""}${scenario ? `&scenario=${scenario}` : ""}${showAllVersions ? "&show_all_versions=true" : ""}`
    ),

  // Matrix
  getMatrix: (scenario?: string) =>
    request<MatrixData>(`/matrix${scenario ? `?scenario=${scenario}` : ""}`),

  // Jobs
  listJobs: () => request<JobListItem[]>("/jobs"),

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
