import { create } from "zustand";

export type ViewMode = "chat" | "coding" | "agent";

interface ViewModeState {
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
}

export const useViewModeStore = create<ViewModeState>((set) => ({
  viewMode: "chat",
  setViewMode: (mode) => set({ viewMode: mode }),
}));