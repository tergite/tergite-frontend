import { create } from "zustand";
import { persist } from "zustand/middleware";

/** What is neither server data nor URL state */
export interface AppState {
  currentProjectId?: string;
  setCurrentProjectId: (value?: string) => void;
  apiToken?: string;
  setApiToken: (value?: string) => void;
  clear: () => void;
  isDark: boolean;
  toggleIsDark: () => void;
}

// only the theme outlives the page: an API token must never reach storage
export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentProjectId: undefined,
      setCurrentProjectId: (currentProjectId) => set({ currentProjectId }),
      apiToken: undefined,
      setApiToken: (apiToken) => set({ apiToken }),
      clear: () => set({ currentProjectId: undefined, apiToken: undefined }),
      isDark: false,
      toggleIsDark: () => set((state) => ({ isDark: !state.isDark })),
    }),
    { name: "app-state", partialize: (state) => ({ isDark: state.isDark }) },
  ),
);
