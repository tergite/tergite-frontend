import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { Gauge } from "lucide-react";
import { Link } from "react-router-dom";
import { type Project } from "@/lib/api/types";

/**
 * Remaining QPU seconds on the user's personal project.
 *
 * Shows the personal project rather than the selected one: it is the number with no
 * other home, since every user has exactly one and it governs their own experiments
 * rather than a balance shared with a group.
 *
 * Deliberately a number rather than a proportional bar. The configured allowance lives
 * in MSS config that the dashboard cannot see, and "40% of an allowance" answers a less
 * useful question than "how long have I got".
 */
export function QpuMeter({ project, isExpanded }: Props) {
  if (!project) {
    return null;
  }

  const remaining = Math.max(project.qpu_seconds, 0);
  const isEmpty = remaining <= 0;
  const label = isEmpty
    ? "No QPU time on your personal project"
    : `${formatSeconds(remaining)} of QPU time left`;

  if (!isExpanded) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div data-cy-qpu-meter className="mx-auto">
            <Gauge
              className={cn(
                "h-4 w-4",
                isEmpty ? "text-destructive" : "text-muted-foreground",
              )}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <div data-cy-qpu-meter className="grid gap-1 px-6 w-full text-xs">
      <span className="text-muted-foreground">My QPU time</span>
      {isEmpty ? (
        // a user cannot grant themselves time, so this points at the request flow
        <Link
          to="/projects"
          data-cy-request-qpu-time
          className="underline text-destructive"
        >
          None left — request more
        </Link>
      ) : (
        <span data-cy-qpu-remaining className="font-medium">
          {formatSeconds(remaining)} left
        </span>
      )}
    </div>
  );
}

interface Props {
  project?: Project;
  isExpanded: boolean;
}

/**
 * Renders a duration in seconds in the largest unit that keeps it readable
 *
 * @param value - the number of seconds
 */
function formatSeconds(value: number): string {
  if (value >= 3600) {
    return `${Math.round(value / 3600)}h`;
  }
  if (value >= 60) {
    return `${Math.round(value / 60)}m`;
  }
  return `${Math.round(value)}s`;
}
