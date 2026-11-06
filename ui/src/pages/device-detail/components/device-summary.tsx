import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { DeviceStatusDiv } from "@/components/ui/device-status-div";
import { Separator } from "@/components/ui/separator";
import type {
  CalibrationValue,
  Device,
  DeviceCalibration,
  Qubit,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { DateTime } from "luxon";
import { useMemo } from "react";
import { DetailItem } from "./detail-item";

export function DeviceSummary({
  device,
  calibrationData,
  className = "",
}: Props) {
  const qubits = calibrationData?.qubits;
  const deviceMedians: DeviceCalibrationMedians = useMemo(
    () =>
      getCalibrationMedians(qubits ?? [], [
        "t1_decoherence",
        "t2_decoherence",
        "readout_assignment_error",
      ]),
    [qubits]
  );

  return (
    <Card id="device-summary" className={cn("overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start bg-muted/50 justify-between">
        <div className="grid gap-0.5">
          <CardTitle className="group flex items-center gap-2 text-lg">
            {device.name}
          </CardTitle>
          <CardDescription>Version {device.version}</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="p-6 text-sm">
        <div className="grid gap-3">
          <div className="font-semibold">Details</div>
          <ul className="grid gap-3">
            <DetailItem label="Status">
              <DeviceStatusDiv device={device} />
            </DetailItem>

            <DetailItem label="Basis gates">
              {device.basis_gates.join(", ")}
            </DetailItem>

            <DetailItem label="Type">
              {device.is_simulator ? "simulator" : "physical"}
            </DetailItem>
          </ul>
          <Separator className="my-2" />
          <ul className="grid gap-3">
            <DetailItem label="Qubits">
              <span className="text-2xl">{device.number_of_qubits}</span>
            </DetailItem>
          </ul>
        </div>

        <Separator className="my-4" />
        <div className="grid gap-3">
          <div className="font-semibold">Calibration Information</div>
          <ul className="grid gap-3">
            <DetailItem label="Median readout error">
              {deviceMedians.readout_assignment_error?.value?.toFixed(2)}{" "}
              {deviceMedians.readout_assignment_error?.unit}
            </DetailItem>
            <DetailItem label="Median T1">
              {deviceMedians.t1_decoherence?.value?.toFixed(2)}{" "}
              {deviceMedians.t1_decoherence?.unit}
            </DetailItem>
            <DetailItem label="Median T2">
              {deviceMedians.t2_decoherence?.value?.toFixed(2)}{" "}
              {deviceMedians.t2_decoherence?.unit}
            </DetailItem>
          </ul>
        </div>
      </CardContent>
      <CardFooter className="flex flex-row items-center border-t bg-muted/50 px-6 py-3">
        <div className="text-xs text-muted-foreground">
          {calibrationData ? (
            <>
              Last calibrated{" "}
              <time dateTime={calibrationData.last_calibrated ?? undefined}>
                {calibrationData.last_calibrated &&
                  DateTime.fromISO(calibrationData.last_calibrated).toRelative()}
              </time>
            </>
          ) : (
            "Not calibrated yet"
          )}
        </div>
      </CardFooter>
    </Card>
  );
}

interface Props {
  device: Device;
  // none for a device not calibrated yet
  calibrationData?: DeviceCalibration;
  className?: string;
}

/** The median of each field, over the values present, in the unit of the first */
function getCalibrationMedians(
  values: Qubit[],
  fields: (keyof Qubit)[],
): { [k: string]: AggregateValue } {
  const constituentLists: { [k: string]: number[] } = Object.fromEntries(
    fields.map((field) => [
      field,
      values
        .map((v) => (v[field] as CalibrationValue | null | undefined)?.value)
        .filter((v): v is number => typeof v === "number")
        .sort((a, b) => a - b),
    ]),
  );

  return Object.fromEntries(
    fields
      .filter((field) => constituentLists[field]?.length > 0)
      .map((field) => [
        field,
        {
          unit: (values[0][field] as CalibrationValue | null)?.unit ?? "",
          value: computeMedian(constituentLists[field]),
        },
      ]),
  );
}

function computeMedian(sorted: number[]): number {
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle];
}

type AggregateValue = { unit: string; value: number };

type DeviceCalibrationMedians = {
  t1_decoherence?: AggregateValue;
  t2_decoherence?: AggregateValue;
  readout_assignment_error?: AggregateValue;
};
