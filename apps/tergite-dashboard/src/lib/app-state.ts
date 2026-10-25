import { createContext, useCallback, useEffect, useState } from "react";
import { AppState } from "../../types";

export const AppStateContext = createContext<AppState>(newAppState());

/**
 * The app state owned by the root component, with setters that change it
 */
export function useRootAppState(): AppState {
  const [currentProjectId, setCurrentProjectId] = useState<string>();
  const [apiToken, setApiToken] = useState<string>();
  const [isDark, setIsDark] = useState<boolean>(getSavedIsDarkMode());
  const toggleIsDark = useCallback(() => setIsDark((value) => !value), []);
  const clear = useCallback(() => {
    setCurrentProjectId(undefined);
    setApiToken(undefined);
  }, []);

  useEffect(() => saveIsDarkMode(isDark), [isDark]);

  return {
    currentProjectId,
    setCurrentProjectId,
    apiToken,
    setApiToken,
    isDark,
    toggleIsDark,
    clear,
  };
}

/**
 * A factory function for generating app states to ensure immutability
 *
 * @returns new app state with proper initializations
 */
export function newAppState(): AppState {
  const state: AppState = {
    currentProjectId: undefined,
    setCurrentProjectId: () => {},
    apiToken: undefined,
    isDark: false,
    setApiToken: () => {},
    toggleIsDark: () => {},
    clear: () => {
      state.setCurrentProjectId(undefined);
      state.setApiToken(undefined);
    },
  };

  return state;
}

function getSavedIsDarkMode() {
  return localStorage.getItem("isDarkMode") == "true";
}

function saveIsDarkMode(isDarkMode: boolean) {
  localStorage.setItem("isDarkMode", `${isDarkMode}`);
  if (isDarkMode) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}
