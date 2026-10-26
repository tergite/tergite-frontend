import { Circle, CircleX } from "lucide-react";
import { cn } from "@/lib/utils";
import { type Device } from "@/lib/api/types";

export function DeviceStatusDiv({ device, className = "" }: Props) {
  return (
    <div className={cn("flex items-center w-fit", className)}>
      {device.is_online ? (
        <>
          <Circle className={`fill-green-600 w-2 h-2 mr-1`} strokeWidth={0} />
          Online
        </>
      ) : (
        <>
          <CircleX className="fill-destructive w-2 h-2 mr-1" strokeWidth={0} />
          <span className="border-b border-dashed border-primary">Offline</span>
        </>
      )}
    </div>
  );
}
interface Props {
  device: Device;
  className?: string;
}
