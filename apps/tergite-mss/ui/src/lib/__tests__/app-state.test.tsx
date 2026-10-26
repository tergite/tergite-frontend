import { describe, expect, it } from "vitest";
import { useAppStore } from "../app-state";

describe("useAppStore", () => {
  it("forgets the current project and api token on clear", () => {
    const { setCurrentProjectId, setApiToken, clear } = useAppStore.getState();
    setCurrentProjectId("project-1");
    setApiToken("token-1");

    clear();

    expect(useAppStore.getState().currentProjectId).toBeUndefined();
    expect(useAppStore.getState().apiToken).toBeUndefined();
  });

  it("keeps only the theme in storage", () => {
    const { setApiToken, toggleIsDark, clear } = useAppStore.getState();
    setApiToken("token-1");
    toggleIsDark();

    const stored = localStorage.getItem("app-state") ?? "";

    expect(JSON.parse(stored).state).toEqual({ isDark: true });
    toggleIsDark();
    clear();
  });
});
