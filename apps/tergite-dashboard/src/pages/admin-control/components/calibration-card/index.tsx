import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  recalibrationInfoQuery,
  singleDeviceCalibrationQuery,
} from "@/lib/api-client";
import { RqJobStatus } from "../../../../../types";
import { CalibrationMetrics } from "./metrics";
import { CalibrationActions } from "./actions";

const ACTIVE_STATUSES: RqJobStatus[] = [
  RqJobStatus.STARTED,
  RqJobStatus.QUEUED,
  RqJobStatus.SCHEDULED,
  RqJobStatus.DEFERRED,
];

interface Props {
  deviceName: string;
}

export function CalibrationCard({ deviceName }: Props) {
  const { data: calibration = null } = useQuery(
    singleDeviceCalibrationQuery(deviceName),
  );

  const { data: recalibInfo } = useQuery(recalibrationInfoQuery(deviceName));

  const currentJobStatus = recalibInfo?.current_job_status;
  const isRunning =
    currentJobStatus !== undefined && ACTIVE_STATUSES.includes(currentJobStatus);

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardDescription>Calibration</CardDescription>
          {isRunning && <Badge variant="secondary">Running</Badge>}
        </div>
        <p className="text-base font-medium">{deviceName}</p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <CalibrationMetrics
          calibration={calibration}
          recalibInfo={recalibInfo}
        />
        <CalibrationActions
          deviceName={deviceName}
          currentJobStatus={currentJobStatus}
        />
      </CardContent>
    </Card>
  );
}
