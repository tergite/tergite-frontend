import { useCallback, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/hooks/use-toast";
import {
  startRecalibration,
  stopRecalibration,
  recalibrationInfoQuery,
  singleDeviceCalibrationQuery,
} from "@/lib/api-client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type DeviceCalibration,
  RqJobStatus,
} from "../../../../types";

interface Props {
  deviceName: string;
  calibration: DeviceCalibration | null;
}

const ACTIVE_STATUSES: RqJobStatus[] = [
  RqJobStatus.STARTED,
  RqJobStatus.QUEUED,
  RqJobStatus.SCHEDULED,
  RqJobStatus.DEFERRED,
];

function statusBadgeVariant(
  status: RqJobStatus | undefined
): "default" | "destructive" | "outline" | "secondary" {
  if (!status) return "outline";
  if (status === RqJobStatus.FINISHED) return "default";
  if (status === RqJobStatus.FAILED) return "destructive";
  if (ACTIVE_STATUSES.includes(status)) return "secondary";
  return "outline";
}

function CalibrationMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-muted/40 p-3">
      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
      <p className="text-base font-medium tabular-nums">{value}</p>
    </div>
  );
}

export function CalibrationCard({ deviceName, calibration }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isTriggering, setIsTriggering] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const { data: recalibInfo } = useQuery(
    recalibrationInfoQuery(deviceName)
  );

  const isRunning =
    recalibInfo?.current_job_status !== undefined &&
    ACTIVE_STATUSES.includes(recalibInfo.current_job_status);

  const refreshInfo = useCallback(async () => {
    await queryClient.invalidateQueries({
      queryKey: recalibrationInfoQuery(deviceName).queryKey,
    });
    await queryClient.invalidateQueries({
      queryKey: singleDeviceCalibrationQuery(deviceName).queryKey,
    });
  }, [queryClient, deviceName]);

  const handleTrigger = useCallback(async () => {
    setIsTriggering(true);
    try {
      await startRecalibration(deviceName);
      await refreshInfo();
      toast({ title: "Recalibration started", description: deviceName });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast({ title: "Failed to start recalibration", description: msg, variant: "destructive" });
    } finally {
      setIsTriggering(false);
    }
  }, [deviceName, refreshInfo, toast]);

  const handleStop = useCallback(async () => {
    setIsStopping(true);
    try {
      await stopRecalibration(deviceName);
      await refreshInfo();
      toast({ title: "Recalibration stopped", description: deviceName });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast({ title: "Failed to stop recalibration", description: msg, variant: "destructive" });
    } finally {
      setIsStopping(false);
    }
  }, [deviceName, refreshInfo, toast]);

  const prevJobStatus = recalibInfo?.previous_job_status;
  const currentJobStatus = recalibInfo?.current_job_status;

  // Pull aggregate calibration values from last calibration
  const qubits = calibration?.qubits ?? [];
  const t1Values = qubits
    .map((q) => q.t1_decoherence?.value)
    .filter((v): v is number => v != null);
  const t2Values = qubits
    .map((q) => q.t2_decoherence?.value)
    .filter((v): v is number => v != null);
  const medianT1 =
    t1Values.length > 0
      ? Math.round(t1Values.reduce((a, b) => a + b, 0) / t1Values.length)
      : null;
  const medianT2 =
    t2Values.length > 0
      ? Math.round(t2Values.reduce((a, b) => a + b, 0) / t2Values.length)
      : null;
  const readoutErrors = qubits
    .map((q) => q.readout_assignment_error?.value)
    .filter((v): v is number => v != null);
  const avgReadout =
    readoutErrors.length > 0
      ? ((readoutErrors.reduce((a, b) => a + b, 0) / readoutErrors.length) * 100).toFixed(2)
      : null;

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardDescription>Calibration</CardDescription>
          {prevJobStatus && (
            <Badge variant={statusBadgeVariant(prevJobStatus)}>
              {prevJobStatus}
            </Badge>
          )}
        </div>
        <p className="text-base font-medium">Latest run</p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* Metrics from last calibration */}
        {calibration ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              {medianT1 !== null && (
                <CalibrationMetric label="Median T1 (µs)" value={medianT1} />
              )}
              {medianT2 !== null && (
                <CalibrationMetric label="Median T2 (µs)" value={medianT2} />
              )}
              {avgReadout !== null && (
                <CalibrationMetric label="Avg readout err (%)" value={avgReadout} />
              )}
              <CalibrationMetric label="Qubits" value={qubits.length} />
            </div>
            <div className="text-xs text-muted-foreground">
              Last calibrated:{" "}
              <span className="font-medium">
                {calibration.last_calibrated
                  ? new Date(calibration.last_calibrated).toLocaleString()
                  : "—"}
              </span>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No calibration data available.</p>
        )}

        {/* Current job status */}
        {recalibInfo && (
          <div className="rounded-md border p-3 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Current job
              </p>
              {currentJobStatus && (
                <Badge variant={statusBadgeVariant(currentJobStatus)}>
                  {currentJobStatus}
                </Badge>
              )}
            </div>
            {isRunning && (
              <Progress className="h-1.5" value={undefined} />
            )}
            {recalibInfo.current_job_started_at && (
              <p className="text-xs text-muted-foreground">
                Started:{" "}
                {new Date(recalibInfo.current_job_started_at).toLocaleString()}
              </p>
            )}
            {recalibInfo.previous_job_error && (
              <p className="text-xs text-destructive truncate" title={recalibInfo.previous_job_error}>
                Error: {recalibInfo.previous_job_error}
              </p>
            )}
          </div>
        )}

        {/* Actions */}
        {isRunning ? (
          <ConfirmDialog
            trigger={
              <Button variant="outline" className="w-full border-destructive text-destructive" disabled={isStopping}>
                Stop recalibration
              </Button>
            }
            title="Stop recalibration?"
            description={`This will cancel the current calibration job for ${deviceName}. The previous calibration will remain active.`}
            confirmBtnLabel="Stop"
            cancelBtnLabel="Keep running"
            onConfirm={handleStop}
          />
        ) : (
          <ConfirmDialog
            trigger={
              <Button
                variant="outline"
                className="w-full border-blue-500 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950"
                disabled={isTriggering}
              >
                Trigger recalibration
              </Button>
            }
            title="Trigger recalibration?"
            description={`This will start a calibration cycle for ${deviceName}. The job queue will be paused during calibration.`}
            confirmBtnLabel="Start calibration"
            cancelBtnLabel="Cancel"
            onConfirm={handleTrigger}
          />
        )}
        <p className="text-xs text-muted-foreground text-center -mt-2">
          Pauses job queue for ~12 min
        </p>
      </CardContent>
    </Card>
  );
}
