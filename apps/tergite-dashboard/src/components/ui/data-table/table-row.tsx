import { Row, flexRender } from "@tanstack/react-table";
import { TableCell, TableRow } from "@/components/ui/table";
import React from "react";

export const DataTableRow = React.forwardRef(function <TData>(
  { row, onClick }: Props<TData>,
  ref: React.ForwardedRef<HTMLTableRowElement>
) {
  return (
    <TableRow
      ref={ref}
      className="cursor-pointer"
      data-state={row.getIsSelected() && "selected"}
      onClick={() => onClick && onClick(row)}
      data-id={row.index}
    >
      {row.getVisibleCells().map((cell) => (
        <TableCell
          key={cell.id}
          width={cell.column.columnDef.size}
          className={cell.column.columnDef.meta?.rowClassName ?? ""}
          data-header={cell.column.id}
        >
          {flexRender(cell.column.columnDef.cell, cell.getContext())}
        </TableCell>
      ))}
    </TableRow>
  );
}) as <T>(
  props: Props<T> & { ref?: React.ForwardedRef<HTMLTableRowElement> }
) => React.ReactNode;

interface Props<TData> {
  row: Row<TData>;
  onClick?: (row: Row<TData>) => void;
}
