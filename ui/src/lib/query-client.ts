import { QueryClient } from "@tanstack/react-query";

const REFETCH_INTERVAL_MS = parseFloat(
  import.meta.env.VITE_REFETCH_INTERVAL_MS || "120000",
);

export const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchInterval: REFETCH_INTERVAL_MS } },
});
