import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

interface AgentModeContextValue {
  isAgentMode: boolean;
  setIsAgentMode: (v: boolean) => void;
  toggleAgentMode: () => void;
}

const AgentModeContext = createContext<AgentModeContextValue | null>(null);

const STORAGE_KEY = "qwenpaw_agent_mode";

export function AgentModeProvider({ children }: { children: ReactNode }) {
  const [isAgentMode, setIsAgentModeState] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored !== null ? stored === "true" : true;
    } catch {
      return true;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isAgentMode));
    } catch {}
  }, [isAgentMode]);

  const setIsAgentMode = (v: boolean) => setIsAgentModeState(v);
  const toggleAgentMode = () => setIsAgentModeState((prev) => !prev);

  return (
    <AgentModeContext.Provider value={{ isAgentMode, setIsAgentMode, toggleAgentMode }}>
      {children}
    </AgentModeContext.Provider>
  );
}

export function useAgentMode(): AgentModeContextValue {
  const ctx = useContext(AgentModeContext);
  if (!ctx) throw new Error("useAgentMode must be used inside AgentModeProvider");
  return ctx;
}
