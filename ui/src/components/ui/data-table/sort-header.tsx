import { cn } from "@/lib/utils";
import { Column } from "@tanstack/react-table";
import { ArrowDown, ArrowUp } from "lucide-react";

export function SortHeader<TData, TValue>({
  column,
  label,
  className = "",
}: Props<TData, TValue>) {
  {
    const isAscending = column.getIsSorted() === "asc";
    return (
      <div
        className={cn("cursor-pointer", className)}
        onClick={() => column.toggleSorting(isAscending)}
      >
        <div className="flex">
          {label}
          {!isAscending && <ArrowDown className="ml-1 h-4 w-4" />}
          {isAscending && <ArrowUp className="ml-1 h-4 w-4" />}
        </div>
      </div>
    );
  }
}

interface Props<TData, TValue> {
  column: Column<TData, TValue>;
  label: string;
  className?: string;
}
