import {
  DrawerClose,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { ProgressStatus } from "@/components/ui/progress-status";
import { type Job } from "@/lib/api/types";
import { DateTime, Duration } from "luxon";
import { IconButton } from "@/components/ui/button";
import { X } from "lucide-react";

export function JobDetailDrawerContent({ job }: Props) {
  return (
    <div
      data-cy-job-detail
      className="h-full w-[300px] md:w-[500px] lg:w-[600px] xl:w-[700px] mt-4"
    >
      <DrawerHeader>
        <DrawerClose asChild>
          <IconButton variant="outline" className="ml-auto" Icon={X} />
        </DrawerClose>
        <DrawerTitle>Job: {job.job_id}</DrawerTitle>
        <DrawerDescription>Details about this job.</DrawerDescription>
      </DrawerHeader>
      <div className="p-4 pb-0">
        <div>
          <h4 className="text-md font-semibold mb-4">Details</h4>
          <div className="flex">
            <div className="mr-2 text-muted-foreground">Status: </div>
            <ProgressStatus
              status={job.status}
              pendingValue={"pending"}
              successValue={"successful"}
              failureValue={"failed"}
            />
          </div>

          <div className="flex">
            <span className="mr-2 text-muted-foreground">Created at:</span>
            <span>
              {DateTime.fromISO(job.created_at).toLocaleString(
                DateTime.DATETIME_MED
              )}
            </span>
          </div>

          <div className="flex">
            <span className="mr-2 text-muted-foreground">Device:</span>
            <span>{job.device}</span>
          </div>

          <div className="flex">
            <span className="mr-2 text-muted-foreground">Duration:</span>
            <span>
              {job.duration_in_secs
                ? Duration.fromObject({
                    seconds: job.duration_in_secs,
                  }).toHuman()
                : "N/A"}
            </span>
          </div>

          {job.failure_reason && (
            <div className="flex">
              <span className="mr-2 text-muted-foreground">Error:</span>
              <span>{job.failure_reason}</span>
            </div>
          )}
        </div>
        <div className="mt-3"></div>
      </div>
    </div>
  );
}

interface Props {
  job: Job;
}
