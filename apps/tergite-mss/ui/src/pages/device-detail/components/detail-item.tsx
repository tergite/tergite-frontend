import { cn } from "@/lib/utils";
import { PropsWithChildren } from "react";

export function DetailItem({
  label,
  children,
  className = "",
}: PropsWithChildren<Props>) {
  return (
    <li
      className={cn("flex items-center justify-between flex-wrap", className)}
    >
      <span className="text-muted-foreground">{label}</span>
      {children}
    </li>
  );
}

interface Props {
  label: string;
  className?: string;
}
