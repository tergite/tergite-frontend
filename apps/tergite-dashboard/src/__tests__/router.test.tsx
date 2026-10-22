import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, createMemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AppStateContext, newAppState } from "../lib/app-state";
import { AppRouter } from "../router";

describe("AppRouter", () => {
  it("builds the router once however often the app state changes", () => {
    const routerConstructor = vi.fn(() =>
      createMemoryRouter([{ path: "/", element: <div /> }]),
    );
    const queryClient = new QueryClient();
    const renderWithProject = (projectId: string) => (
      <QueryClientProvider client={queryClient}>
        <AppStateContext.Provider
          value={{ ...newAppState(), currentProjectId: projectId }}
        >
          <AppRouter
            routerConstructor={
              routerConstructor as unknown as typeof createBrowserRouter
            }
          />
        </AppStateContext.Provider>
      </QueryClientProvider>
    );

    const { rerender } = render(renderWithProject("project-1"));
    rerender(renderWithProject("project-2"));

    expect(routerConstructor).toHaveBeenCalledTimes(1);
  });

  it("reloads the routes when the selected project changes", () => {
    const router = createMemoryRouter([{ path: "/", element: <div /> }]);
    const revalidate = vi.spyOn(router, "revalidate");
    const queryClient = new QueryClient();
    const renderWithProject = (projectId: string) => (
      <QueryClientProvider client={queryClient}>
        <AppStateContext.Provider
          value={{ ...newAppState(), currentProjectId: projectId }}
        >
          <AppRouter
            routerConstructor={
              (() => router) as unknown as typeof createBrowserRouter
            }
          />
        </AppStateContext.Provider>
      </QueryClientProvider>
    );

    const { rerender } = render(renderWithProject("project-1"));
    rerender(renderWithProject("project-1"));
    expect(revalidate).not.toHaveBeenCalled();

    rerender(renderWithProject("project-2"));
    expect(revalidate).toHaveBeenCalledTimes(1);
  });
});
