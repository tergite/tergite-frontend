import { cn } from "@/lib/utils";
import { PropsWithChildren } from "react";

export function DetailItem({
  label,
  value,
  className,
  children,
}: PropsWithChildren<Props>) {
  return (
    <div className={cn("flex", className)}>
      <span className="mr-2 text-muted-foreground">{label}</span>
      <span>{value ?? children}</span>
    </div>
  );
}

interface Props {
  label: string;
  value?: string;
  className?: string;
}
