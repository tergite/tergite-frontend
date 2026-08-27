import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { describe, it, expect } from "vitest";
import { useState } from "react";
import { MultiInput } from "../multi-input";
import { ComboboxInput } from "../combobox-input";

function Harness({
  initial = [""],
  InputComponent,
}: {
  initial?: string[];
  InputComponent?: React.ComponentType<
    React.InputHTMLAttributes<HTMLInputElement>
  >;
}) {
  const [value, setValue] = useState<(string | number)[] | undefined>(initial);
  return (
    <MultiInput
      id="emails"
      name="emails"
      type="email"
      value={value}
      onChange={setValue}
      InputComponent={InputComponent}
    />
  );
}

const rows = () =>
  [...document.querySelectorAll("input[data-index]")] as HTMLInputElement[];

describe("multi-input", () => {
  it("puts what is typed in the row that was typed into", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["", "", ""]} />);

    await user.type(rows()[1], "middle@example.com");

    expect(rows().map((r) => r.value)).toEqual([
      "",
      "middle@example.com",
      "",
    ]);
  });

  it("adds a row on the plus button", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /plus/i }));

    expect(rows()).toHaveLength(2);
  });

  it("drops the row whose close button is pressed, not another", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["first@example.com", "second@example.com"]} />);

    await user.click(document.querySelector("#emails-0-del-btn")!);

    expect(rows().map((r) => r.value)).toEqual(["second@example.com"]);
  });

  // the row index used to be read off the DOM node's dataset, which a control that
  // suggests values has no way to carry; a combobox row must still edit its own row
  it("routes the change by row when a custom control replaces the input", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["", ""]} InputComponent={ComboboxInput} />);

    await user.type(rows()[1], "second@example.com");

    expect(rows().map((r) => r.value)).toEqual(["", "second@example.com"]);
  });
});
