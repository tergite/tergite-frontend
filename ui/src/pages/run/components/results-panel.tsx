import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProgressStatus } from "@/components/ui/progress-status";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getMyJobLogfileUrl, isFinal } from "@/lib/api/jobs";
import type { Job } from "@/lib/api/types";
import { type CircuitCounts, getCircuitCounts } from "@/lib/qasm/counts";

/**
 * How a run went: its status while it runs, then its counts as a histogram or a table, its
 * failure reason if it failed, and its logfile and counts to download.
 */
export function ResultsPanel({ job, onCancel, isCancelling }: Props) {
  const circuits = getCircuitCounts(job?.result);
  const [circuitIndex, setCircuitIndex] = useState(0);
  const circuit = circuits[Math.min(circuitIndex, circuits.length - 1)];
  const isCancellable = !!job && !isFinal(job.status);
  const hasActions =
    isCancellable || !!job?.download_url || circuits.length > 0;

  if (!job) {
    return (
      <Card id="results" className="min-w-0">
        <CardHeader>
          <CardTitle className="text-lg">Results</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Run the circuit, or open a run below.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card id="results" className="flex min-w-0 flex-col">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0 border-b pb-4">
        <div className="space-y-1">
          <CardTitle className="text-lg">Results</CardTitle>
          <p className="text-sm text-muted-foreground">
            {[
              job.source?.circuits[0]?.name,
              job.device,
              job.result?.shots && `${job.result.shots} shots`,
              job.duration_in_secs != null &&
                `${job.duration_in_secs.toFixed(1)} s`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <ProgressStatus
          status={job.status ?? "pending"}
          pendingValue="pending"
          successValue="successful"
          failureValue="failed"
          className="text-sm"
        />
      </CardHeader>

      <CardContent className="flex-1 pt-4">
        {job.status === "failed" && (
          <p role="alert" className="text-sm text-destructive">
            {job.failure_reason ?? "The job failed."}
          </p>
        )}
        {job.status === "cancelled" && (
          <p className="text-sm text-muted-foreground">
            {job.cancellation_reason ?? "The job was cancelled."}
          </p>
        )}
        {!isFinal(job.status) && (
          <p className="text-sm text-muted-foreground">
            {job.status === "executing" ? "Running on" : "Queued for"}{" "}
            {job.device}…
          </p>
        )}
        {job.status === "successful" && !circuit && (
          <p className="text-sm text-muted-foreground">
            Measured at level 1: IQ points, in the logfile.
          </p>
        )}
        {circuit && (
          <Tabs defaultValue="histogram">
            <div className="flex flex-wrap items-center justify-between gap-2">
              {circuits.length > 1 ? (
                <select
                  aria-label="Circuit"
                  value={circuitIndex}
                  onChange={(event) =>
                    setCircuitIndex(Number(event.target.value))
                  }
                  className="rounded-md border bg-background px-2 py-1 text-sm"
                >
                  {circuits.map((v, index) => (
                    <option key={index} value={index}>
                      {v.name}
                    </option>
                  ))}
                </select>
              ) : (
                <span />
              )}
              <TabsList>
                <TabsTrigger value="histogram">Histogram</TabsTrigger>
                <TabsTrigger value="counts">Counts</TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="histogram">
              <Histogram circuit={circuit} />
            </TabsContent>
            <TabsContent value="counts">
              <CountsTable circuit={circuit} />
            </TabsContent>
          </Tabs>
        )}
      </CardContent>

      {hasActions && (
        <div className="flex flex-wrap justify-end gap-2 border-t p-4">
          {isCancellable && (
            <Button
              variant="outline"
              onClick={() => onCancel(job.job_id)}
              disabled={isCancelling}
            >
              Cancel
            </Button>
          )}
          {job.download_url && (
            <Button variant="outline" asChild>
              <a href={getMyJobLogfileUrl(job.job_id)} download>
                <Download className="mr-2 h-4 w-4" />
                Logfile
              </a>
            </Button>
          )}
          {circuits.length > 0 && (
            <Button variant="outline" onClick={() => saveCounts(job, circuits)}>
              <Download className="mr-2 h-4 w-4" />
              Counts
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}

interface Props {
  job?: Job;
  onCancel: (jobId: string) => void;
  isCancelling: boolean;
}

function Histogram({ circuit }: { circuit: CircuitCounts }) {
  const highest = Math.max(...circuit.counts.map((v) => v.count), 1);
  const summary = circuit.counts
    .map((v) => `${v.outcome}: ${v.count}`)
    .join(", ");
  return (
    <div
      role="img"
      aria-label={`Counts of ${circuit.name}: ${summary}`}
      className="pt-4"
    >
      <div className="flex h-56 items-end gap-3 border-b px-2">
        {circuit.counts.map((v) => (
          <div
            key={v.outcome}
            className="flex h-full min-w-6 flex-1 flex-col items-center justify-end gap-1"
          >
            <span className="text-xs text-muted-foreground">{v.count}</span>
            <div
              className="w-full max-w-16 rounded-t-md bg-primary"
              style={{ height: `${Math.max((v.count / highest) * 100, 1)}%` }}
            />
          </div>
        ))}
      </div>
      <div className="flex gap-3 px-2 pt-1">
        {circuit.counts.map((v) => (
          <span
            key={v.outcome}
            className="min-w-6 flex-1 text-center font-mono text-xs"
          >
            {v.outcome}
          </span>
        ))}
      </div>
    </div>
  );
}

function CountsTable({ circuit }: { circuit: CircuitCounts }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Outcome</TableHead>
          <TableHead className="text-right">Count</TableHead>
          <TableHead className="text-right">Share</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {circuit.counts.map((v) => (
          <TableRow key={v.outcome}>
            <TableCell className="font-mono">{v.outcome}</TableCell>
            <TableCell className="text-right">{v.count}</TableCell>
            <TableCell className="text-right">
              {((v.count / Math.max(circuit.shots, 1)) * 100).toFixed(1)}%
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** Downloads the run's counts as JSON: each circuit's outcomes and how often they came up */
function saveCounts(job: Job, circuits: CircuitCounts[]) {
  const content = Object.fromEntries(
    circuits.map((v) => [
      v.name,
      Object.fromEntries(v.counts.map((c) => [c.outcome, c.count])),
    ]),
  );
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(content, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${job.job_id}-counts.json`;
  link.click();
  URL.revokeObjectURL(url);
}
