import { act, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { vi, describe, it, expect, afterEach, beforeEach } from "vitest";
import { useDebouncedValue } from "../use-debounced-value";

function Harness({ value }: { value: string }) {
  return <span data-testid="settled">{useDebouncedValue(value, 300)}</span>;
}

const settled = () => screen.getByTestId("settled").textContent;

describe("use-debounced-value", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("holds the first value until the delay has passed", () => {
    const { rerender } = render(<Harness value="a" />);
    rerender(<Harness value="ab" />);

    expect(settled()).toBe("a");

    act(() => vi.advanceTimersByTime(300));
    expect(settled()).toBe("ab");
  });

  // the point of the hook: one settle per pause, not one per keystroke
  it("skips the values typed through, settling only on the last", () => {
    const { rerender } = render(<Harness value="" />);

    for (const value of ["j", "jo", "joh", "john"]) {
      rerender(<Harness value={value} />);
      act(() => vi.advanceTimersByTime(100));
    }
    expect(settled()).toBe("");

    act(() => vi.advanceTimersByTime(300));
    expect(settled()).toBe("john");
  });
});
