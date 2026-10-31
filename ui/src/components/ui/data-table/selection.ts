import { RowSelectionState } from "@tanstack/react-table";

/**
 * The row whose id is selected; DataTable keys the selection by row id
 */
export function findSelectedRow<T extends { id: string }>(
  rows: T[],
  selection: RowSelectionState,
): T | undefined {
  return rows.find((row) => selection[row.id]);
}
