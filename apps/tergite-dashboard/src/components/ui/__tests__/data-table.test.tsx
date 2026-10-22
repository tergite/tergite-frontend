import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ColumnDef } from "@tanstack/react-table";
import { describe, expect, it } from "vitest";
import { DataTable } from "../data-table";
import { findSelectedRow } from "../data-table/selection";

type Item = { id: string; name: string };

const columns: ColumnDef<Item>[] = [{ accessorKey: "name", header: "Name" }];

describe("DataTable", () => {
  it("keeps a selected row selected when the data is reordered", () => {
    const rowSelection = { b: true };

    render(
      <DataTable
        columns={columns}
        data={[
          { id: "b", name: "Bravo" },
          { id: "a", name: "Alpha" },
        ]}
        options={{ state: { rowSelection } }}
      />,
    );

    expect(screen.getByText("Bravo").closest("tr")).toHaveAttribute(
      "data-state",
      "selected",
    );
    expect(screen.getByText("Alpha").closest("tr")).not.toHaveAttribute(
      "data-state",
      "selected",
    );
  });
});

describe("findSelectedRow", () => {
  it("finds the selected row by its id", () => {
    const rows = [
      { id: "a", name: "Alpha" },
      { id: "b", name: "Bravo" },
    ];

    expect(findSelectedRow(rows, { b: true })).toEqual(rows[1]);
    expect(findSelectedRow(rows, {})).toBeUndefined();
  });
});
