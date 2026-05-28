import { Badge } from "@/components/ui/badge";
import {
  type DeviceCalibration,
  type RecalibrationInfo,
  RqJobStatus,
} from "../../../../../types";

const ACTIVE_STATUSES: RqJobStatus[] = [
  RqJobStatus.STARTED,
  RqJobStatus.QUEUED,
  RqJobStatus.SCHEDULED,
  RqJobStatus.DEFERRED,
];

function statusBadgeVariant(
  status: RqJobStatus | undefined,
): "default" | "destructive" | "outline" | "secondary" {
  if (!status) return "outline";
  if (status === RqJobStatus.FINISHED) return "default";
  if (status === RqJobStatus.FAILED) return "destructive";
  if (ACTIVE_STATUSES.includes(status)) return "secondary";
  return "outline";
}

interface MetricBoxProps {
  label: string;
  value: string | number;
}

function MetricBox({ label, value }: MetricBoxProps) {
  return (
    <div className="rounded-md border bg-muted/40 p-3">
      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
        {label}
      </p>
      <p className="text-base font-medium tabular-nums">{value}</p>
    </div>
  );
}

interface Props {
  calibration: DeviceCalibration | null;
  recalibInfo: RecalibrationInfo | undefined;
}

export function CalibrationMetrics({ calibration, recalibInfo }: Props) {
  const qubits = calibration?.qubits ?? [];

  const medianT1 = median(
    qubits
      .map((q) => q.t1_decoherence?.value)
      .filter((v): v is number => v != null),
  );
  const medianT2 = median(
    qubits
      .map((q) => q.t2_decoherence?.value)
      .filter((v): v is number => v != null),
  );
  const readoutErrors = qubits
    .map((q) => q.readout_assignment_error?.value)
    .filter((v): v is number => v != null);
  const avgReadout =
    readoutErrors.length > 0
      ? (
          (readoutErrors.reduce((a, b) => a + b, 0) / readoutErrors.length) *
          100
        ).toFixed(2)
      : null;

  const prevStatus = recalibInfo?.previous_job_status;
  const currentStatus = recalibInfo?.current_job_status;

  return (
    <div className="flex flex-col gap-3">
      {/* Last-run badge */}
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Latest run</p>
        {prevStatus && (
          <Badge variant={statusBadgeVariant(prevStatus)}>{prevStatus}</Badge>
        )}
      </div>

      {/* Aggregate metrics */}
      {calibration ? (
        <>
          <div className="grid grid-cols-2 gap-3">
            {medianT1 !== null && (
              <MetricBox label="Median T1 (µs)" value={medianT1} />
            )}
            {medianT2 !== null && (
              <MetricBox label="Median T2 (µs)" value={medianT2} />
            )}
            {avgReadout !== null && (
              <MetricBox label="Avg readout err (%)" value={avgReadout} />
            )}
            <MetricBox label="Qubits" value={qubits.length} />
          </div>
          <p className="text-xs text-muted-foreground">
            Last calibrated:{" "}
            <span className="font-medium">
              {calibration.last_calibrated
                ? new Date(calibration.last_calibrated).toLocaleString()
                : "—"}
            </span>
          </p>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          No calibration data available.
        </p>
      )}

      {/* Current job status */}
      {recalibInfo && currentStatus && (
        <div className="rounded-md border p-3 flex items-center justify-between gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Current job
          </p>
          <Badge variant={statusBadgeVariant(currentStatus)}>
            {currentStatus}
          </Badge>
        </div>
      )}

      {recalibInfo?.previous_job_error && (
        <p
          className="text-xs text-destructive truncate"
          title={recalibInfo.previous_job_error}
        >
          Error: {recalibInfo.previous_job_error}
        </p>
      )}
    </div>
  );
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? Math.round(sorted[mid])
    : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}
