import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ErrorAlert from "../error-alert";

describe("ErrorAlert", () => {
  it("shows a loader's error when no ErrorBoundary wraps it", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const router = createMemoryRouter([
      {
        path: "/",
        element: <div />,
        loader: () => {
          throw new Error("the loader failed");
        },
        errorElement: <ErrorAlert />,
      },
    ]);

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("the loader failed")).toBeInTheDocument();
  });
});
