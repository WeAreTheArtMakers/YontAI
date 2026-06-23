import { create } from "zustand";

interface AppState {
  activeSection: string;
  setActiveSection: (section: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeSection: "Ana Panel",
  setActiveSection: (section) => set({ activeSection: section })
}));
