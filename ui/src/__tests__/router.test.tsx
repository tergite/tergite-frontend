import { createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAppStore } from "../lib/app-state";
import { revalidateOnProjectChange } from "../router";

describe("revalidateOnProjectChange", () => {
  afterEach(() => useAppStore.getState().clear());

  it("reloads the routes only when the selected project changes", () => {
    const router = createMemoryRouter([{ path: "/", element: <div /> }]);
    const revalidate = vi.spyOn(router, "revalidate");
    useAppStore.getState().setCurrentProjectId("project-1");
    const unsubscribe = revalidateOnProjectChange(router);

    useAppStore.getState().setCurrentProjectId("project-1");
    useAppStore.getState().toggleIsDark();
    expect(revalidate).not.toHaveBeenCalled();

    useAppStore.getState().setCurrentProjectId("project-2");
    expect(revalidate).toHaveBeenCalledTimes(1);
    unsubscribe();
  });
});
