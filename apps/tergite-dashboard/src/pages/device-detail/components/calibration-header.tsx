import { CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { type Device } from "@/lib/api/types";
import {
  type QubitProp,
} from "@/pages/device-detail/components/calibration-points";
import { PropSelector } from "./prop-selector";

export function CalibrationHeader({
  device,
  currentData,
  onCurrentDataChange: onCurrentPropChange,
  fieldLabels,
}: Props) {
  const description = (fieldLabels && fieldLabels[currentData]) || currentData;

  return (
    <div className="flex justify-between items-center p-6 flex-wrap h-auto space-y-1">
      <CardHeader className="p-0 pb-1">
        <CardTitle>{device.name}</CardTitle>
        <CardDescription>{description} data</CardDescription>
      </CardHeader>
      {onCurrentPropChange && fieldLabels && (
        <PropSelector
          value={currentData as QubitProp}
          onValueChange={onCurrentPropChange}
          fieldLabels={fieldLabels}
        />
      )}
    </div>
  );
}

interface Props {
  device: Device;
  currentData: string | QubitProp;
  onCurrentDataChange?: (value: QubitProp) => void;
  fieldLabels?: { [k: string]: string };
}
