import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { QpuTimeRequestDialog } from "../qpu-time-request-dialog";
import type { Project, UserRequest } from "@/lib/api/types";

const requestQpuTimeExtension = vi.fn();

vi.mock("@/lib/api/requests", () => ({
  requestQpuTimeExtension: (...args: unknown[]) =>
    requestQpuTimeExtension(...args),
  refreshMyRequests: vi.fn(),
}));

const project = { id: "project-1", name: "test", admin_id: "user-1" } as Project;

const box = (id: string) => screen.getByLabelText(id) as HTMLInputElement;
const displayed = () =>
  ["days", "hrs", "mins", "secs"].map((id) => box(id).value);

async function openDialog() {
  const user = userEvent.setup();
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <QpuTimeRequestDialog project={project} requests={[]} />
    </QueryClientProvider>
  );
  await user.click(screen.getByRole("button", { name: /more qpu time/i }));
  return user;
}

async function submit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByPlaceholderText(/type your reason/i), "why");
  await user.click(screen.getByRole("button", { name: /submit/i }));
}

describe("QpuTimeRequestDialog", () => {
  beforeEach(() => {
    requestQpuTimeExtension.mockReset();
    requestQpuTimeExtension.mockResolvedValue({});
  });

  it("shows every unit of the default request, not just the non-zero one", async () => {
    await openDialog();
    expect(displayed()).toEqual(["0", "0", "60", "0"]);
  });

  it("sends exactly the duration on display", async () => {
    const user = await openDialog();
    await user.clear(box("mins"));
    await user.type(box("days"), "2");
    await user.type(box("hrs"), "3");
    await user.type(box("secs"), "10");

    expect(displayed()).toEqual(["2", "3", "0", "10"]);
    await submit(user);

    await vi.waitFor(() =>
      expect(requestQpuTimeExtension).toHaveBeenCalledWith(
        expect.objectContaining({
          seconds: 2 * 86_400 + 3 * 3_600 + 10,
        })
      )
    );
  });

  // clearing a box used to yield NaN, which zod rejected as "expected number,
  // received nan" — the request never left the browser
  it("treats a cleared box as zero rather than blocking the request", async () => {
    const user = await openDialog();
    await user.clear(box("mins"));
    await user.type(box("days"), "2");
    await submit(user);

    await vi.waitFor(() =>
      expect(requestQpuTimeExtension).toHaveBeenCalledWith(
        expect.objectContaining({ seconds: 2 * 86_400 })
      )
    );
  });

  it("ignores a pending request of another kind", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <QpuTimeRequestDialog
          project={project}
          requests={[
            {
              type: "project-pulse-access",
              resource_id: "project-1",
              status: "pending",
            } as UserRequest,
          ]}
        />
      </QueryClientProvider>
    );

    expect(screen.getByRole("button", { name: /more qpu time/i })).toBeEnabled();
  });
});
