import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getRecalibrationInfoQuery } from "@/lib/api/admin-control";
import { getDeviceCalibrationQuery } from "@/lib/api/devices";
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
    getDeviceCalibrationQuery(deviceName),
  );

  const { data: recalibInfo } = useQuery(getRecalibrationInfoQuery(deviceName));

  const currentJobStatus = recalibInfo?.current_job_status;
  const isRunning =
    currentJobStatus !== undefined && ACTIVE_STATUSES.includes(currentJobStatus);

  return (
    <Card className="h-full" data-testid="calibration-card">
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
