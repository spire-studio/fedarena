import { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { BenchJob } from "../api/client";

interface BenchContextValue {
  prompt: string;
  setPrompt: (v: string) => void;
  submitting: boolean;
  error: string | null;
  activeJob: BenchJob | null;
  history: BenchJob[];
  submit: () => Promise<void>;
  refreshHistory: () => void;
}

const BenchContext = createContext<BenchContextValue | null>(null);

export function BenchProvider({ children }: { children: ReactNode }) {
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<BenchJob | null>(null);
  const [history, setHistory] = useState<BenchJob[]>([]);

  const refreshHistory = useCallback(() => {
    api.listBenchJobs().then(setHistory).catch(() => {});
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    if (!activeJob || activeJob.status === "completed" || activeJob.status === "failed") return;
    const interval = setInterval(() => {
      api.getBenchJob(activeJob.id).then((j) => {
        setActiveJob(j);
        if (j.status === "completed" || j.status === "failed") {
          refreshHistory();
        }
      });
    }, 2000);
    return () => clearInterval(interval);
  }, [activeJob, refreshHistory]);

  const submit = useCallback(async () => {
    if (!prompt.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const job = await api.createBenchJob(prompt.trim());
      setActiveJob(job);
      setPrompt("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }, [prompt]);

  return (
    <BenchContext.Provider
      value={{ prompt, setPrompt, submitting, error, activeJob, history, submit, refreshHistory }}
    >
      {children}
    </BenchContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useBench() {
  const ctx = useContext(BenchContext);
  if (!ctx) throw new Error("useBench must be used within BenchProvider");
  return ctx;
}
