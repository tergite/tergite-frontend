import { Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Device } from "@/lib/api/types";

export function DeviceStatusDiv({ device, className = "" }: Props) {
  return (
    <div
      className={cn(
        "flex w-fit items-center rounded-full px-2 py-1 text-[11px] font-semibold",
        device.is_online
          ? "bg-success-tint/10 text-success"
          : "bg-destructive/10 text-destructive",
        className,
      )}
    >
      {device.is_online ? (
        <>
          <Circle className="mr-1.5 h-1.5 w-1.5 fill-current" strokeWidth={0} />
          Online
        </>
      ) : (
        <>
          <Circle className="mr-1.5 h-1.5 w-1.5 fill-current" strokeWidth={0} />
          <span>Offline</span>
        </>
      )}
    </div>
  );
}
interface Props {
  device: Device;
  className?: string;
}
