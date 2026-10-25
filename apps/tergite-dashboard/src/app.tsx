import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useEffect } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { useAppStore } from "./lib/app-state";
import { queryClient } from "./lib/query-client";
import { revalidateOnProjectChange, routes } from "./router";

const router = createBrowserRouter(routes, {
  basename: import.meta.env.BASE_URL,
});
revalidateOnProjectChange(router);

export function App() {
  const isDark = useAppStore((state) => state.isDark);

  // the dialogs render outside the layout, so the theme goes on the document too
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
