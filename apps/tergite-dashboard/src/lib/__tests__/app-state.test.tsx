import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useRootAppState } from "../app-state";

describe("useRootAppState", () => {
  it("forgets the current project and api token on clear", () => {
    const { result } = renderHook(() => useRootAppState());
    act(() => {
      result.current.setCurrentProjectId("project-1");
      result.current.setApiToken("token-1");
    });

    act(() => result.current.clear());

    expect(result.current.currentProjectId).toBeUndefined();
    expect(result.current.apiToken).toBeUndefined();
  });
});
