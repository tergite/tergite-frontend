import { Card } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";

/** A headline number on the home page, with what it counts and a line of context. */
export function MetricCard({ label, value, detail, Icon }: Props) {
  return (
    <Card className="group relative overflow-hidden p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-metric-hover">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {label}
          </p>
          <p className="mt-3 font-display text-3xl font-semibold tracking-tight">
            {value}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
        </div>
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/[0.08] text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
          <Icon className="h-5 w-5" />
        </span>
      </div>
    </Card>
  );
}

interface Props {
  label: string;
  value: string;
  detail: string;
  Icon: LucideIcon;
}
