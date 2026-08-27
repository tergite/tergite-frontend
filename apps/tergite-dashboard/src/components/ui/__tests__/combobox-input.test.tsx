import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { vi, describe, it, expect } from "vitest";
import { useState } from "react";
import { ComboboxInput } from "../combobox-input";

const SUGGESTIONS = [
  "john.doe@example.com",
  "jane.doe@example.com",
  "paul.smith@example.com",
];

function Harness({ onChange }: { onChange?: (value: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <ComboboxInput
      id="email"
      suggestions={SUGGESTIONS}
      value={value}
      onChange={(ev) => {
        setValue(ev.target.value);
        onChange?.(ev.target.value);
      }}
    />
  );
}

const options = () => screen.queryAllByRole("option");

describe("combobox-input", () => {
  it("offers only the suggestions matching what has been typed", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByRole("combobox"), "doe");

    expect(options().map((item) => item.textContent)).toEqual([
      "john.doe@example.com",
      "jane.doe@example.com",
    ]);
  });

  // the input is outside the popover content, so a click on it used to read as an
  // interaction outside and shut the list the focus had just opened
  it("keeps the list up when the input itself is clicked", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("combobox"));
    expect(options()).toHaveLength(SUGGESTIONS.length);

    await user.click(screen.getByRole("combobox"));
    expect(options()).toHaveLength(SUGGESTIONS.length);
  });

  it("puts the picked suggestion in the field", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByRole("combobox"), "jane");
    await user.click(screen.getByRole("option", { name: /jane\.doe/ }));

    expect(screen.getByRole("combobox")).toHaveValue("jane.doe@example.com");
    expect(options()).toHaveLength(0);
  });

  it("takes an address that matches nothing, since the list is not closed", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Harness onChange={onChange} />);

    await user.type(screen.getByRole("combobox"), "newcomer@example.com");

    expect(screen.getByRole("combobox")).toHaveValue("newcomer@example.com");
    expect(options()).toHaveLength(0);
  });

  it("moves through the list with the arrow keys and takes one on Enter", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByRole("combobox"), "doe");
    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");

    expect(screen.getByRole("combobox")).toHaveValue("jane.doe@example.com");
  });

  // Enter has to reach the form when nothing is highlighted, or picking a suggestion
  // would be the only way to submit
  it("leaves Enter alone when no suggestion is highlighted", async () => {
    const onSubmit = vi.fn((ev) => ev.preventDefault());
    const user = userEvent.setup();
    render(
      <form onSubmit={onSubmit}>
        <Harness />
      </form>
    );

    await user.type(screen.getByRole("combobox"), "doe");
    await user.keyboard("{Enter}");

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape without changing the value", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByRole("combobox"), "doe");
    await user.keyboard("{Escape}");

    expect(options()).toHaveLength(0);
    expect(screen.getByRole("combobox")).toHaveValue("doe");
  });
});
