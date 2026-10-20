import { useCallback, useEffect, useState } from "react";
import { AppState } from "../types";
import { newAppState, AppStateContext } from "./lib/app-state";
import { AppRouter } from "./router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter } from "react-router-dom";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { getSavedIsDarkMode, saveIsDarkMode } from "./lib/utils";

const queryClient = new QueryClient();

export function App({ routerConstructor = createBrowserRouter }: Props) {
  const [currentProject, setCurrentProject] = useState<string>();
  const [apiToken, setApiToken] = useState<string>();
  const [isDark, _setIsDark] = useState<boolean>(getSavedIsDarkMode());
  const toggleIsDark = useCallback(
    () => _setIsDark(!isDark),
    [isDark, _setIsDark]
  );

  const state: AppState = {
    ...newAppState(),
    apiToken,
    setApiToken,
    isDark,
    toggleIsDark,
    currentProjectId: currentProject,
    setCurrentProjectId: setCurrentProject,
  };

  useEffect(() => {
    saveIsDarkMode(isDark);
  }, [isDark]);

  return (
    <QueryClientProvider client={queryClient}>
      <AppStateContext.Provider value={state}>
        <AppRouter routerConstructor={routerConstructor} />
      </AppStateContext.Provider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

interface Props {
  routerConstructor?: typeof createBrowserRouter;
}
