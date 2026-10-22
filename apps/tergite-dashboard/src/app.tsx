import { AppStateContext, useRootAppState } from "./lib/app-state";
import { AppRouter } from "./router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter } from "react-router-dom";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

const queryClient = new QueryClient();

export function App({ routerConstructor = createBrowserRouter }: Props) {
  const state = useRootAppState();

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
