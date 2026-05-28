import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/hooks/use-toast";
import {
  apiBaseUrl,
  recalibrationInfoQuery,
  singleDeviceCalibrationQuery,
  startRecalibration,
  stopRecalibration,
} from "@/lib/api-client";
import { RqJobStatus } from "../../../../../types";

const ACTIVE_STATUSES: RqJobStatus[] = [
  RqJobStatus.STARTED,
  RqJobStatus.QUEUED,
  RqJobStatus.SCHEDULED,
  RqJobStatus.DEFERRED,
];

interface Props {
  deviceName: string;
  currentJobStatus: RqJobStatus | undefined;
}

export function CalibrationActions({ deviceName, currentJobStatus }: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const refreshCalibCache = async () => {
    await queryClient.invalidateQueries({
      queryKey: recalibrationInfoQuery(deviceName).queryKey,
    });
    await queryClient.invalidateQueries({
      queryKey: singleDeviceCalibrationQuery(deviceName).queryKey,
    });
  };

  const triggerCalib = useMutation({
    mutationKey: [apiBaseUrl, "admin", "recalibration", deviceName, "init"],
    async mutationFn() {
      return await startRecalibration(deviceName);
    },
    async onSuccess() {
      await refreshCalibCache();
      toast({ title: "Recalibration started", description: deviceName });
    },
    throwOnError: true,
  });

  const stopCalib = useMutation({
    mutationKey: [apiBaseUrl, "admin", "recalibration", deviceName, "cancel"],
    async mutationFn() {
      return await stopRecalibration(deviceName);
    },
    async onSuccess() {
      await refreshCalibCache();
      toast({ title: "Recalibration stopped", description: deviceName });
    },
    throwOnError: true,
  });

  const isRunning =
    currentJobStatus !== undefined && ACTIVE_STATUSES.includes(currentJobStatus);

  return (
    <div className="flex flex-col gap-1.5">
      {isRunning ? (
        <ConfirmDialog
          trigger={
            <Button
              variant="outline"
              className="w-full border-destructive text-destructive"
              disabled={stopCalib.isPending}
            >
              Stop recalibration
            </Button>
          }
          title="Stop recalibration?"
          description={`This will cancel the current calibration job for ${deviceName}. The previous calibration will remain active.`}
          confirmBtnLabel="Stop"
          cancelBtnLabel="Keep running"
          onConfirm={() => stopCalib.mutate()}
        />
      ) : (
        <ConfirmDialog
          trigger={
            <Button
              variant="outline"
              className="w-full border-blue-500 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950"
              disabled={triggerCalib.isPending}
            >
              Trigger recalibration
            </Button>
          }
          title="Trigger recalibration?"
          description={`This will start a calibration cycle for ${deviceName}. The job queue will be paused during calibration.`}
          confirmBtnLabel="Start calibration"
          cancelBtnLabel="Cancel"
          onConfirm={() => triggerCalib.mutate()}
        />
      )}
      <p className="text-xs text-muted-foreground text-center">
        Pauses job queue for ~12 min
      </p>
    </div>
  );
}
