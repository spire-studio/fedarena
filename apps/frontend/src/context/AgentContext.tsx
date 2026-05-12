import { createContext, useContext, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";

type Phase = "idle" | "generating" | "review" | "submitting";

interface AgentState {
  prompt: string;
  phase: Phase;
  error: string | null;
  code: string;
  role: "attack" | "defense";
  displayName: string;
  description: string;
  numSeeds: number;
}

interface AgentContextValue extends AgentState {
  setPrompt: (v: string) => void;
  setPhase: (v: Phase) => void;
  setError: (v: string | null) => void;
  setCode: (v: string) => void;
  setRole: (v: "attack" | "defense") => void;
  setDisplayName: (v: string) => void;
  setDescription: (v: string) => void;
  setNumSeeds: (v: number) => void;
  generate: () => Promise<void>;
  reset: () => void;
}

const AgentContext = createContext<AgentContextValue | null>(null);

export function AgentProvider({ children }: { children: ReactNode }) {
  const [prompt, setPrompt] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [role, setRole] = useState<"attack" | "defense">("attack");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [numSeeds, setNumSeeds] = useState(0);

  const generate = useCallback(async () => {
    if (!prompt.trim()) return;
    setPhase("generating");
    setError(null);
    try {
      const result = await api.generateCode(prompt.trim());
      setCode(result.code);
      setRole(result.role as "attack" | "defense");
      setDisplayName(result.display_name);
      setDescription(result.description);
      setPhase("review");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("idle");
    }
  }, [prompt]);

  const reset = useCallback(() => {
    setPhase("idle");
    setError(null);
    setCode("");
    setDisplayName("");
    setDescription("");
    setNumSeeds(0);
  }, []);

  return (
    <AgentContext.Provider
      value={{
        prompt, setPrompt,
        phase, setPhase,
        error, setError,
        code, setCode,
        role, setRole,
        displayName, setDisplayName,
        description, setDescription,
        numSeeds, setNumSeeds,
        generate,
        reset,
      }}
    >
      {children}
    </AgentContext.Provider>
  );
}

export function useAgent() {
  const ctx = useContext(AgentContext);
  if (!ctx) throw new Error("useAgent must be used within AgentProvider");
  return ctx;
}
