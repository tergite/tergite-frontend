import { Circle, CircleX } from "lucide-react";
import { cn } from "@/lib/utils";

export function HealthStatus({
  isHealthy,
  className = "",
  healthyLabel = "Live",
  unhealthyLabel = "Expired",
}: Props) {
  return (
    <div className={cn("flex items-center w-fit", className)}>
      {isHealthy ? (
        <>
          <Circle className={`fill-green-600 w-2 h-2 mr-1`} strokeWidth={0} />
          {healthyLabel}
        </>
      ) : (
        <>
          <CircleX className="fill-destructive w-2 h-2 mr-1" strokeWidth={0} />
          <span className="border-b border-dashed border-primary">
            {unhealthyLabel}
          </span>
        </>
      )}
    </div>
  );
}

interface Props {
  isHealthy: boolean;
  healthyLabel?: string;
  unhealthyLabel?: string;
  className?: string;
}
