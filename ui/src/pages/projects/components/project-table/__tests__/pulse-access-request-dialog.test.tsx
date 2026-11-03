import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { PulseAccessRequestDialog } from "../pulse-access-request-dialog";
import type { Project, UserRequest } from "@/lib/api/types";

const requestPulseAccess = vi.fn();

vi.mock("@/lib/api/requests", () => ({
  requestPulseAccess: (...args: unknown[]) => requestPulseAccess(...args),
  refreshMyRequests: vi.fn(),
}));

const project = { id: "project-1", name: "test", admin_id: "user-1" } as Project;

function renderDialog(requests: Partial<UserRequest>[] = []) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <PulseAccessRequestDialog
        project={project}
        requests={requests as UserRequest[]}
      />
    </QueryClientProvider>
  );
}

describe("PulseAccessRequestDialog", () => {
  beforeEach(() => {
    requestPulseAccess.mockReset();
    requestPulseAccess.mockResolvedValue({});
  });

  it("sends the reason for the project", async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(
      screen.getByRole("button", { name: /ask for pulse-level jobs/i })
    );
    await user.type(screen.getByPlaceholderText(/type your reason/i), "why");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await vi.waitFor(() =>
      expect(requestPulseAccess).toHaveBeenCalledWith({
        project_id: "project-1",
        reason: "why",
      })
    );
  });

  it("is disabled while a request on the project is pending", () => {
    renderDialog([
      { type: "project-pulse-access", resource_id: "project-1", status: "pending" },
    ]);

    expect(screen.getByRole("button", { name: /request pending/i })).toBeDisabled();
  });

  it("ignores a pending request of another kind", () => {
    renderDialog([
      { type: "project-qpu-seconds", resource_id: "project-1", status: "pending" },
    ]);

    expect(
      screen.getByRole("button", { name: /ask for pulse-level jobs/i })
    ).toBeEnabled();
  });
});
