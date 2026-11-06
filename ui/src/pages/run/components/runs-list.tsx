import { DateTime } from "luxon";
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
import { isFinal } from "@/lib/api/jobs";
import type { Job } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * The user's runs in the project, newest first: open one to load its circuit and results,
 * resubmit a finished one as a new run, or cancel one still running. Runs sent from the SDK
 * have no circuit to load, so they only open.
 */
export function RunsList({
  jobs,
  selectedJobId,
  onOpen,
  onResubmit,
  onCancel,
}: Props) {
  return (
    <Card id="runs">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">Runs</CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        {jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No runs yet.</p>
        ) : (
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead>Circuit</TableHead>
                <TableHead>Device</TableHead>
                <TableHead>Shots</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow
                  key={job.job_id}
                  data-state={
                    job.job_id === selectedJobId ? "selected" : undefined
                  }
                  className={cn("cursor-pointer")}
                  onClick={() => onOpen(job)}
                >
                  <TableCell className="font-mono text-[13px]">
                    {job.source?.circuits[0]?.name ?? job.job_id.slice(0, 8)}
                  </TableCell>
                  <TableCell>{job.device}</TableCell>
                  <TableCell>
                    {job.source?.shots ?? job.result?.shots ?? "—"}
                  </TableCell>
                  <TableCell>
                    <ProgressStatus
                      status={job.status ?? "pending"}
                      pendingValue="pending"
                      successValue="successful"
                      failureValue="failed"
                    />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {DateTime.fromISO(job.created_at).toRelative()}
                  </TableCell>
                  <TableCell className="text-right">
                    {!isFinal(job.status) ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(event) => {
                          event.stopPropagation();
                          onCancel(job);
                        }}
                      >
                        Cancel
                      </Button>
                    ) : (
                      job.source && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(event) => {
                            event.stopPropagation();
                            onResubmit(job);
                          }}
                        >
                          Resubmit
                        </Button>
                      )
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

interface Props {
  jobs: Job[];
  selectedJobId?: string;
  onOpen: (job: Job) => void;
  onResubmit: (job: Job) => void;
  onCancel: (job: Job) => void;
}
